"""MatchLens live server: replays synthetic matches through the live engine and
streams timed, machine-readable messages over WebSocket.

    uvicorn matchlens.server:app --reload
    open http://localhost:8000

Endpoints
    GET  /api/matches                     catalogue of available matches (no final scores: no spoilers)
    GET  /api/matches/{match_id}          match summary + live session status
    GET  /api/sessions/{match_id}/state   full current snapshot, including players
    POST /api/sessions/{match_id}/control {"action": "pause"|"resume"|"speed"|"restart", "speed": 60, "from_minute": 0}
    WS   /ws/{match_id}?speed=60&from_minute=0&restart=0
         Joins the running session for that match, or starts one. First message is `hello`
         (teams, line-ups, pre-match context, current state); then `state`, `event`, `alert`,
         `win_prob_swing`, `minute`, `players`, `session` messages. See OVERLAY.md.
         Clients may send {"action": "pause"} etc. over the socket as well.
"""
from __future__ import annotations

import asyncio
import json
import time
from collections import deque
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from matchsim.replay import load_match
from .models import load_models
from .state import MatchState

ROOT = Path(__file__).resolve().parents[1]
DATA_DIRS = [ROOT / "data" / "matches", ROOT / "data" / "season_2026-27" / "matches"]
STATIC = Path(__file__).parent / "static"
PROTOCOL_VERSION = 1

# events that trigger an immediate `state` message (others are throttled)
STATE_NOW = {"goal", "card", "substitution", "period_start", "period_end", "match_end", "added_time", "kick_off"}
# fields on pass events that are only known after the fact – never sent live
LOOKAHEAD_FIELDS = {"key_pass", "assist", "provider_completion_prob"}
STATE_INTERVAL_S = 1.0
PLAYERS_INTERVAL_S = 10.0

MODELS = load_models()


# --------------------------------------------------------------------------- catalogue
def _catalogue() -> dict:
    cat = {}
    for d in DATA_DIRS:
        if not d.exists():
            continue
        for mdir in sorted(p for p in d.iterdir() if (p / "metadata.json").exists()):
            meta = json.loads((mdir / "metadata.json").read_text(encoding="utf-8"))
            cat[meta["match_id"]] = {
                "match_id": meta["match_id"],
                "path": str(mdir),
                "competition": meta.get("competition", {}),
                "kickoff_utc": meta.get("kickoff_utc"),
                "venue": meta.get("venue", {}).get("stadium"),
                "home": {k: meta["home"][k] for k in ("team_id", "name", "abbr", "colors")},
                "away": {k: meta["away"][k] for k in ("team_id", "name", "abbr", "colors")},
                "source": "season" if "season" in str(d) else "demo",
            }
    return cat


CATALOGUE = _catalogue()


def team_block(t: dict) -> dict:
    keep = ("player_id", "name", "short_name", "shirt", "position", "group", "nationality", "age", "is_star")
    return {"team_id": t["team_id"], "name": t["name"], "short_name": t["short_name"], "abbr": t["abbr"],
            "nickname": t["nickname"], "market": t["market"], "colors": t["colors"], "formation": t["formation"],
            "starting_xi": [{k: p[k] for k in keep} for p in t["starting_xi"]],
            "bench": [{k: p[k] for k in keep} for p in t["bench"]]}


def slim_event(ev: dict) -> dict:
    d = {k: v for k, v in (ev.get("details") or {}).items() if k not in LOOKAHEAD_FIELDS}
    out = {k: ev.get(k) for k in ("event_id", "type", "team_side", "player_id", "player_name", "shirt",
                                  "possession_id", "play_pattern", "location_abs", "end_location_abs",
                                  "outcome", "duration_s")}
    out["details"] = d
    if ev.get("derived"):
        out["derived"] = ev["derived"]
    return out


# --------------------------------------------------------------------------- session
class MatchSession:
    def __init__(self, match_id: str, speed: float = 60.0, from_minute: float = 0.0):
        info = CATALOGUE[match_id]
        self.match_id = match_id
        m = load_match(info["path"])
        self.meta, self.events = m["metadata"], m["events"]
        self.speed = max(0.1, float(speed))
        self.from_minute = max(0.0, float(from_minute))
        self.paused = False
        self._resume = asyncio.Event()
        self._resume.set()
        self.subscribers: set[asyncio.Queue] = set()
        self.seq = 0
        self.recent_alerts: deque = deque(maxlen=40)
        self.done = False
        self.task: asyncio.Task | None = None
        self._reset_state()

    def _reset_state(self):
        self.state = MatchState(self.meta, models=MODELS)
        self.idx = 0
        self._last_state_wall = 0.0
        self._last_players_wall = 0.0
        self._last_minute = None
        self.recent_alerts.clear()
        self.done = False

    # ---- messaging
    def envelope(self, mtype: str, payload: dict) -> dict:
        self.seq += 1
        st = self.state
        return {"v": PROTOCOL_VERSION, "type": mtype, "match_id": self.match_id, "seq": self.seq,
                "period": st.period, "clock": st.clock, "display_minute": st.display_minute,
                "match_time_s": round(st.t, 2), "wall_ts": round(time.time(), 3), "payload": payload}

    def broadcast(self, mtype: str, payload: dict):
        msg = self.envelope(mtype, payload)
        if mtype in ("alert", "win_prob_swing"):
            self.recent_alerts.append(msg)
        for q in list(self.subscribers):
            if q.full():                      # slow client: drop its oldest message rather than block the match
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            q.put_nowait(msg)

    def state_payload(self) -> dict:
        snap = self.state.snapshot(include_players=False)
        snap.pop("series", None)
        snap["session"] = self.status()
        return snap

    def status(self) -> dict:
        return {"speed": self.speed, "paused": self.paused, "done": self.done,
                "progress": round(self.idx / max(1, len(self.events)), 4), "viewers": len(self.subscribers)}

    def hello(self) -> dict:
        meta = self.meta
        pre = {k: v for k, v in (meta.get("pre_match") or {}).items() if k != "players"}
        return self.envelope("hello", {
            "protocol": PROTOCOL_VERSION,
            "match": {"match_id": self.match_id, "competition": meta.get("competition"),
                      "kickoff_utc": meta.get("kickoff_utc"), "venue": meta.get("venue"),
                      "attendance": meta.get("attendance"), "referee": meta.get("referee"),
                      "weather": meta.get("weather"), "pitch": meta.get("pitch"),
                      "coordinates": meta.get("coordinates")},
            "home": team_block(meta["home"]), "away": team_block(meta["away"]),
            "pre_match": pre,
            "state": self.state_payload(),
            "series": self.state.series,
            "recent_alerts": list(self.recent_alerts),
        })

    # ---- processing
    def process(self, ev: dict, live: bool = True):
        signals = self.state.update(ev)
        self.idx += 1
        if not live:
            return
        now = time.monotonic()
        if ev["type"] != "physical_snapshot":
            self.broadcast("event", slim_event(ev))
        for s in signals:
            self.broadcast("win_prob_swing" if s["kind"] == "win_prob_swing" else "alert", s)
        if ev["type"] in STATE_NOW or now - self._last_state_wall >= STATE_INTERVAL_S:
            self._last_state_wall = now
            self.broadcast("state", self.state_payload())
        if self.state.series and self._last_minute != self.state.series[-1]["minute"]:
            self._last_minute = self.state.series[-1]["minute"]
            self.broadcast("minute", self.state.series[-1])
        if now - self._last_players_wall >= PLAYERS_INTERVAL_S or ev["type"] in ("period_end", "match_end"):
            self._last_players_wall = now
            self.broadcast("players", {"players": self.state.snapshot()["players"]})

    def _fast_forward(self):
        """Jump to `from_minute` without streaming (synchronous, so the next hello is already up to date)."""
        while self.idx < len(self.events) and \
                self.events[self.idx]["minute"] + self.events[self.idx]["second"] / 60 < self.from_minute:
            self.process(self.events[self.idx], live=False)
        if self.idx:
            self._last_minute = self.state.series[-1]["minute"] if self.state.series else None

    async def run(self):
        loop = asyncio.get_running_loop()
        anchor_t = self.events[self.idx]["match_time_s"] if self.idx < len(self.events) else 0.0
        anchor_wall = loop.time()
        speed_seen = self.speed
        while self.idx < len(self.events):
            ev = self.events[self.idx]
            while True:
                if self.paused:
                    await self._resume.wait()
                    anchor_t, anchor_wall = ev["match_time_s"], loop.time()
                if self.speed != speed_seen:          # re-anchor so a speed change applies from now on
                    anchor_t = self.state.t if self.idx else ev["match_time_s"]
                    anchor_wall, speed_seen = loop.time(), self.speed
                lag = anchor_wall + (ev["match_time_s"] - anchor_t) / self.speed - loop.time()
                if lag <= 0:
                    break
                await asyncio.sleep(min(lag, 0.25))
            self.process(ev)
        self.done = True
        self.broadcast("state", self.state_payload())
        self.broadcast("session", self.status())

    def start(self):
        self._fast_forward()
        self.task = asyncio.create_task(self.run())

    # ---- controls
    def control(self, action: str, speed: float | None = None, from_minute: float | None = None):
        if action == "pause":
            self.paused = True
            self._resume.clear()
        elif action == "resume":
            self.paused = False
            self._resume.set()
        elif action == "speed" and speed:
            self.speed = max(0.1, float(speed))
        elif action == "restart":
            if self.task:
                self.task.cancel()
            if speed:
                self.speed = max(0.1, float(speed))
            self.from_minute = max(0.0, float(from_minute or 0.0))
            self.paused = False
            self._resume.set()
            self._reset_state()
            self.broadcast("session", {**self.status(), "restarted": True})
            for q in list(self.subscribers):
                q.put_nowait(self.hello())
            self.start()
        else:
            raise ValueError(f"unknown action {action!r}")
        self.broadcast("session", self.status())


SESSIONS: dict[str, MatchSession] = {}


def get_session(match_id: str, speed=60.0, from_minute=0.0, restart=False) -> MatchSession:
    if match_id not in CATALOGUE:
        raise KeyError(match_id)
    s = SESSIONS.get(match_id)
    if s is None or restart:
        if s and s.task:
            s.task.cancel()
        subs = s.subscribers if s else set()
        s = MatchSession(match_id, speed, from_minute)
        s.subscribers = subs
        SESSIONS[match_id] = s
        s.start()
        for q in list(subs):                  # viewers already watching get a fresh hello after a restart
            q.put_nowait(s.hello())
    return s


# --------------------------------------------------------------------------- app
app = FastAPI(title="MatchLens live", version="0.2.0")
if STATIC.exists():
    app.mount("/static", StaticFiles(directory=STATIC), name="static")


class Control(BaseModel):
    action: str
    speed: float | None = None
    from_minute: float | None = None


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/matches")
def list_matches():
    out = []
    for mid, info in CATALOGUE.items():
        s = SESSIONS.get(mid)
        out.append({k: v for k, v in info.items() if k != "path"} |
                   {"live": bool(s and not s.done), "viewers": len(s.subscribers) if s else 0})
    out.sort(key=lambda r: (r["source"] != "demo", r["competition"].get("matchday", 0), r["match_id"]))
    return out


@app.get("/api/matches/{match_id}")
def match_info(match_id: str):
    if match_id not in CATALOGUE:
        raise HTTPException(404, "unknown match")
    s = SESSIONS.get(match_id)
    return {k: v for k, v in CATALOGUE[match_id].items() if k != "path"} | {"session": s.status() if s else None}


@app.get("/api/sessions/{match_id}/state")
async def session_state(match_id: str):
    s = SESSIONS.get(match_id)
    if not s:
        raise HTTPException(404, "no session for this match – open the WebSocket first")
    return s.state.snapshot(include_players=True) | {"session": s.status()}


@app.post("/api/sessions/{match_id}/control")
async def session_control(match_id: str, c: Control):
    try:
        s = SESSIONS.get(match_id) or get_session(match_id)
        s.control(c.action, c.speed, c.from_minute)
    except KeyError:
        raise HTTPException(404, "unknown match")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return s.status()


@app.websocket("/ws/{match_id}")
async def ws_match(ws: WebSocket, match_id: str, speed: float = 60.0, from_minute: float = 0.0, restart: int = 0):
    await ws.accept()
    try:
        s = get_session(match_id, speed, from_minute, bool(restart))
    except KeyError:
        await ws.send_json({"v": PROTOCOL_VERSION, "type": "error", "payload": {"message": "unknown match"}})
        await ws.close()
        return
    q: asyncio.Queue = asyncio.Queue(maxsize=2000)
    s.subscribers.add(q)
    await ws.send_json(s.hello())

    async def pump():
        while True:
            msg = await q.get()
            await ws.send_json(msg)

    async def listen():
        while True:
            data = await ws.receive_text()
            try:
                cmd = json.loads(data)
                SESSIONS[match_id].control(cmd.get("action", ""), cmd.get("speed"), cmd.get("from_minute"))
            except (ValueError, KeyError) as e:
                await ws.send_json({"v": PROTOCOL_VERSION, "type": "error", "payload": {"message": str(e)}})

    tasks = [asyncio.create_task(pump()), asyncio.create_task(listen())]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
    except WebSocketDisconnect:
        pass
    finally:
        for t in tasks:
            t.cancel()
        SESSIONS.get(match_id, s).subscribers.discard(q)

"""Data replays ("highlights") for the big moments: goals, big chances missed, great saves and penalties.

There is no video: the replay is rebuilt from the events of the move that led to the shot (passes, carries,
dribbles, duels, pressure, the shot and the goalkeeper's action), with positions and timings, and the web app
animates it on a pitch. Only events that have already happened are used: a highlight is published shortly
after its shot, never before.
"""
from __future__ import annotations

from collections import deque

from .state import BIG_CHANCE_XG

GREAT_SAVE_XG = 0.25
WINDOW_S = 22.0              # build-up shown before the shot (match seconds)
AFTER_S = 1.5                # events after the shot that belong to the clip (save, rebound, goal)
ANIMATED = {"pass", "carry", "shot", "dribble", "clearance", "aerial_duel", "tackle", "pressure", "interception",
            "ball_recovery", "block", "dribbled_past", "goalkeeper", "sprint", "goal"}


def _kind(shot: dict) -> str | None:
    d, out = shot["details"], shot["outcome"]
    pen = shot.get("play_pattern") == "from_penalty"
    if out == "goal":
        return "penalty_goal" if pen else "goal"
    if pen:
        return "penalty_save" if out == "saved" else "penalty_miss"
    if out == "saved" and d.get("xg", 0) >= GREAT_SAVE_XG:
        return "great_save"
    if d.get("xg", 0) >= BIG_CHANCE_XG:
        return "big_chance"
    return None


def _frame(ev: dict) -> dict:
    return {"t": round(ev["match_time_s"], 2), "type": ev["type"], "side": ev.get("team_side"),
            "player_id": ev.get("player_id"), "name": ev.get("player_name"), "shirt": ev.get("shirt"),
            "loc": ev.get("location_abs"), "end": ev.get("end_location_abs"),
            "dur": ev.get("duration_s"), "outcome": ev.get("outcome"),
            "to": ev["details"].get("recipient_id") if ev["type"] == "pass" else None,
            "height": ev["details"].get("height") if ev["type"] == "pass" else None,
            "action": ev["details"].get("action") if ev["type"] == "goalkeeper" else None}


class HighlightDetector:
    def __init__(self, meta: dict):
        self.meta = meta
        self.recent: deque = deque(maxlen=400)
        self.pending: dict | None = None
        self.chance_at: dict = {}            # event_id -> live goal chance right after that touch
        self.count = 0

    def observe(self, ev: dict, score: dict, chance: dict | None = None) -> dict | None:
        """Feed every event in order; returns a finished highlight when one is complete."""
        done = None
        if chance and chance.get("t") == round(ev["match_time_s"], 2):
            self.chance_at[ev["event_id"]] = chance["p"]
        if self.pending and (ev["match_time_s"] > self.pending["shot_t"] + AFTER_S or ev["type"] == "goal"):
            if ev["type"] == "goal":
                self.recent.append(ev)
            done = self._finish(score)
        if ev["type"] in ANIMATED and ev.get("location_abs"):
            self.recent.append(ev)
        if ev["type"] == "shot" and ev.get("outcome"):
            kind = _kind(ev)
            if kind:
                if self.pending:                         # two shots in a row: close the first one now
                    done = done or self._finish(score)
                self.pending = {"shot": ev, "kind": kind, "shot_t": ev["match_time_s"]}
        return done

    def flush(self, score: dict) -> dict | None:
        return self._finish(score) if self.pending else None

    def _finish(self, score: dict) -> dict:
        p, self.pending = self.pending, None
        shot, t_shot = p["shot"], p["shot_t"]
        window = [e for e in self.recent if t_shot - WINDOW_S <= e["match_time_s"] <= t_shot + AFTER_S
                  and (e["type"] != "sprint" or e["match_time_s"] >= t_shot - 8)]
        # start at the first ball action of the attacking side's possession within the window
        poss = shot.get("possession_id")
        starts = [e["match_time_s"] for e in window
                  if e.get("possession_id") == poss and e["type"] in ("pass", "carry", "dribble", "shot")]
        t0 = max(min(starts) - 1.0, t_shot - WINDOW_S) if starts else t_shot - 6
        frames = []
        for e in window:
            if e["match_time_s"] >= t0:
                f = _frame(e)
                if e["event_id"] in self.chance_at and e.get("team_side") == shot["team_side"]:
                    f["chance"] = self.chance_at[e["event_id"]]
                frames.append(f)
        curve = [f["chance"] for f in frames if "chance" in f]
        d = shot["details"]
        self.count += 1
        side = shot["team_side"]
        return {
            "highlight_id": f"{self.meta['match_id']}-H{self.count}", "kind": p["kind"],
            "display_minute": shot["display_minute"], "match_time_s": round(t_shot, 2), "side": side,
            "team": self.meta[side]["short_name"], "player_id": shot["player_id"], "player": shot["player_name"],
            "shirt": shot.get("shirt"), "xg": d.get("xg"), "shot_speed_kmh": d.get("shot_speed_kmh"),
            "body_part": d.get("body_part"), "technique": d.get("technique"), "distance_m": d.get("distance_m"),
            "goalkeeper_id": d.get("goalkeeper_id"), "score_after": dict(score),
            "t_start": round(t0, 2), "t_shot": round(t_shot, 2), "frames": frames,
            # live goal chance of the move before the shot (start of the clip -> highest), then the shot's xG
            "chance_start": curve[0] if curve else None, "chance_peak": max(curve) if curve else None,
        }

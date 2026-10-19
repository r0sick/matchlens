"""Real-time replay of a simulated match as a live event feed.

`iter_live()` yields events paced by match time (optionally sped up), which is
what the ingest stage of the pipeline consumes. `ticker_line()` renders a
human-readable commentary-style line for terminal demos.
"""
from __future__ import annotations

import gzip
import json
import time
from pathlib import Path

QUIET = {"physical_snapshot", "sprint", "carry", "pressure", "aerial_duel", "ball_recovery",
         "dribbled_past", "possession_change", "block", "ball_out"}


def load_match(path: str | Path) -> dict:
    path = Path(path)
    if (path / "events.jsonl").exists():
        raw = (path / "events.jsonl").read_text(encoding="utf-8")
    else:
        with gzip.open(path / "events.jsonl.gz", "rt", encoding="utf-8") as f:
            raw = f.read()
    events = [json.loads(l) for l in raw.splitlines() if l]
    meta = json.loads((path / "metadata.json").read_text(encoding="utf-8"))
    return {"metadata": meta, "events": events}


def iter_live(events: list[dict], speed: float = 1.0, from_minute: float = 0.0,
              halftime_pause_s: float = 0.0, sleep=time.sleep):
    """Yield events at the pace of the match clock divided by `speed`."""
    start_t = None
    wall0 = time.monotonic()
    last_period = None
    pause = 0.0
    for ev in events:
        abs_min = ev["minute"] + ev["second"] / 60
        if abs_min < from_minute and ev["type"] not in ("match_start",):
            continue
        if last_period == 1 and ev["period"] == 2 and halftime_pause_s:
            pause += halftime_pause_s
        last_period = ev["period"]
        if start_t is None:
            start_t = ev["match_time_s"]
        due = (ev["match_time_s"] - start_t) / speed + pause
        lag = due - (time.monotonic() - wall0)
        if lag > 0:
            sleep(lag)
        yield ev


def ticker_line(ev: dict, meta: dict) -> str | None:
    t = ev["type"]
    if t in QUIET:
        return None
    d = ev["details"]
    sides = {"home": meta["home"]["abbr"], "away": meta["away"]["abbr"]}
    tm = sides.get(ev["team_side"], "")
    who = f"{ev['player_name']} ({tm})" if ev["player_name"] else tm
    sc = f"{sides['home']} {ev['score']['home']}-{ev['score']['away']} {sides['away']}"
    m = ev["display_minute"]
    if t == "pass":
        if not (d.get("key_pass") or d.get("pass_type") in ("corner", "through_ball") or d.get("cross")):
            return None
        return f"{m:>7} {who} {d['pass_type'].replace('_', ' ')} -> {d['recipient_name']} [{ev['outcome']}]"
    if t == "shot":
        return (f"{m:>7} SHOT {who}: {ev['outcome'].upper()} | xG {d['xg']:.2f} | "
                f"{d['shot_speed_kmh']:.0f} km/h | {d['distance_m']:.0f} m")
    if t == "goal":
        a = f", assist {d['assist_player_name']}" if d.get("assist_player_name") else ""
        return f"{m:>7} *** GOAL *** {who}{a}  ==> {sc}"
    if t == "card":
        return f"{m:>7} {d['card'].replace('_', ' ').upper()} CARD {who}"
    if t == "substitution":
        return f"{m:>7} SUB {tm}: {d['player_on_name']} on, {d['player_off_name']} off"
    if t in ("period_start", "period_end", "match_end", "added_time"):
        extra = f" (+{d['minutes']} min)" if t == "added_time" else ""
        return f"{m:>7} --- {t.replace('_', ' ').upper()}{extra} --- {sc}"
    if t == "foul":
        return f"{m:>7} foul by {who}" + (" (PENALTY)" if d.get("penalty") else "")
    if t == "offside":
        return f"{m:>7} offside {who}"
    if t == "goalkeeper" and d.get("action") == "save":
        return f"{m:>7} save by {who} ({d['shot_speed_kmh']:.0f} km/h shot)"
    if t in ("injury",):
        return f"{m:>7} {who} down injured"
    return None

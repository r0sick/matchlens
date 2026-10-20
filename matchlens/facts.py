"""Deterministic fact sheets: the grounding layer between the live engine and the AI newsroom.

`MomentDetector.observe(event, signals, state)` decides which moments deserve a narrative
(goals, red cards, big chances, a "state of play" read every 15 minutes, half-time and
full-time recaps) and returns a fact sheet for each one. A fact sheet holds every number
the writers are allowed to use, already rounded the way it should be quoted (probabilities
as whole percentages, xG with two decimals). The fact checker later rejects any number in
the AI's text that cannot be traced back to a fact sheet or to an MCP tool result.
"""
from __future__ import annotations

import re
from typing import Any

STATE_OF_PLAY_MINUTES = (15, 30, 60, 75)
LATE_MINUTE = 85
CAREER_GOAL_MILESTONES = (25, 50, 75, 100, 150, 200, 250, 300)


def pct(p: float | None) -> int | None:
    return None if p is None else int(round(100 * p))


def r2(x: float | None) -> float | None:
    return None if x is None else round(float(x), 2)


def other(side: str) -> str:
    return "away" if side == "home" else "home"


def control_label(chaos: float) -> str:
    return "chaotic" if chaos >= 55 else "controlled" if chaos <= 30 else "balanced"


class MomentDetector:
    """Watches the live stream and emits fact sheets for narrative-worthy moments."""

    def __init__(self, meta: dict):
        self.meta = meta
        self.pre = meta.get("pre_match") or {}
        self.pre_players = {p["player_id"]: p for p in self.pre.get("players", [])}
        self.done_sop: set[int] = set()
        self.done_recaps: set[str] = set()
        self.last_wp: dict | None = None
        self.last_momentum = 0.0
        self.key_events: list[dict] = []

    # ------------------------------------------------------------------ helpers
    def team(self, side: str) -> dict:
        t = self.meta[side]
        return {"side": side, "name": t["name"], "short_name": t["short_name"], "abbr": t["abbr"],
                "nickname": t.get("nickname"), "market": t.get("market")}

    def player_context(self, st, pid: str | None) -> dict | None:
        if not pid or pid not in st.players:
            return None
        P = st.players[pid]
        pre = self.pre_players.get(pid, {})
        season, career = pre.get("season", {}), pre.get("career", {})
        goals_now = int(P.get("goals", 0))
        out = {
            "player_id": pid, "name": P["name"], "shirt": P["shirt"], "position": P["position"],
            "team": self.meta[P["side"]]["short_name"],
            "match": {"goals": goals_now, "assists": int(P.get("assists", 0)), "shots": int(P.get("shots", 0)),
                      "xg": r2(P.get("xg", 0)), "key_passes": int(P.get("key_passes", 0)),
                      "rating": st.player_rating(P)},
        }
        if season:
            out["season_before_match"] = {k: season.get(k) for k in ("apps", "goals", "assists")}
            out["season_goals_incl_today"] = int(season.get("goals", 0)) + goals_now
        if career:
            out["career_goals_incl_today"] = int(career.get("goals", 0)) + goals_now
            out["career_apps_before_match"] = career.get("apps")
        streak = pre.get("scoring_streak_matches", 0)
        if streak:
            out["scoring_streak_before_match"] = streak
        return out

    def match_context(self, st) -> dict:
        th, ta = st.teams["home"], st.teams["away"]
        poss = st.possession()
        return {
            "minute": st.display_minute, "period": st.period,
            "score": {"home": st.score["home"], "away": st.score["away"]},
            "xg": {"home": r2(th["xg"]), "away": r2(ta["xg"])},
            "shots": {"home": int(th["shots"]), "away": int(ta["shots"])},
            "shots_on_target": {"home": int(th["shots_on_target"]), "away": int(ta["shots_on_target"])},
            "possession_pct": {"home": round(poss["total"][0]), "away": round(poss["total"][1])},
            "win_probability_pct": ({k: pct(v) for k, v in st.win_prob.items()} if st.win_prob else None),
            "momentum": round(st.momentum), "chaos": round(st.chaos), "control": control_label(st.chaos),
        }

    def standings_context(self) -> dict | None:
        s = self.pre.get("standings")
        if not s:
            return None
        keep = ("position", "points", "played", "won", "drawn", "lost", "gd", "form")
        return {side: {k: s[side][k] for k in keep if k in s[side]} for side in ("home", "away")}

    # ------------------------------------------------------------------ main entry
    def observe(self, ev: dict, signals: list[dict], st, key_events: list[dict] | None = None) -> list[dict]:
        self.key_events = key_events or []
        moments: list[dict] = []
        swing = next((s for s in signals if s["kind"] == "win_prob_swing"), None)
        for s in signals:
            if s["kind"] != "alert":
                continue
            a = s["alert"]
            if a == "goal":
                moments.append(self.goal_sheet(ev, s, swing, st))
            elif a == "card" and s["data"]["card"] in ("red", "second_yellow"):
                moments.append(self.red_card_sheet(ev, s, swing, st))
            elif a == "big_chance_missed":
                moments.append(self.big_chance_sheet(ev, s, st))
        m = st.minute
        if ev["type"] not in ("period_end", "match_end") and m in STATE_OF_PLAY_MINUTES and m not in self.done_sop:
            self.done_sop.add(m)
            moments.append(self.state_of_play_sheet(st))
        if ev["type"] == "period_end" and ev["period"] == 1 and "half_time" not in self.done_recaps:
            self.done_recaps.add("half_time")
            moments.append(self.recap_sheet(st, "half_time"))
        if ev["type"] == "match_end" and "full_time" not in self.done_recaps:
            self.done_recaps.add("full_time")
            moments.append(self.recap_sheet(st, "full_time"))
        if st.win_prob:
            self.last_wp = dict(st.win_prob)
        self.last_momentum = st.momentum
        return moments

    def _base(self, kind: str, ev: dict, st, moment_id: str) -> dict:
        return {"moment_id": moment_id, "kind": kind, "match_id": self.meta["match_id"],
                "display_minute": ev["display_minute"], "match_time_s": ev["match_time_s"],
                "home": self.team("home"), "away": self.team("away"),
                "competition": self.meta.get("competition", {}).get("name"),
                "match": self.match_context(st)}

    # ------------------------------------------------------------------ sheets
    def goal_sheet(self, ev, alert, swing, st) -> dict:
        side = alert["side"]
        d = alert["data"]
        after = d["score"]
        f, a = after[side], after[other(side)]
        before_f = f - 1
        if before_f == 0 and a == 0:
            situation = "opener"
        elif f == a:
            situation = "equaliser"
        elif f == a + 1 and before_f == a:
            situation = "go_ahead"
        elif f > a + 1:
            situation = "extends_lead"
        else:
            situation = "pulls_one_back"
        shot = next((e for e in reversed(self.key_events) if e.get("type") == "shot"), None)
        sheet = self._base("goal", ev, st, alert["event_id"])
        scorer = self.player_context(st, alert["player_id"])
        sheet["goal"] = {
            "team": self.meta[side]["short_name"], "side": side, "situation": situation,
            "late": st.minute + 1 >= LATE_MINUTE,
            "score_before": {side: before_f, other(side): a}, "score_after": after,
            "xg": r2(d.get("xg")), "chance_scored_pct": pct(d.get("xg")),
            "assist": d.get("assist"),
        }
        if ev.get("details"):
            det = ev["details"]
            sheet["goal"].update({"body_part": det.get("body_part"), "technique": det.get("technique")})
        if shot:
            sd = shot.get("details") or {}
            sheet["goal"].update({"distance_m": round(sd["distance_m"]) if sd.get("distance_m") else None,
                                  "shot_speed_kmh": round(sd["shot_speed_kmh"]) if sd.get("shot_speed_kmh") else None,
                                  "play_pattern": shot.get("play_pattern")})
        if scorer:
            sheet["scorer"] = scorer
            cg = scorer.get("career_goals_incl_today")
            if cg in CAREER_GOAL_MILESTONES:
                sheet["milestone"] = {"type": "career_goals", "value": cg}
            streak = scorer.get("scoring_streak_before_match", 0)
            if streak and scorer["match"]["goals"] == 1:
                sheet["streak"] = {"matches_in_a_row_incl_today": streak + 1}
        if scorer and scorer["match"]["goals"] >= 2:
            sheet["brace_or_more"] = scorer["match"]["goals"]
        sheet["win_probability"] = self._swing_block(swing, side)
        sheet["standings"] = self.standings_context()
        return sheet

    def red_card_sheet(self, ev, alert, swing, st) -> dict:
        side = alert["side"]
        sheet = self._base("red_card", ev, st, alert["event_id"])
        sheet["card"] = {"type": alert["data"]["card"], "team": self.meta[side]["short_name"], "side": side,
                         "players_left_on_pitch": 11 - st.reds[side]}
        sheet["player"] = self.player_context(st, alert["player_id"])
        sheet["win_probability"] = self._swing_block(swing, other(side))
        return sheet

    def big_chance_sheet(self, ev, alert, st) -> dict:
        side = alert["side"]
        sheet = self._base("big_chance", ev, st, alert["event_id"])
        xg = alert["data"]["xg"]
        sheet["chance"] = {"team": self.meta[side]["short_name"], "side": side, "xg": r2(xg),
                           "usually_scored_pct": pct(xg), "outcome": alert["data"]["outcome"]}
        sheet["player"] = self.player_context(st, alert["player_id"])
        return sheet

    def state_of_play_sheet(self, st) -> dict:
        ev = {"display_minute": st.display_minute, "match_time_s": st.t}
        sheet = self._base("state_of_play", ev, st, f"sop-{st.minute}")
        series = st.series
        now = series[-1] if series else None
        past = next((p for p in reversed(series) if p["t_min"] <= (now["t_min"] - 15 if now else 0)), series[0] if series else None)
        if now and past:
            sheet["last_15_min"] = {
                "xg": {"home": r2(now["xg"][0] - past["xg"][0]), "away": r2(now["xg"][1] - past["xg"][1])},
                "momentum_then": round(past["momentum"]), "momentum_now": round(now["momentum"]),
                "chaos_then": round(past["chaos"]), "chaos_now": round(now["chaos"]),
                "control_then": control_label(past["chaos"]), "control_now": control_label(now["chaos"]),
                "win_probability_then_pct": {k: pct(v) for k, v in past["win_prob"].items()} if past.get("win_prob") else None,
            }
        ppda = st.ppda()
        tilt = st.field_tilt()
        sheet["pressing_and_territory"] = {
            "ppda_last_15": {"home": ppda["home_last15"], "away": ppda["away_last15"]},
            "ppda_match": {"home": ppda["home"], "away": ppda["away"]},
            "field_tilt_last_10_pct": {"home": round(tilt["last10"][0]), "away": round(tilt["last10"][1])},
            "possession_last_5_pct": {"home": round(st.possession()["last5"][0]), "away": round(st.possession()["last5"][1])},
            "explanation": "PPDA = opponent passes allowed per defensive action; lower means more intense pressing.",
        }
        obs = getattr(st, "chaos_obs", {}) or {}
        if obs:
            sheet["rhythm"] = {"turnovers_per_min": round(obs.get("turnovers_pm", 0), 1),
                               "fouls_per_min": round(obs.get("fouls_pm", 0), 1),
                               "pass_failure_pct": round(100 * obs.get("pass_fail_rate", 0))}
        sheet["top_players"] = self.top_players(st, 3)
        return sheet

    def recap_sheet(self, st, which: str) -> dict:
        ev = {"display_minute": st.display_minute, "match_time_s": st.t}
        sheet = self._base(which, ev, st, which)
        goals = [e for e in self.key_events if e.get("type") == "goal"]
        sheet["goals"] = [{"minute": g.get("display_minute"), "scorer": g.get("player_name"),
                           "team": self.meta[g["team_side"]]["short_name"],
                           "assist": (g.get("details") or {}).get("assist_player_name"),
                           "xg": r2((g.get("details") or {}).get("xg"))} for g in goals]
        cards = [e for e in self.key_events if e.get("type") == "card"]
        sheet["cards"] = [{"minute": c.get("display_minute"), "player": c.get("player_name"),
                           "team": self.meta[c["team_side"]]["short_name"], "card": (c.get("details") or {}).get("card")}
                          for c in cards]
        T = {s: st.team_view(s) for s in ("home", "away")}
        sheet["team_stats"] = {s: {"xg": r2(T[s].get("xg", 0)), "shots": int(T[s].get("shots", 0)),
                                   "shots_on_target": int(T[s].get("shots_on_target", 0)),
                                   "pass_accuracy_pct": round(T[s]["pass_accuracy_pct"]) if T[s].get("pass_accuracy_pct") else None,
                                   "corners": int(T[s].get("corners", 0)),
                                   "distance_km": round(T[s].get("distance_km", 0), 1)} for s in ("home", "away")}
        sheet["ppda"] = {"home": st.ppda()["home"], "away": st.ppda()["away"]}
        sheet["top_players"] = self.top_players(st, 3)
        series = [p for p in st.series if p.get("win_prob")]
        if series:
            lo = {k: min(series, key=lambda p: p["win_prob"][k]) for k in ("home", "away")}
            hi = {k: max(series, key=lambda p: p["win_prob"][k]) for k in ("home", "away")}
            sheet["win_probability_range_pct"] = {k: {"low": pct(lo[k]["win_prob"][k]), "low_minute": lo[k]["minute"] + 1,
                                                      "high": pct(hi[k]["win_prob"][k]), "high_minute": hi[k]["minute"] + 1}
                                                  for k in ("home", "away")}
            sheet["momentum_phases"] = momentum_phases(st.series, self.meta)
        sheet["standings_before_match"] = self.standings_context()
        if which == "full_time":
            h, a = st.score["home"], st.score["away"]
            sheet["result"] = "home_win" if h > a else "away_win" if a > h else "draw"
            if sheet["standings_before_match"]:
                pts = {"home": 3 if h > a else 1 if h == a else 0, "away": 3 if a > h else 1 if h == a else 0}
                sheet["points_after_match"] = {s: sheet["standings_before_match"][s]["points"] + pts[s] for s in pts}
        return sheet

    # ------------------------------------------------------------------ shared pieces
    def _swing_block(self, swing, side) -> dict | None:
        if not swing:
            return None
        return {"for_team": self.meta[side]["short_name"],
                "before_pct": pct(swing["before"][side]), "after_pct": pct(swing["after"][side]),
                "draw_before_pct": pct(swing["before"]["draw"]), "draw_after_pct": pct(swing["after"]["draw"])}

    def top_players(self, st, n: int) -> list[dict]:
        rows = [st.player_view(pid) for pid, P in st.players.items()
                if P["passes"] + P["shots"] + P["tackles"] > 5]
        rows.sort(key=lambda r: -r["rating"])
        return [{"name": r["name"], "team": self.meta[r["side"]]["short_name"], "position": r["position"],
                 "rating": r["rating"], "goals": int(r.get("goals", 0)), "assists": int(r.get("assists", 0)),
                 "xg": r2(r.get("xg", 0)), "key_passes": int(r.get("key_passes", 0)),
                 "tackles_won": int(r.get("tackles_won", 0)), "passes_complete": int(r.get("passes_complete", 0))}
                for r in rows[:n]]


def momentum_phases(series: list[dict], meta: dict, threshold: float = 30, min_len: int = 5) -> list[dict]:
    """Spells of at least `min_len` minutes where one team's momentum stayed above `threshold`."""
    out, cur = [], None
    for p in series:
        side = "home" if p["momentum"] >= threshold else "away" if p["momentum"] <= -threshold else None
        if side and cur and cur["side"] == side:
            cur["to"] = p["minute"] + 1
        else:
            if cur and cur["to"] - cur["from"] + 1 >= min_len:
                out.append(cur)
            cur = {"side": side, "from": p["minute"] + 1, "to": p["minute"] + 1} if side else None
    if cur and cur["to"] - cur["from"] + 1 >= min_len:
        out.append(cur)
    return [{"team": meta[c["side"]]["short_name"], "from_minute": c["from"], "to_minute": c["to"]} for c in out]


# --------------------------------------------------------------------------- number grounding
NUM_RE = re.compile(r"(?<![\w.])(\d+(?:[.,]\d+)?)(?![\w])")


def numbers_in(obj: Any, out: set | None = None) -> set:
    """Every number contained in a JSON-like object (and in any text inside it)."""
    out = set() if out is None else out
    if isinstance(obj, bool) or obj is None:
        return out
    if isinstance(obj, (int, float)):
        out.add(round(float(obj), 2))
    elif isinstance(obj, str):
        for m in NUM_RE.findall(obj):
            out.add(round(float(m.replace(",", ".")), 2))
    elif isinstance(obj, dict):
        for v in obj.values():
            numbers_in(v, out)
    elif isinstance(obj, (list, tuple, set)):
        for v in obj:
            numbers_in(v, out)
    return out


def allowed_numbers(*sources: Any) -> set:
    allowed = set()
    for s in sources:
        numbers_in(s, allowed)
    extra = set()
    for v in allowed:
        if 0 < v < 1:                                  # 0.32 xG may be quoted as 32% or "1 in 3"
            extra.add(round(v * 100))
            extra.add(round(1 / v))
            extra.update({round(v * 100) - 1, round(v * 100) + 1})   # rounding differences in percentages
        if v == int(v) and 1 <= v <= 50:               # 4% may be quoted as "1 in 25"
            extra.add(round(100 / v))
    allowed |= extra
    allowed |= {float(i) for i in range(0, 12)}        # small counts (players, goals) are always fine
    allowed |= {45.0, 90.0, 100.0}
    return allowed


def unsupported_numbers(text: str, allowed: set) -> list[str]:
    bad = []
    for m in NUM_RE.findall(text or ""):
        v = round(float(m.replace(",", ".")), 2)
        if v in allowed or any(abs(v - a) <= 0.011 for a in allowed if a < 10):
            continue
        bad.append(m)
    return bad

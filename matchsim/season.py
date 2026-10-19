"""Season orchestration: fixtures, standings, cumulative player stats and pre-match context.

Pre-match context is derived from matches already simulated in the season, so
storylines such as form runs, scoring streaks and upcoming milestones are
consistent with the data rather than invented.
"""
from __future__ import annotations

import hashlib
import random
from collections import defaultdict
from datetime import datetime, timedelta

from .league import Club, Player
from .stats import box_score

GOAL_RATE = {"ST": 0.40, "W": 0.24, "AM": 0.20, "WM": 0.11, "CM": 0.08, "DM": 0.04,
             "FB": 0.03, "CB": 0.045, "GK": 0.0}
ASSIST_RATE = {"ST": 0.12, "W": 0.18, "AM": 0.20, "WM": 0.14, "CM": 0.11, "DM": 0.05,
               "FB": 0.09, "CB": 0.02, "GK": 0.003}
GOAL_MILESTONES = [25, 50, 75, 100, 150, 200, 250, 300]
APP_MILESTONES = [50, 100, 150, 200, 250, 300, 350, 400, 450, 500]


def career_baseline(p: Player) -> dict:
    """Deterministic pre-season career totals for a player (synthetic)."""
    h = int(hashlib.md5(p.player_id.encode()).hexdigest()[:8], 16)
    r = random.Random(h)
    seasons = max(0.0, p.age - 18.5 + r.uniform(-1, 1))
    apps = int(seasons * r.uniform(20, 34))
    q = 1.3 if p.is_star else 1.0
    goals = int(apps * GOAL_RATE[p.group] * q * r.uniform(0.7, 1.3))
    assists = int(apps * ASSIST_RATE[p.group] * q * r.uniform(0.7, 1.3))
    caps = int(max(0, (p.overall() - 72)) * r.uniform(0.5, 4) * seasons / 5) if p.overall() > 72 else 0
    return {"apps": apps, "goals": goals, "assists": assists, "international_caps": caps,
            "clean_sheets": int(apps * r.uniform(0.25, 0.4)) if p.group == "GK" else None}


def round_robin(clubs: list[Club], seed: int) -> list[list[tuple[Club, Club]]]:
    rng = random.Random(seed)
    teams = clubs[:]
    rng.shuffle(teams)
    n = len(teams)
    rounds = []
    arr = teams[:]
    for r in range(n - 1):
        pairs = []
        for i in range(n // 2):
            a, b = arr[i], arr[n - 1 - i]
            pairs.append((a, b) if (r + i) % 2 == 0 else (b, a))
        rounds.append(pairs)
        arr = [arr[0]] + [arr[-1]] + arr[1:-1]
    second = [[(b, a) for a, b in rd] for rd in rounds]
    return rounds + second


class SeasonState:
    def __init__(self, clubs: list[Club]):
        self.clubs = {c.club_id: c for c in clubs}
        self.table = {c.club_id: defaultdict(int) for c in clubs}
        self.form = {c.club_id: [] for c in clubs}
        self.h2h = defaultdict(list)
        self.pstats = defaultdict(lambda: defaultdict(float))
        self.last_goal_md = {}
        self.scoring_streak = defaultdict(int)
        self.career = {p.player_id: career_baseline(p) for c in clubs for p in c.squad}
        self.matchday_played = 0

    def standings(self) -> list[dict]:
        rows = []
        for cid, t in self.table.items():
            c = self.clubs[cid]
            rows.append({"team_id": cid, "name": c.name, "abbr": c.abbr, "played": t["p"], "won": t["w"],
                         "drawn": t["d"], "lost": t["l"], "gf": t["gf"], "ga": t["ga"],
                         "gd": t["gf"] - t["ga"], "points": t["pts"],
                         "form": "".join(self.form[cid][-5:])})
        rows.sort(key=lambda r: (-r["points"], -r["gd"], -r["gf"], r["name"]))
        for i, r in enumerate(rows, start=1):
            r["position"] = i
        return rows

    def player_context(self, club: Club) -> list[dict]:
        out = []
        for p in club.squad:
            s = self.pstats[p.player_id]
            car = self.career[p.player_id]
            cg = car["goals"] + int(s["goals"])
            ca = car["apps"] + int(s["apps"])
            row = {"player_id": p.player_id, "name": p.short_name,
                   "season": {"apps": int(s["apps"]), "minutes": int(s["minutes"]), "goals": int(s["goals"]),
                              "assists": int(s["assists"]), "xg": round(s["xg"], 2), "shots": int(s["shots"]),
                              "key_passes": int(s["key_passes"])},
                   "career": {"apps": ca, "goals": cg, "assists": car["assists"] + int(s["assists"]),
                              "international_caps": car["international_caps"]},
                   "scoring_streak_matches": self.scoring_streak[p.player_id]}
            watch = []
            for mlt in GOAL_MILESTONES:
                if 0 < mlt - cg <= 2:
                    watch.append({"type": "career_goals", "target": mlt, "needed": mlt - cg})
            for mlt in APP_MILESTONES:
                if mlt - ca == 1:
                    watch.append({"type": "career_apps", "target": mlt, "needed": 1})
            if watch:
                row["milestone_watch"] = watch
            out.append(row)
        return out

    def pre_match(self, home: Club, away: Club, matchday: int) -> dict:
        st = {r["team_id"]: r for r in self.standings()}
        key = tuple(sorted([home.club_id, away.club_id]))
        players = self.player_context(home) + self.player_context(away)
        return {
            "matchday": matchday,
            "standings": {"home": st[home.club_id], "away": st[away.club_id]},
            "head_to_head_this_season": self.h2h[key],
            "players": players,
            "milestones_watch": [{"player_id": r["player_id"], "name": r["name"], **w}
                                 for r in players for w in r.get("milestone_watch", [])],
            "scoring_streaks": [{"player_id": r["player_id"], "name": r["name"],
                                 "matches": r["scoring_streak_matches"]}
                                for r in players if r["scoring_streak_matches"] >= 2],
        }

    def record(self, match: dict, matchday: int):
        meta = match["metadata"]
        h, a = meta["home"]["team_id"], meta["away"]["team_id"]
        hs, as_ = meta["final_score"]["home"], meta["final_score"]["away"]
        for cid, gf, ga in ((h, hs, as_), (a, as_, hs)):
            t = self.table[cid]
            t["p"] += 1
            t["gf"] += gf
            t["ga"] += ga
            if gf > ga:
                t["w"] += 1; t["pts"] += 3; self.form[cid].append("W")
            elif gf == ga:
                t["d"] += 1; t["pts"] += 1; self.form[cid].append("D")
            else:
                t["l"] += 1; self.form[cid].append("L")
        key = tuple(sorted([h, a]))
        self.h2h[key].append({"match_id": meta["match_id"], "matchday": matchday, "home": h, "away": a,
                              "score": f"{hs}-{as_}"})
        bs = box_score(match)
        mins = match["ground_truth"]["minutes_played"]
        for pid, mm in mins.items():
            s = self.pstats[pid]
            s["apps"] += 1
            s["minutes"] += max(0, (mm["off"] or 90) - mm["on"])
        scored = set()
        for pid, row in bs["players"].items():
            s = self.pstats[pid]
            for k in ("goals", "assists", "xg", "shots", "key_passes"):
                s[k] += row.get(k, 0)
            if row.get("goals", 0) > 0:
                scored.add(pid)
        for pid in mins:
            self.scoring_streak[pid] = self.scoring_streak[pid] + 1 if pid in scored else 0


def kickoff_time(start: datetime, matchday: int, slot: int, rng: random.Random) -> str:
    base = start + timedelta(days=7 * (matchday - 1))
    times = [(5, 11, 30), (5, 14, 0), (5, 14, 0), (5, 16, 30), (6, 13, 0)]
    dow, hh, mm = times[slot % len(times)]
    d = base + timedelta(days=(dow - base.weekday()) % 7)
    return d.replace(hour=hh, minute=mm).strftime("%Y-%m-%dT%H:%M:00Z")

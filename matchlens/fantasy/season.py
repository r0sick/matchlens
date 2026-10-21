"""Fantasy season data: prices, history, fixtures, squads and the deterministic transfer signals.

Everything is "as of" a matchday: only matchdays before it are visible, so watching matchday 10
never reveals what happens in matchday 10 or later.
"""
from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

from .pricing import expected_points, form

PATH = Path(__file__).resolve().parents[2] / "data" / "season_2026-27" / "fantasy.json"
BUDGET = 100.0
SQUAD_SHAPE = {"GK": 2, "DEF": 5, "MID": 5, "FWD": 3}
MAX_PER_CLUB = 3


@lru_cache(maxsize=1)
def load() -> dict | None:
    if not PATH.exists():
        return None
    return json.loads(PATH.read_text(encoding="utf-8"))


def available() -> bool:
    return load() is not None


# --------------------------------------------------------------------------- fixtures
def difficulty_table() -> dict:
    """club_id -> difficulty 1 (easiest opponent) .. 5 (hardest), from club strength."""
    F = load()
    ratings = {cid: c["rating"] for cid, c in F["clubs"].items()}
    lo, hi = min(ratings.values()), max(ratings.values())
    return {cid: 1 + round(4 * (r - lo) / max(1e-9, hi - lo)) for cid, r in ratings.items()}


def upcoming(club_id: str, matchday: int, n: int = 3) -> list[dict]:
    """The club's next n fixtures from `matchday` on (inclusive), with difficulty."""
    F = load()
    diff = difficulty_table()
    abbr = {cid: c["abbr"] for cid, c in F["clubs"].items()}
    out = []
    for fx in sorted(F["fixtures"], key=lambda f: f["matchday"]):
        if fx["matchday"] < matchday or club_id not in (fx["home"], fx["away"]):
            continue
        home = fx["home"] == club_id
        opp = fx["away"] if home else fx["home"]
        out.append({"md": fx["matchday"], "opponent": abbr[opp], "home": home,
                    "difficulty": max(1, diff[opp] - (1 if home and diff[opp] > 1 else 0))})
        if len(out) == n:
            break
    return out


# --------------------------------------------------------------------------- players
def history(pid: str, matchday: int) -> list[dict]:
    return [r for r in load()["players"][pid]["history"] if r["md"] < matchday]


def price(pid: str, matchday: int) -> float:
    P = load()["players"][pid]
    for r in P["history"]:
        if r["md"] == matchday:
            return r["price"]
    return P["history"][-1]["price"] if P["history"] else P["start_price"]


def summary(pid: str, matchday: int) -> dict:
    """Card-level view of a player before `matchday`."""
    P = load()["players"][pid]
    h = history(pid, matchday)
    played = [r for r in h if r["minutes"] > 0]
    mins = sum(r["minutes"] for r in h)
    pts = sum(r["points"] for r in h)
    return {"player_id": pid, "name": P["name"], "full_name": P["full_name"], "club": P["club"],
            "club_id": P["club_id"], "position": P["position"], "price": price(pid, matchday),
            "points": pts, "form": round(form(h), 1) if h else 0.0, "played": len(played), "minutes": mins,
            "goals": sum(r["goals"] for r in h), "assists": sum(r["assists"] for r in h),
            "xg": round(sum(r["xg"] for r in h), 2), "xa": round(sum(r["xa"] for r in h), 2),
            "last5": [r["points"] for r in h[-5:]]}


def all_players(matchday: int) -> list[dict]:
    return [summary(pid, matchday) for pid in load()["players"]]


def projection(pid: str, matchday: int) -> float:
    """Expected points per match over the next three fixtures (simple, explainable)."""
    P = load()["players"][pid]
    h = history(pid, matchday)
    if not h:
        return round(expected_points(P["start_price"]) * 0.6, 2)
    played = [r for r in h if r["minutes"] > 0]
    per_match = sum(r["points"] for r in played) / len(played) if played else 0.0
    recent = h[-3:]
    availability = sum(min(90, r["minutes"]) for r in recent) / (90 * len(recent))
    fx = upcoming(P["club_id"], matchday)
    fdr = sum(f["difficulty"] for f in fx) / len(fx) if fx else 3.0
    base = 0.5 * form(h) + 0.5 * per_match * availability
    return round(max(0.0, base * (1.15 - 0.05 * fdr)), 2)


# --------------------------------------------------------------------------- squads
def validate(squad: list[str], matchday: int, budget: float = BUDGET) -> list[str]:
    F = load()
    issues = []
    if len(set(squad)) != len(squad):
        issues.append("A player appears twice.")
    unknown = [p for p in squad if p not in F["players"]]
    if unknown:
        return issues + [f"Unknown players: {', '.join(unknown)}."]
    counts = {k: 0 for k in SQUAD_SHAPE}
    clubs: dict[str, int] = {}
    for p in squad:
        P = F["players"][p]
        counts[P["position"]] += 1
        clubs[P["club"]] = clubs.get(P["club"], 0) + 1
    for pos, n in SQUAD_SHAPE.items():
        if counts[pos] != n:
            issues.append(f"Need {n} {pos}, have {counts[pos]}.")
    for c, n in clubs.items():
        if n > MAX_PER_CLUB:
            issues.append(f"At most {MAX_PER_CLUB} players per club ({c} has {n}).")
    cost = round(sum(price(p, matchday) for p in squad), 1)
    if cost > budget + 1e-9:
        issues.append(f"Squad costs {cost}m, budget is {budget}m.")
    return issues


def default_squad(matchday: int, focus_clubs: tuple[str, ...] = (), budget: float = BUDGET) -> list[str]:
    """A sensible ready-made squad: best projected value per position within budget and club limits.
    Players from `focus_clubs` (the clubs in the match being watched) are preferred so live points show."""
    F = load()
    rows = []
    for pid, P in F["players"].items():
        proj = projection(pid, matchday)
        bonus = 2.5 if P["club_id"] in focus_clubs else 0.0     # so live points show while watching
        rows.append((proj + bonus, pid, P["position"], P["club"], price(pid, matchday)))
    squad, spent, clubs = [], 0.0, {}
    need = dict(SQUAD_SHAPE)
    # two passes: first the starters by value per million with a reserve kept for the rest, then cheap fill
    by_value = sorted(rows, key=lambda r: -(r[0] / math.sqrt(r[4])))
    for score, pid, pos, club, cost in by_value:
        slots_left = sum(need.values())
        if need[pos] == 0 or clubs.get(club, 0) >= MAX_PER_CLUB:
            continue
        reserve = 4.3 * (slots_left - 1)
        if spent + cost + reserve > budget:
            continue
        squad.append(pid)
        spent += cost
        need[pos] -= 1
        clubs[club] = clubs.get(club, 0) + 1
        if not sum(need.values()):
            break
    return squad


# --------------------------------------------------------------------------- transfer signals
def signals(pid: str, matchday: int) -> dict:
    """Deterministic evidence for the Transfer Advisor, every number traceable to the season table."""
    P = load()["players"][pid]
    h = history(pid, matchday)
    pr = price(pid, matchday)
    last3, prev3, last6 = h[-3:], h[-6:-3], h[-6:]
    f = form(h) if h else 0.0
    exp = expected_points(pr)
    goals6, xg6 = sum(r["goals"] for r in last6), round(sum(r["xg"] for r in last6), 2)
    ast6, xa6 = sum(r["assists"] for r in last6), round(sum(r["xa"] for r in last6), 2)
    mins3, mins_prev3 = sum(r["minutes"] for r in last3), sum(r["minutes"] for r in prev3)
    starts3 = sum(1 for r in last3 if r.get("started"))
    fx = upcoming(P["club_id"], matchday)
    fdr = round(sum(x["difficulty"] for x in fx) / len(fx), 1) if fx else None
    price_3_ago = h[-3]["price"] if len(h) >= 3 else P["start_price"]
    return {
        "player_id": pid, "name": P["name"], "club": P["club"], "position": P["position"], "price": pr,
        "price_change_3": round(pr - price_3_ago, 1),
        "form_last3": round(f, 1), "expected_for_price": round(exp, 1), "form_gap": round(f - exp, 1),
        "points_last3": [r["points"] for r in last3],
        "season_points": sum(r["points"] for r in h), "matches_played": sum(1 for r in h if r["minutes"] > 0),
        "goals_last6": goals6, "xg_last6": xg6, "goals_minus_xg_last6": round(goals6 - xg6, 2),
        "assists_last6": ast6, "xa_last6": xa6,
        "minutes_last3": mins3, "minutes_prev3": mins_prev3, "starts_last3": starts3,
        "next_fixtures": fx, "fixture_difficulty_next3": fdr,
        "projected_points_per_match": projection(pid, matchday),
    }


def verdict(sig: dict) -> dict:
    """HOLD / WATCH / SELL from transparent rules; each contribution is listed as a reason."""
    reasons, score = [], 0.0
    gap = sig["form_gap"]
    c = max(-3.0, min(3.0, gap))
    score += c
    reasons.append({"factor": "form", "effect": round(c, 1),
                    "text": f"Form {sig['form_last3']} points per match vs {sig['expected_for_price']} expected at {sig['price']}m"})
    if sig["matches_played"]:
        ppm = sig["season_points"] / sig["matches_played"]
        c = round(max(-1.5, min(1.5, (ppm - sig["expected_for_price"]) / 2)), 1)
        score += c
        reasons.append({"factor": "season", "effect": c,
                        "text": f"{sig['season_points']} points in {sig['matches_played']} matches this season"})
    if sig["position"] in ("MID", "FWD") and sig["xg_last6"] >= 0.5:
        luck = sig["goals_minus_xg_last6"]
        # scoring below xG is usually bad luck (a reason to hold); scoring above it tends to cool off
        c = min(2.0, -0.8 * luck) if luck < 0 else max(-1.0, -0.4 * luck)
        score += c
        reasons.append({"factor": "finishing_luck", "effect": round(c, 1),
                        "text": f"{sig['goals_last6']} goals from {sig['xg_last6']} xG in the last 6 matchdays"})
    if sig["fixture_difficulty_next3"] is not None:
        c = round((3.0 - sig["fixture_difficulty_next3"]) * 0.8, 1)
        score += c
        reasons.append({"factor": "fixtures", "effect": c,
                        "text": "Next opponents: " + ", ".join(
                            f"{x['opponent']} ({'H' if x['home'] else 'A'}, difficulty {x['difficulty']})"
                            for x in sig["next_fixtures"])})
    m3, mp = sig["minutes_last3"], sig["minutes_prev3"]
    if m3 < 120:
        c = -3.0
    elif mp - m3 >= 90:
        c = -1.0
    else:
        c = 0.0
    score += c
    reasons.append({"factor": "minutes", "effect": c,
                    "text": f"{m3} minutes and {sig['starts_last3']} starts in the last 3 matchdays (previous 3: {mp} minutes)"})
    score = round(score, 1)
    call = "HOLD" if score >= 0.5 else "SELL" if score <= -1.5 else "WATCH"
    return {"verdict": call, "score": score, "reasons": reasons}


def replacements(pid: str, squad: list[str], matchday: int, bank: float = 0.0, n: int = 3) -> list[dict]:
    """Same position, affordable (selling price + bank), club limit respected, best projection first."""
    F = load()
    P = F["players"][pid]
    limit = round(price(pid, matchday) + bank, 1)
    clubs: dict[str, int] = {}
    for q in squad:
        if q != pid:
            clubs[F["players"][q]["club"]] = clubs.get(F["players"][q]["club"], 0) + 1
    rows = []
    for qid, Q in F["players"].items():
        if qid == pid or qid in squad or Q["position"] != P["position"]:
            continue
        if clubs.get(Q["club"], 0) >= MAX_PER_CLUB:
            continue
        cost = price(qid, matchday)
        if cost > limit:
            continue
        if sum(r["minutes"] for r in history(qid, matchday)[-3:]) < 150:
            continue
        rows.append((projection(qid, matchday), qid, cost))
    rows.sort(reverse=True)
    out = []
    for proj, qid, cost in rows[:n]:
        s = signals(qid, matchday)
        out.append({"player_id": qid, "name": s["name"], "club": s["club"], "price": cost,
                    "projected_points_per_match": proj, "form_last3": s["form_last3"],
                    "fixture_difficulty_next3": s["fixture_difficulty_next3"],
                    "bank_after": round(limit - cost, 1)})
    return out


def xg_shares(club_ids, matchday: int) -> dict:
    """player_id -> share of their club's expected goals this season (before `matchday`)."""
    F = load()
    out = {}
    for cid in club_ids:
        pids = [pid for pid, P in F["players"].items() if P["club_id"] == cid]
        xg = {pid: sum(r["xg"] for r in history(pid, matchday)) for pid in pids}
        tot = sum(xg.values())
        if tot > 1.0:
            out.update({pid: round(v / tot, 4) for pid, v in xg.items()})
    return out

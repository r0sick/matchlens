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


# --------------------------------------------------------------------------- player profile
# Attribute hexagon (EA FC-style card, Football Manager-style shape). Each category has sub-attributes:
#   kind "attr"  -> the player's scouting attribute (1-99) that drives the simulator
#   kind "stat"  -> measured in this season's matches, as a percentile against the same position (1-99)
# The hexagon draws two shapes: ratings (attributes) and this season (measured percentiles).
HEXAGON = {
    "outfield": [
        ("pac", "Pace", [("attr", "pace", "Pace"), ("stat", "top_speed", "Top speed"), ("stat", "sprints90", "Sprints per 90")]),
        ("sho", "Shooting", [("attr", "finishing", "Finishing"), ("attr", "shot_power", "Shot power"),
                             ("attr", "positioning", "Attacking positioning"), ("stat", "shots90", "Shots per 90"),
                             ("stat", "xg90", "xG per 90")]),
        ("pas", "Passing", [("attr", "passing", "Passing"), ("attr", "vision", "Vision"),
                            ("stat", "pass_acc", "Pass accuracy"), ("stat", "kp90", "Key passes per 90"),
                            ("stat", "prog90", "Progressive actions per 90")]),
        ("dri", "Dribbling", [("attr", "dribbling", "Dribbling"), ("attr", "composure", "Composure"),
                              ("stat", "drb90", "Dribbles per 90")]),
        ("def", "Defending", [("attr", "tackling", "Tackling"), ("attr", "aerial", "Heading"),
                              ("stat", "def90", "Defensive actions per 90")]),
        ("phy", "Physical", [("attr", "stamina", "Stamina"), ("stat", "dist90", "Distance per 90"),
                             ("stat", "availability", "Availability")]),
    ],
    "GK": [
        ("div", "Diving", [("attr", "keeping", "Goalkeeping"), ("stat", "saves90", "Saves per 90")]),
        ("han", "Handling", [("attr", "keeping", "Goalkeeping"), ("attr", "composure", "Composure"),
                             ("stat", "conceded90", "Goals conceded per 90 (fewer is better)")]),
        ("kic", "Kicking", [("attr", "passing", "Passing"), ("stat", "pass_acc", "Pass accuracy")]),
        ("ref", "Reflexes", [("attr", "keeping", "Goalkeeping"), ("attr", "aerial", "Aerial reach"),
                             ("stat", "save_pct", "Save percentage")]),
        ("spd", "Speed", [("attr", "pace", "Pace"), ("stat", "top_speed", "Top speed")]),
        ("pos", "Positioning", [("attr", "positioning", "Positioning"), ("stat", "clean_sheets", "Clean-sheet rate"),
                                ("stat", "availability", "Availability")]),
    ],
}
MIN_MINUTES_RADAR = 270
ABSOLUTE = {"availability"}          # shown as share of possible minutes (1-99), not a percentile: most regulars tie
INVERTED = {"conceded90"}            # lower is better


def _per90(h: list[dict]) -> dict | None:
    """Measured season values (per 90 where it makes sense); None below the minutes threshold."""
    mins = sum(r["minutes"] for r in h)
    if mins < MIN_MINUTES_RADAR:
        return None
    g = lambda k: sum(r.get(k, 0) or 0 for r in h)
    played = [r for r in h if r["minutes"] > 0]
    f = 90 / mins
    passes = g("passes")
    return {
        "top_speed": max((r.get("top_speed") or 0) for r in h), "sprints90": g("sprints") * f,
        "shots90": g("shots") * f, "xg90": g("xg") * f,
        "pass_acc": g("passes_complete") / passes if passes else 0, "kp90": g("key_passes") * f,
        "prog90": g("progressive") * f, "drb90": g("dribbles") * f, "def90": g("def_actions") * f,
        "dist90": g("distance_km") * f, "availability": mins / (90 * len(h)), "saves90": g("saves") * f,
        "conceded90": g("conceded") * f,
        "save_pct": g("saves") / (g("saves") + g("conceded")) if g("saves") + g("conceded") else 0,
        "clean_sheets": sum(1 for r in played if r["minutes"] >= 60 and r.get("conceded", 0) == 0) / max(1, len(played)),
    }


@lru_cache(maxsize=64)
def _peer_values(position: str, matchday: int) -> dict:
    """key -> sorted measured values of same-position players with enough minutes."""
    out: dict[str, list] = {}
    for pid, P in load()["players"].items():
        if P["position"] != position:
            continue
        v = _per90(history(pid, matchday))
        if v:
            for k, x in v.items():
                out.setdefault(k, []).append(x)
    return {k: sorted(v) for k, v in out.items()}


@lru_cache(maxsize=1)
def _attrs() -> dict:
    league = json.loads((PATH.parent / "league.json").read_text(encoding="utf-8"))
    return {p["player_id"]: p["attrs"] for c in league["clubs"] for p in c["squad"]}


def _pct(vals: list, x: float) -> int:
    below = sum(1 for v in vals if v < x) + 0.5 * sum(1 for v in vals if v == x)
    return max(1, min(99, round(99 * below / len(vals))))


def hexagon(pid: str, matchday: int) -> dict:
    P = load()["players"][pid]
    attrs = _attrs().get(pid, {})
    mine = _per90(history(pid, matchday))
    peers = _peer_values(P["position"], matchday)
    cats = []
    for key, label, subs in HEXAGON["GK" if P["position"] == "GK" else "outfield"]:
        rows = []
        for kind, k, sub_label in subs:
            if kind == "attr":
                rows.append({"kind": "attr", "key": k, "label": sub_label, "value": round(attrs.get(k, 0))})
            else:
                ok = mine is not None and peers.get(k)
                if not ok:
                    value = None
                elif k in ABSOLUTE:
                    value = max(1, min(99, round(99 * mine[k])))
                else:
                    value = _pct(peers[k], mine[k])
                    if k in INVERTED:
                        value = 100 - value
                rows.append({"kind": "stat", "key": k, "label": sub_label, "value": value,
                             "raw": round(mine[k], 2) if mine is not None else None})
        a = [r["value"] for r in rows if r["kind"] == "attr"]
        s = [r["value"] for r in rows if r["kind"] == "stat" and r["value"] is not None]
        rating = round(sum(a) / len(a)) if a else None
        season = round(sum(s) / len(s)) if s else None
        cats.append({"key": key, "label": label, "rating": rating, "season": season, "subs": rows})
    # strengths / weaknesses relative to the position: rating percentile among peers, blended with this season
    peer_ratings = {c["key"]: [] for c in cats}
    for q, Q in load()["players"].items():
        if Q["position"] != P["position"]:
            continue
        qa = _attrs().get(q, {})
        for key, _, subs in HEXAGON["GK" if P["position"] == "GK" else "outfield"]:
            a = [qa.get(k, 0) for kind, k, _ in subs if kind == "attr"]
            peer_ratings[key].append(sum(a) / len(a))
    for c in cats:
        sub_a = [r["value"] for r in c["subs"] if r["kind"] == "attr"]
        rp = _pct(sorted(peer_ratings[c["key"]]), sum(sub_a) / len(sub_a))
        c["score"] = round((rp + c["season"]) / 2) if c["season"] is not None else rp
    strengths = [c["key"] for c in sorted(cats, key=lambda c: -c["score"]) if c["score"] >= 70][:2]
    weaknesses = [c["key"] for c in sorted(cats, key=lambda c: c["score"]) if c["score"] <= 30][:2]
    return {"overall": P["overall"], "categories": cats, "strengths": strengths, "weaknesses": weaknesses,
            "peers": len(next(iter(peers.values()), [])), "min_minutes": MIN_MINUTES_RADAR,
            "has_season": mine is not None}


def status(h: list[dict]) -> str:
    """starter | rotation | bench | not_playing, from the last three matchdays."""
    last = h[-3:]
    if not last:
        return "unknown"
    starts = sum(1 for r in last if r.get("started"))
    mins = sum(r["minutes"] for r in last)
    if starts >= 2:
        return "starter"
    if mins >= 60:
        return "rotation"
    return "bench" if mins else "not_playing"


def profile(pid: str, matchday: int) -> dict:
    """Everything the player page shows, as of `matchday`."""
    F = load()
    P = F["players"][pid]
    h = history(pid, matchday)
    played = [r for r in h if r["minutes"] > 0]
    pr = price(pid, matchday)
    g = lambda k: sum(r.get(k, 0) or 0 for r in h)
    peers_form = sorted(form(history(q, matchday)) for q, Q in F["players"].items()
                        if Q["position"] == P["position"] and history(q, matchday))
    f = form(h) if h else 0.0
    form_pct = round(100 * sum(1 for x in peers_form if x < f) / len(peers_form)) if peers_form else None
    home = [r for r in played if r.get("home")]
    away = [r for r in played if not r.get("home")]
    avg = lambda rows: round(sum(r["points"] for r in rows) / len(rows), 1) if rows else None
    return {
        "player_id": pid, "name": P["name"], "full_name": P["full_name"], "club": P["club"], "club_id": P["club_id"],
        "club_name": F["clubs"][P["club_id"]]["name"], "position": P["position"], "role": P.get("role"),
        "group": P["group"], "shirt": P.get("shirt"), "age": P.get("age"), "nationality": P.get("nationality"),
        "foot": P.get("foot"), "height_cm": P.get("height_cm"),
        "price": pr, "start_price": P["start_price"], "price_change_3": round(pr - (h[-3]["price"] if len(h) >= 3 else P["start_price"]), 1),
        "status": status(h), "form": round(f, 1), "form_pct": form_pct,
        "points": g("points"), "matches": len(played), "starts": sum(1 for r in h if r.get("started")),
        "minutes": g("minutes"), "avg_points": avg(played), "avg_home": avg(home), "avg_away": avg(away),
        "avg_last3": round(form(h), 1) if h else None, "projected": projection(pid, matchday),
        "totals": {k: g(k) for k in ("goals", "assists", "shots", "key_passes", "saves", "yellow", "red")}
                  | {"xg": round(g("xg"), 2), "xa": round(g("xa"), 2),
                     "pass_accuracy": round(100 * g("passes_complete") / g("passes")) if g("passes") else None,
                     "def_actions": g("def_actions"), "top_speed": max([r.get("top_speed") or 0 for r in h] or [0])},
        "hexagon": hexagon(pid, matchday),
        "by_matchday": [{k: r.get(k) for k in ("md", "opponent", "home", "score", "minutes", "started", "points",
                                               "price", "goals", "assists", "rating", "reasons")} for r in h],
        "last5": [{k: r.get(k) for k in ("md", "opponent", "home", "score", "minutes", "started", "points")}
                  for r in h[-5:]][::-1],
        "next5": upcoming(P["club_id"], matchday, 5),
    }


def fixtures_grid(club_ids, matchday: int, n: int = 5) -> dict:
    return {cid: upcoming(cid, matchday, n) for cid in club_ids}

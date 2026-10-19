"""Box-score aggregation from an event list (used for validation and season context)."""
from __future__ import annotations

from collections import defaultdict


def box_score(match: dict) -> dict:
    meta, events = match["metadata"], match["events"]
    sides = {meta["home"]["team_id"]: "home", meta["away"]["team_id"]: "away"}
    T = {s: defaultdict(float) for s in ("home", "away")}
    P = defaultdict(lambda: defaultdict(float))
    names = {}
    for blk in ("home", "away"):
        for p in meta[blk]["starting_xi"] + meta[blk]["bench"]:
            names[p["player_id"]] = (p["short_name"], blk)

    last_phys = {}
    for e in events:
        tid = e["team_id"]
        if tid is None:
            continue
        s = sides[tid]
        t = e["type"]
        pid = e["player_id"]
        d = e["details"]
        if t == "pass":
            T[s]["passes"] += 1
            P[pid]["passes"] += 1
            if e["outcome"] == "complete":
                T[s]["passes_complete"] += 1
                P[pid]["passes_complete"] += 1
            if d.get("cross"):
                T[s]["crosses"] += 1
            if d.get("pass_type") == "corner":
                T[s]["corners"] += 1
            if d.get("key_pass"):
                P[pid]["key_passes"] += 1
            if d.get("assist"):
                P[pid]["assists"] += 1
        elif t == "shot":
            T[s]["shots"] += 1
            T[s]["xg"] += d["xg"]
            P[pid]["shots"] += 1
            P[pid]["xg"] += d["xg"]
            if d["on_target"]:
                T[s]["shots_on_target"] += 1
            if e["outcome"] == "blocked":
                T[s]["shots_blocked"] += 1
            if d.get("big_chance"):
                T[s]["big_chances"] += 1
        elif t == "goal":
            T[s]["goals"] += 1
            P[pid]["goals"] += 1
        elif t == "foul":
            T[s]["fouls"] += 1
        elif t == "card":
            T[s]["yellow" if d["card"] == "yellow" else "red"] += 1
            if d["card"] == "second_yellow":
                T[s]["yellow"] += 1
        elif t == "offside":
            T[s]["offsides"] += 1
        elif t == "tackle":
            T[s]["tackles"] += 1
            P[pid]["tackles"] += 1
            if e["outcome"] == "won":
                T[s]["tackles_won"] += 1
        elif t == "interception":
            T[s]["interceptions"] += 1
            P[pid]["interceptions"] += 1
        elif t == "pressure":
            T[s]["pressures"] += 1
            P[pid]["pressures"] += 1
        elif t == "dribble":
            T[s]["dribbles"] += 1
            if e["outcome"] == "complete":
                T[s]["dribbles_complete"] += 1
        elif t == "goalkeeper" and d.get("action") == "save":
            T[s]["saves"] += 1
        elif t == "sprint":
            T[s]["sprints"] += 1
        elif t == "substitution":
            T[s]["subs"] += 1
        elif t == "physical_snapshot":
            for row in d["players"]:
                last_phys[row["player_id"]] = row
    for pid, row in last_phys.items():
        P[pid]["distance_m"] = row["distance_m"]
        P[pid]["top_speed_kmh"] = row["top_speed_kmh"]
        P[pid]["sprints"] = row["sprints"]
        T[names[pid][1]]["distance_km"] += row["distance_m"] / 1000 if pid in names else 0

    gt = match.get("ground_truth", {}).get("possession_seconds")
    if gt:
        tot = gt["home"] + gt["away"]
        T["home"]["possession_pct"] = 100 * gt["home"] / tot
        T["away"]["possession_pct"] = 100 * gt["away"] / tot
    for s in T:
        T[s]["pass_accuracy_pct"] = 100 * T[s]["passes_complete"] / max(1, T[s]["passes"])
        T[s] = {k: round(v, 2) for k, v in T[s].items()}
    players = {}
    for pid, row in P.items():
        if pid is None or pid not in names:
            continue
        r = {k: round(v, 3) for k, v in row.items()}
        r["name"], r["side"] = names[pid]
        players[pid] = r
    return {"match_id": meta["match_id"], "teams": T, "players": players,
            "score": meta["final_score"]}

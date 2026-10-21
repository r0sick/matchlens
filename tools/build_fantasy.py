"""Build the Fantasy season table: points with reasons for every player in every played match,
plus prices that move with form.

    python tools/build_fantasy.py            ->  data/season_2026-27/fantasy.json

Each match is replayed through the live engine (MatchState + FantasyScorer), so season points are
computed by exactly the same code that scores a match live.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from matchsim.replay import load_match                      # noqa: E402
from matchlens.fantasy.pricing import base_price, next_price  # noqa: E402
from matchlens.fantasy.scoring import FantasyScorer, position_of  # noqa: E402
from matchlens.models import load_models                    # noqa: E402
from matchlens.state import MatchState                      # noqa: E402

SEASON = ROOT / "data" / "season_2026-27"


def main():
    league = json.loads((SEASON / "league.json").read_text())
    fixtures = json.loads((SEASON / "fixtures.json").read_text())
    clubs = {c["club_id"]: c for c in league["clubs"]}
    models = load_models()

    players = {}
    for c in league["clubs"]:
        for p in c["squad"]:
            pos = position_of(p["group"])
            players[p["player_id"]] = {
                "player_id": p["player_id"], "name": p["short_name"], "full_name": p["name"],
                "club_id": c["club_id"], "club": c["abbr"], "position": pos, "group": p["group"],
                "overall": p["overall"], "is_star": p["is_star"], "start_price": base_price(p["overall"], pos),
                "history": []}

    rows = defaultdict(dict)        # pid -> md -> row
    for fx in sorted(fixtures, key=lambda f: (f["matchday"], f["match_id"])):
        m = load_match(SEASON / "matches" / fx["match_id"])
        st = MatchState(m["metadata"], models)
        fs = FantasyScorer(st)
        for ev in m["events"]:
            st.update(ev)
            fs.update(ev)
        table = fs.table()
        for side in ("home", "away"):
            meta = m["metadata"][side]
            opp = m["metadata"]["away" if side == "home" else "home"]
            for p in meta["starting_xi"] + meta["bench"]:
                pid = p["player_id"]
                Q = st.players[pid]
                r = table.get(pid)
                rows[pid][fx["matchday"]] = {
                    "md": fx["matchday"], "match_id": fx["match_id"], "opponent": opp["abbr"],
                    "home": side == "home", "score": fx["score"] if side == "home" else "-".join(fx["score"].split("-")[::-1]),
                    "started": p in meta["starting_xi"], "minutes": r["minutes"] if r else 0,
                    "points": r["points"] if r else 0,
                    "reasons": {x["code"]: x["pts"] for x in r["reasons"]} if r else {},
                    "goals": int(Q["goals"]), "assists": int(Q["assists"]),
                    "xg": round(Q["xg"], 2), "xa": round(Q["xa"], 2),
                    "rating": r["rating"] if r else None}

    last_md = max(f["matchday"] for f in fixtures)
    for pid, P in players.items():
        price = P["start_price"]
        hist = []
        for md in range(1, last_md + 1):
            row = rows[pid].get(md) or {"md": md, "match_id": None, "minutes": 0, "points": 0, "reasons": {},
                                        "goals": 0, "assists": 0, "xg": 0.0, "xa": 0.0, "rating": None}
            row["price"] = price                       # price before this matchday
            hist.append(row)
            price = next_price(price, P["start_price"], hist)
        P["history"] = hist

    out = {"season": "2026/27", "competition": "Aurora League", "last_matchday": last_md,
           "rules": "see matchlens/fantasy/scoring.py",
           "clubs": {cid: {"club_id": cid, "name": c["name"], "abbr": c["abbr"], "rating": c["rating"]}
                     for cid, c in clubs.items()},
           "fixtures": fixtures, "players": players}
    path = SEASON / "fantasy.json"
    path.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False))
    print(f"wrote {path.relative_to(ROOT)}: {len(players)} players, {last_md} matchdays, "
          f"{path.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()

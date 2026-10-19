"""MatchSim CLI.

  python -m matchsim league   --out data
  python -m matchsim match    --home THR --away BWA --seed 42 --out data/matches
  python -m matchsim season   --out data/season --matchdays 18
  python -m matchsim replay   data/matches/M000042 --speed 30 --format ticker
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import random
import sys
from datetime import datetime
from pathlib import Path

from .engine import MatchEngine
from .league import build_league, club_by_id
from .replay import iter_live, load_match, ticker_line
from .season import SeasonState, kickoff_time, round_robin
from .stats import box_score

FLAT = ["seq", "event_id", "match_id", "period", "clock", "minute", "second", "display_minute",
        "match_time_s", "type", "team_id", "team_side", "player_id", "player_name", "shirt",
        "possession_id", "possession_team_id", "play_pattern", "outcome", "duration_s"]


def write_match(match: dict, out: Path, with_csv: bool = False, gz: bool = False) -> Path:
    d = out / match["metadata"]["match_id"]
    d.mkdir(parents=True, exist_ok=True)
    opener = (lambda p: gzip.open(str(p) + ".gz", "wt", encoding="utf-8")) if gz else \
        (lambda p: open(p, "w", encoding="utf-8"))
    with opener(d / "events.jsonl") as f:
        for e in match["events"]:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    (d / "metadata.json").write_text(json.dumps(match["metadata"], ensure_ascii=False, indent=2), encoding="utf-8")
    (d / "ground_truth.json").write_text(json.dumps(match["ground_truth"], indent=1), encoding="utf-8")
    (d / "box_score.json").write_text(json.dumps(box_score(match), ensure_ascii=False, indent=1), encoding="utf-8")
    if with_csv:
        with open(d / "events.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(FLAT + ["x", "y", "end_x", "end_y", "x_abs", "y_abs", "home_score", "away_score", "details"])
            for e in match["events"]:
                loc, end, ab = e["location"] or [None, None], e["end_location"] or [None, None], e["location_abs"] or [None, None]
                w.writerow([e[k] for k in FLAT] + [loc[0], loc[1], end[0], end[1], ab[0], ab[1],
                                                   e["score"]["home"], e["score"]["away"],
                                                   json.dumps(e["details"], ensure_ascii=False)])
    return d


def cmd_league(a):
    clubs = build_league(a.league_seed)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "league.json").write_text(json.dumps({"league": "Aurora League", "season": "2026/27", "synthetic": True,
                                                 "clubs": [c.to_dict() for c in clubs]}, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    for c in clubs:
        print(f"{c.abbr}  {c.name:<22} {c.formation:<8} rating {c.rating}  market={c.country_market}")
    print(f"wrote {out / 'league.json'}")


def cmd_match(a):
    clubs = build_league(a.league_seed)
    home, away = club_by_id(clubs, a.home), club_by_id(clubs, a.away)
    st = SeasonState(clubs)
    eng = MatchEngine(home, away, seed=a.seed, match_id=a.match_id or f"M{a.seed:06d}",
                      kickoff_utc=a.kickoff, pre_match=st.pre_match(home, away, 1))
    m = eng.run()
    d = write_match(m, Path(a.out), a.csv)
    sc = m["metadata"]["final_score"]
    print(f"{home.name} {sc['home']}-{sc['away']} {away.name}  |  {len(m['events'])} events  ->  {d}")


def cmd_season(a):
    clubs = build_league(a.league_seed)
    out = Path(a.out)
    (out / "matches").mkdir(parents=True, exist_ok=True)
    rounds = round_robin(clubs, a.seed)[: a.matchdays]
    st = SeasonState(clubs)
    rng = random.Random(a.seed)
    start = datetime(2026, 8, 15)
    fixtures = []
    for md, pairs in enumerate(rounds, start=1):
        for slot, (h, w) in enumerate(pairs):
            mid = f"AUR26-MD{md:02d}-{h.abbr}-{w.abbr}"
            ko = kickoff_time(start, md, slot, rng)
            eng = MatchEngine(h, w, seed=a.seed * 1000 + md * 10 + slot, match_id=mid, kickoff_utc=ko,
                              competition={"name": "Aurora League", "season": "2026/27", "matchday": md},
                              pre_match=st.pre_match(h, w, md))
            m = eng.run()
            write_match(m, out / "matches", a.csv, gz=not a.no_gzip)
            st.record(m, md)
            sc = m["metadata"]["final_score"]
            fixtures.append({"match_id": mid, "matchday": md, "kickoff_utc": ko, "home": h.club_id,
                             "away": w.club_id, "score": f"{sc['home']}-{sc['away']}"})
        top = st.standings()[0]
        print(f"MD{md:02d} done  | leader {top['name']} {top['points']} pts", file=sys.stderr)
    (out / "fixtures.json").write_text(json.dumps(fixtures, indent=1), encoding="utf-8")
    (out / "standings.json").write_text(json.dumps(st.standings(), ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "league.json").write_text(json.dumps({"clubs": [c.to_dict() for c in clubs]}, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    print(f"{'#':>2} {'club':<22}{'P':>3}{'W':>3}{'D':>3}{'L':>3}{'GF':>4}{'GA':>4}{'Pts':>5}  form")
    for r in st.standings():
        print(f"{r['position']:>2} {r['name']:<22}{r['played']:>3}{r['won']:>3}{r['drawn']:>3}{r['lost']:>3}"
              f"{r['gf']:>4}{r['ga']:>4}{r['points']:>5}  {r['form']}")


def cmd_replay(a):
    m = load_match(a.path)
    meta = m["metadata"]
    if a.format == "ticker":
        print(f"{meta['home']['name']} vs {meta['away']['name']} — {meta['venue']['stadium']}, "
              f"ref {meta['referee']['name']}, {meta['weather']['condition']}")
    try:
        for ev in iter_live(m["events"], speed=a.speed, from_minute=a.from_minute):
            if a.format == "jsonl":
                print(json.dumps(ev, ensure_ascii=False), flush=True)
            else:
                line = ticker_line(ev, meta)
                if line:
                    print(line, flush=True)
    except (KeyboardInterrupt, BrokenPipeError):
        pass


def main(argv=None):
    ap = argparse.ArgumentParser(prog="matchsim", description="Synthetic football event generator")
    ap.add_argument("--league-seed", type=int, default=2026)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("league", help="write league.json (clubs + squads)")
    s.add_argument("--out", default="data")
    s.set_defaults(fn=cmd_league)

    s = sub.add_parser("match", help="simulate one match")
    s.add_argument("--home", required=True, help="club id, abbreviation or short name")
    s.add_argument("--away", required=True)
    s.add_argument("--seed", type=int, default=42)
    s.add_argument("--match-id")
    s.add_argument("--kickoff", default="2026-10-24T14:00:00Z")
    s.add_argument("--out", default="data/matches")
    s.add_argument("--csv", action="store_true", help="also write a flat events.csv")
    s.set_defaults(fn=cmd_match)

    s = sub.add_parser("season", help="simulate a double round-robin season")
    s.add_argument("--seed", type=int, default=2026)
    s.add_argument("--matchdays", type=int, default=18)
    s.add_argument("--out", default="data/season_2026-27")
    s.add_argument("--csv", action="store_true")
    s.add_argument("--no-gzip", action="store_true", help="write plain events.jsonl instead of .jsonl.gz")
    s.set_defaults(fn=cmd_season)

    s = sub.add_parser("replay", help="stream a match in (accelerated) real time")
    s.add_argument("path", help="match folder containing events.jsonl + metadata.json")
    s.add_argument("--speed", type=float, default=30.0, help="1 = real time, 60 = one match minute per second")
    s.add_argument("--from-minute", type=float, default=0.0)
    s.add_argument("--format", choices=["jsonl", "ticker"], default="ticker")
    s.set_defaults(fn=cmd_replay)

    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()

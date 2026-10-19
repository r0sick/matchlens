"""Simulate N matches and compare per-team averages to typical top-flight values."""
import argparse, statistics as S, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from matchsim.league import build_league
from matchsim.engine import MatchEngine
from matchsim.stats import box_score

# Approximate per-team, per-match reference values for a modern top-flight league
REF = {"goals": 1.4, "xg": 1.4, "shots": 12.5, "shots_on_target": 4.3, "passes": 470,
       "pass_accuracy_pct": 81, "corners": 5.0, "crosses": 16, "fouls": 10.5, "yellow": 1.9,
       "offsides": 1.8, "tackles": 17, "interceptions": 9, "dribbles": 9, "saves": 3.0,
       "sprints": 120, "distance_km": 110, "pressures": 150}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("-n", type=int, default=100); a = ap.parse_args()
    clubs = build_league()
    rows, pens, reds, bip, hw, dr = [], 0, 0, [], 0, 0
    for s in range(a.n):
        h, w = clubs[s % 10], clubs[(s * 7 + 3) % 10]
        if h is w: w = clubs[(s + 1) % 10]
        m = MatchEngine(h, w, seed=1000 + s).run()
        b = box_score(m)
        rows += [b["teams"]["home"], b["teams"]["away"]]
        pens += sum(1 for e in m["events"] if e["type"] == "shot" and e["details"]["technique"] == "penalty")
        reds += sum(1 for e in m["events"] if e["type"] == "card" and e["details"]["card"] != "yellow")
        g = m["ground_truth"]["possession_seconds"]; bip.append((g["home"] + g["away"]) / 60)
        sc = m["metadata"]["final_score"]; hw += sc["home"] > sc["away"]; dr += sc["home"] == sc["away"]
    print(f"{'metric':<20}{'sim':>9}{'ref':>9}")
    for k, ref in REF.items():
        v = S.mean(r.get(k, 0) for r in rows)
        flag = "" if 0.75 * ref <= v <= 1.25 * ref else "  <-- off"
        print(f"{k:<20}{v:>9.2f}{ref:>9}{flag}")
    print(f"penalties/match {pens / a.n:.2f}  reds/match {reds / a.n:.2f}  ball-in-play {S.mean(bip):.1f} min")
    print(f"home win {hw / a.n:.0%}  draw {dr / a.n:.0%}  away win {1 - (hw + dr) / a.n:.0%}")

if __name__ == "__main__":
    main()

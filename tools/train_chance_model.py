"""Fit the live goal-chance model (probability that the team on the ball scores in this possession).

    python tools/train_chance_model.py --matches 1200 --workers 2

Simulates fresh matches (seeds from 800000, never overlapping demo, season or the other training data),
labels every touch of the team in possession with "did this possession end in a goal", fits a logistic
model on 80% of matches and reports log loss, AUC and calibration on the other 20%.
Writes matchlens/model_files/goal_chance.json and adds a "goal_chance" section to training_report.json.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, roc_auc_score
from sklearn.preprocessing import StandardScaler

from matchsim.engine import MatchEngine
from matchsim.league import build_league
from matchlens.chance import BALL_EVENTS, MODEL_FILE, features

SEED0 = 800_000
TERMS = None


def simulate(i):
    clubs = build_league()
    rng = random.Random(SEED0 + i)
    h, a = rng.sample(clubs, 2)
    m = MatchEngine(h, a, seed=SEED0 + i, match_id=f"C{i:06d}").run()
    ev = m["events"]
    scored = {e["possession_id"] for e in ev if e["type"] == "goal" and not e["details"].get("own_goal")
              and e.get("team_id") == e.get("possession_team_id")}
    rows, poss, ctx = [], None, {}
    for e in ev:
        pid = e.get("possession_id")
        if pid is not None and pid != poss:
            poss, ctx = pid, {"actions": 0, "start": e["match_time_s"], "pattern": e.get("play_pattern")}
        if e["type"] not in BALL_EVENTS or e.get("team_id") != e.get("possession_team_id"):
            continue
        ctx["actions"] += 1
        ctx["seconds"] = e["match_time_s"] - ctx["start"]
        f = features(e, ctx)
        if f is not None:
            rows.append((i, f, int(pid in scored)))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--matches", type=int, default=1200)
    ap.add_argument("--workers", type=int, default=2)
    a = ap.parse_args()
    t0 = time.time()
    with Pool(a.workers) as pool:
        res = pool.map(simulate, range(a.matches), chunksize=10)
    rows = [r for rs in res for r in rs]
    terms = list(rows[0][1].keys())
    X = np.array([[f[k] for k in terms] for _, f, _ in rows])
    y = np.array([lab for *_, lab in rows])
    mid = np.array([m for m, *_ in rows])
    test = mid % 5 == 0
    sc = StandardScaler().fit(X[~test])
    lr = LogisticRegression(C=1.0, max_iter=2000).fit(sc.transform(X[~test]), y[~test])
    p = lr.predict_proba(sc.transform(X[test]))[:, 1]
    base = np.full_like(p, y[~test].mean())
    bins = np.quantile(p, np.linspace(0, 1, 11))
    cal = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        k = (p >= lo) & (p <= hi)
        if k.sum():
            cal.append({"pred": round(float(p[k].mean()), 4), "obs": round(float(y[test][k].mean()), 4), "n": int(k.sum())})
    report = {"matches": a.matches, "touches": int(len(y)), "goal_rate": round(float(y.mean()), 4),
              "log_loss": round(float(log_loss(y[test], p)), 4), "log_loss_base_rate": round(float(log_loss(y[test], base)), 4),
              "auc": round(float(roc_auc_score(y[test], p)), 3), "calibration": cal,
              "coefficients": {t: round(float(c), 3) for t, c in zip(terms, lr.coef_[0])}}
    spec = {"terms": terms, "coef": [float(c) for c in lr.coef_[0]], "intercept": float(lr.intercept_[0]),
            "scaler_mean": [float(v) for v in sc.mean_], "scaler_scale": [float(v) for v in sc.scale_],
            "trained_on": f"{a.matches} simulated matches (seeds {SEED0}+)", "report": {k: report[k] for k in ("auc", "log_loss", "log_loss_base_rate")}}
    MODEL_FILE.write_text(json.dumps(spec, indent=1))
    rp = MODEL_FILE.parent / "training_report.json"
    full = json.loads(rp.read_text()) if rp.exists() else {}
    full["goal_chance"] = report
    rp.write_text(json.dumps(full, indent=1))
    print(json.dumps({k: v for k, v in report.items() if k != "calibration"}, indent=1))
    print("calibration:", cal)
    print(f"done in {time.time() - t0:.0f}s -> {MODEL_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

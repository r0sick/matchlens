"""Simulate training matches and fit the live models.

    python tools/train_models.py --matches 3000 --workers 4

Outputs JSON coefficient files into matchlens/model_files/ plus an evaluation
report (log loss, Brier score, calibration) against a held-out set of matches.
Training seeds start at 500000, so they never overlap the demo or season data.
Requires numpy + scikit-learn (training only; the live app does not need them).
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, roc_auc_score
from sklearn.preprocessing import StandardScaler

from matchsim.engine import MatchEngine
from matchsim.league import build_league
from matchlens.models import PASS_FEATURES, pass_features, expand, MODEL_DIR
from matchlens.state import MatchState

WIN_TERMS = ["gd", "gd_late", "gd_late2", "abs_gd_late", "xg_diff", "xg_diff_15", "shots_diff_15",
             "red_diff", "strength", "strength_raw", "momentum", "tilt", "poss", "time_left",
             "time_left2", "level_late", "goals_total"]
RAW = ["minute", "time_left", "goal_diff", "home_goals", "away_goals", "xg_diff", "xg_diff_15",
       "shots_diff_15", "red_diff", "strength_diff", "momentum", "tilt_10", "poss_5"]
SEED0 = 500_000


def simulate(i):
    clubs = build_league()
    rng = random.Random(SEED0 + i)
    h, a = rng.sample(clubs, 2)
    m = MatchEngine(h, a, seed=SEED0 + i, match_id=f"T{i:06d}").run()
    st = MatchState(m["metadata"])
    goals = [(e["match_time_s"], e["team_side"]) for e in m["events"] if e["type"] == "goal"]
    final = m["metadata"]["final_score"]
    result = "home" if final["home"] > final["away"] else "away" if final["away"] > final["home"] else "draw"
    snaps, passes, gt_rows = [], [], []
    last_min = -1
    gt = {(r["period"], r["minute"]): r for r in m["ground_truth"]["timeline"]}
    for ev in m["events"]:
        st.update(ev)
        if ev["type"] == "pass" and ev["outcome"] != "offside" and ev["details"].get("pass_type") != "kick_off" \
                and rng.random() < 0.25:
            f = pass_features(ev)
            passes.append([f[k] for k in PASS_FEATURES] + [int(ev["outcome"] == "complete"),
                                                           ev["details"].get("provider_completion_prob", -1)])
        if ev["minute"] != last_min and ev["type"] not in ("match_end", "period_end"):
            last_min = ev["minute"]
            f = st.features()
            t = ev["match_time_s"]
            nxt = next((s for gt_t, s in goals if gt_t > t), "none")
            snaps.append({"match": i, "f": f, "result": result, "next_goal": nxt})
            g = gt.get((ev["period"], ev["minute"] + 1))
            if g:
                o = st.chaos_obs
                gt_rows.append((st.momentum, g["momentum_home"], st.chaos, g["chaos"],
                                o["turnovers_pm"], o["fouls_pm"], o["pass_fail_rate"], i))
    return snaps, passes, gt_rows


def calibration(p, y, bins=10):
    edges = np.linspace(0, 1, bins + 1)
    out = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (p >= lo) & (p < hi)
        if m.sum() > 50:
            out.append((round(float(p[m].mean()), 3), round(float(y[m].mean()), 3), int(m.sum())))
    return out


def export_logit(model, scaler, classes, terms):
    order = list(model.classes_)
    return {"type": "multinomial_logit", "classes": classes, "terms": terms,
            "coef": {c: [round(float(v), 6) for v in model.coef_[order.index(c)]] for c in classes},
            "intercept": {c: round(float(model.intercept_[order.index(c)]), 6) for c in classes},
            "scaler_mean": [round(float(v), 6) for v in scaler.mean_],
            "scaler_scale": [round(float(v), 6) for v in scaler.scale_]}


def mlogloss(Y, P, classes):
    """sklearn's log_loss expects columns in sorted label order; reorder before scoring."""
    order = sorted(classes)
    return log_loss(Y, P[:, [classes.index(c) for c in order]], labels=order)


def multiclass_brier(P, Y, classes):
    onehot = np.stack([(Y == c).astype(float) for c in classes], axis=1)
    return float(((P - onehot) ** 2).sum(axis=1).mean())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--matches", type=int, default=3000)
    ap.add_argument("--workers", type=int, default=os.cpu_count() or 2)
    ap.add_argument("--out", default=str(MODEL_DIR))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    with Pool(a.workers) as pool:
        res = pool.map(simulate, range(a.matches), chunksize=20)
    print(f"simulated {a.matches} matches in {time.time() - t0:.0f}s")
    snaps = [s for r in res for s in r[0]]
    passes = np.array([p for r in res for p in r[1]], dtype=float)
    gtr = np.array([g for r in res for g in r[2]], dtype=float)
    report = {"matches": a.matches, "snapshots": len(snaps), "passes": int(len(passes))}

    # ---------------- pass difficulty
    X, y, prov = passes[:, :len(PASS_FEATURES)], passes[:, len(PASS_FEATURES)], passes[:, -1]
    n = len(X)
    idx = np.random.default_rng(0).permutation(n)
    tr, te = idx[: int(0.8 * n)], idx[int(0.8 * n):]
    pm = LogisticRegression(max_iter=2000, C=1.0).fit(X[tr], y[tr])
    pp = pm.predict_proba(X[te])[:, 1]
    report["pass_model"] = {"log_loss": round(log_loss(y[te], pp), 4), "auc": round(roc_auc_score(y[te], pp), 4),
                            "base_rate": round(float(y.mean()), 4),
                            "corr_with_engine_truth": round(float(np.corrcoef(pp, prov[te])[0, 1]), 3),
                            "calibration": calibration(pp, y[te])}
    (out / "pass_difficulty.json").write_text(json.dumps({
        "type": "logit", "features": PASS_FEATURES,
        "coef": {k: round(float(v), 6) for k, v in zip(PASS_FEATURES, pm.coef_[0])},
        "intercept": round(float(pm.intercept_[0]), 6),
        "feature_means": {k: round(float(v), 6) for k, v in zip(PASS_FEATURES, X.mean(axis=0))}}, indent=1))

    # ---------------- win probability & next goal (split by match)
    match_ids = np.array([s["match"] for s in snaps])
    test_mask = match_ids % 5 == 0
    XE = np.array([expand(s["f"], WIN_TERMS) for s in snaps])
    XR = np.array([[s["f"][k] for k in RAW] for s in snaps])
    for target, classes, fname in (("result", ["home", "draw", "away"], "win_prob.json"),
                                   ("next_goal", ["home", "none", "away"], "next_goal.json")):
        Y = np.array([s[target] for s in snaps])
        sc = StandardScaler().fit(XE[~test_mask])
        lr = LogisticRegression(max_iter=3000, C=1.0).fit(sc.transform(XE[~test_mask]), Y[~test_mask])
        P_lr = lr.predict_proba(sc.transform(XE[test_mask]))
        P_lr = P_lr[:, [list(lr.classes_).index(c) for c in classes]]
        gb = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_leaf_nodes=31).fit(
            XR[~test_mask], Y[~test_mask])
        P_gb = gb.predict_proba(XR[test_mask])[:, [list(gb.classes_).index(c) for c in classes]]
        # baseline: same model family using only the scoreline and the clock
        base_cols = [WIN_TERMS.index(t) for t in ("gd", "gd_late", "gd_late2", "abs_gd_late", "time_left",
                                                   "time_left2", "level_late", "goals_total")]
        sb = StandardScaler().fit(XE[~test_mask][:, base_cols])
        lb = LogisticRegression(max_iter=3000).fit(sb.transform(XE[~test_mask][:, base_cols]), Y[~test_mask])
        P_b = lb.predict_proba(sb.transform(XE[test_mask][:, base_cols]))[:, [list(lb.classes_).index(c) for c in classes]]
        r = {"scoreline_only_log_loss": round(mlogloss(Y[test_mask], P_b, classes), 4),"logit_log_loss": round(mlogloss(Y[test_mask], P_lr, classes), 4),
             "gbm_log_loss": round(mlogloss(Y[test_mask], P_gb, classes), 4),
             "logit_brier": round(multiclass_brier(P_lr, Y[test_mask], classes), 4),
             "gbm_brier": round(multiclass_brier(P_gb, Y[test_mask], classes), 4),
             "prior_log_loss": round(mlogloss(Y[test_mask], np.tile([(Y[~test_mask] == c).mean() for c in classes],
                                                                   (test_mask.sum(), 1)), classes), 4),
             "calibration_" + classes[0]: calibration(P_lr[:, 0], (Y[test_mask] == classes[0]).astype(float))}
        # accuracy by phase for the result model
        if target == "result":
            mins = XR[test_mask, 0]
            for lo, hi in ((0, 15), (30, 45), (60, 75), (80, 100)):
                m = (mins >= lo) & (mins < hi)
                r[f"log_loss_min_{lo}_{hi}"] = round(mlogloss(Y[test_mask][m], P_lr[m], classes), 4)
        report[fname.replace(".json", "")] = r
        (out / fname).write_text(json.dumps(export_logit(lr, sc, classes, WIN_TERMS), indent=1))

    # ---------------- chaos index: observable rhythm -> latent chaos (fit on 80%, test on 20% of matches)
    from sklearn.linear_model import LinearRegression
    obs, lat, mid = gtr[:, 4:7], gtr[:, 3], gtr[:, 7].astype(int)
    trm = mid % 5 != 0
    ch = LinearRegression().fit(obs[trm], lat[trm])
    ch_pred = ch.predict(obs[~trm])
    (out / "chaos_index.json").write_text(json.dumps({
        "type": "linear", "target": "latent chaos (0..1) from simulation ground truth",
        "coef": {k: round(float(v), 6) for k, v in zip(["turnovers_pm", "fouls_pm", "pass_fail_rate"], ch.coef_)},
        "intercept": round(float(ch.intercept_), 6)}, indent=1))

    # ---------------- explainability check vs hidden ground truth (held-out matches)
    report["ground_truth_check"] = {
        "corr_momentum_vs_latent": round(float(np.corrcoef(gtr[~trm, 0], gtr[~trm, 1])[0, 1]), 3),
        "corr_chaos_index_vs_latent": round(float(np.corrcoef(ch_pred, lat[~trm])[0, 1]), 3)}
    (out / "training_report.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()

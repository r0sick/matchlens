"""Chart one match: live win probability, momentum and chaos vs the hidden ground truth.

    python tools/match_report.py data/matches/M000042 --out report.png
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from matchsim.replay import load_match
from matchlens.models import load_models
from matchlens.state import MatchState


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--out", default="match_report.png")
    a = ap.parse_args()
    m = load_match(a.path)
    meta = m["metadata"]
    gt = json.loads((Path(a.path) / "ground_truth.json").read_text())["timeline"]
    st = MatchState(meta, models=load_models())
    goals = []
    for ev in m["events"]:
        st.update(ev)
        if ev["type"] == "goal":
            goals.append((ev["match_time_s"] / 60.0, ev["team_side"], ev["player_name"]))
    s = st.series
    mins = [p["t_min"] for p in s]      # continuous playing time (handles stoppage time)
    H, A = meta["home"], meta["away"]
    ch, ca = H["colors"]["primary"], A["colors"]["primary"]
    if ch.lower() == ca.lower():
        ca = A["colors"]["secondary"]

    fig, ax = plt.subplots(4, 1, figsize=(11, 12), sharex=True, gridspec_kw={"height_ratios": [3, 2, 2, 2]})
    fig.suptitle(f"{H['name']} {st.score['home']}–{st.score['away']} {A['name']}  ·  live model view vs hidden truth",
                 fontsize=13, x=0.01, ha="left")

    wh = [p["win_prob"]["home"] for p in s]
    wd = [p["win_prob"]["draw"] for p in s]
    wa = [p["win_prob"]["away"] for p in s]
    ax[0].stackplot(mins, wh, wd, wa, colors=[ch, "#BDBDBD", ca], alpha=0.85,
                    labels=[H["abbr"] + " win", "draw", A["abbr"] + " win"])
    for mm, side, name in goals:
        ax[0].axvline(mm, color="black", lw=0.8, ls=":")
        ax[0].text(mm + 0.5, 0.97 if side == "home" else 0.05, f"GOAL {name}", fontsize=8, va="top" if side == "home" else "bottom")
    ax[0].set_ylim(0, 1)
    ax[0].set_ylabel("win probability")
    ax[0].legend(loc="upper left", fontsize=8, ncol=3, frameon=False)

    ax[1].plot(mins, [p["xg"][0] for p in s], color=ch, lw=2, label=f"{H['abbr']} xG")
    ax[1].plot(mins, [p["xg"][1] for p in s], color=ca, lw=2, label=f"{A['abbr']} xG")
    ax[1].set_ylabel("cumulative xG")
    ax[1].legend(loc="upper left", fontsize=8, frameon=False)

    n1 = sum(1 for r in gt if r["period"] == 1)
    gmins = [r["minute"] if r["period"] == 1 else n1 + r["minute"] - 45 for r in gt]
    ax[2].axhline(0, color="#999", lw=0.6)
    ax[2].plot(mins, [p["momentum"] / 100 for p in s], color="#1f77b4", lw=2, label="momentum index (from events)")
    ax[2].plot(gmins, [r["momentum_home"] for r in gt], color="#d62728", lw=1.2, ls="--", label="latent momentum (hidden)")
    ax[2].set_ylim(-1, 1)
    ax[2].set_ylabel(f"← {A['abbr']}   {H['abbr']} →")
    ax[2].legend(loc="upper left", fontsize=8, frameon=False)

    ax[3].plot(mins, [p["chaos"] / 100 for p in s], color="#9467bd", lw=2, label="chaos index (from events)")
    ax[3].plot(gmins, [r["chaos"] for r in gt], color="#d62728", lw=1.2, ls="--", label="latent chaos (hidden)")
    ax[3].set_ylim(0, 1)
    ax[3].set_ylabel("control → chaos")
    ax[3].set_xlabel("minutes of play (first-half stoppage time included)")
    ax[3].legend(loc="upper left", fontsize=8, frameon=False)
    for x in ax:
        x.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    plt.savefig(a.out, dpi=130)
    print(f"saved {a.out}")


if __name__ == "__main__":
    main()

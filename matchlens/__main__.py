"""Live terminal dashboard.

    python -m matchlens data/matches/M000042 --speed 60
    python -m matchlens data/matches/M000042 --speed 600 --alerts-only

Streams the match through the live state engine and prints one status line per
match minute plus alerts (goals, win-probability swings, speed, hard passes...).
"""
from __future__ import annotations

import argparse

from matchsim.replay import iter_live, load_match
from .models import load_models
from .state import MatchState


def bar(p, width=20):
    n = int(round(p * width))
    return "█" * n + "·" * (width - n)


def fmt_alert(sig, meta):
    abbr = {"home": meta["home"]["abbr"], "away": meta["away"]["abbr"]}
    m = sig["display_minute"]
    if sig["kind"] == "win_prob_swing":
        a, b = sig["before"], sig["after"]
        return (f"{m:>7} ⚖  win prob after {sig['cause']}: {abbr['home']} {100*a['home']:.0f}%→{100*b['home']:.0f}% | "
                f"draw {100*a['draw']:.0f}%→{100*b['draw']:.0f}% | {abbr['away']} {100*a['away']:.0f}%→{100*b['away']:.0f}%")
    d = sig["data"]
    who = f"{sig['player_name']} ({abbr.get(sig['side'], '')})"
    k = sig["alert"]
    if k == "goal":
        return f"{m:>7} ⚽ GOAL {who}  {abbr['home']} {d['score']['home']}-{d['score']['away']} {abbr['away']}  (xG {d['xg']:.2f})"
    if k == "speed":
        rec = " – fastest of the match" if d["match_record"] else ""
        return f"{m:>7} ⚡ {who} sprint {d['top_speed_kmh']:.1f} km/h{rec}"
    if k == "rocket_shot":
        return f"{m:>7} 🚀 {who} shot at {d['shot_speed_kmh']:.0f} km/h ({d['outcome']})"
    if k == "hard_pass":
        return f"{m:>7} 🎯 {who} completes a difficulty-{d['difficulty']} pass to {d['recipient']} ({', '.join(d['reasons'])})"
    if k == "long_pass":
        return f"{m:>7} ↗  {who} {d['length_m']:.0f} m pass to {d['recipient']}"
    if k == "big_chance_missed":
        return f"{m:>7} 😬 {who} misses a big chance (xG {d['xg']:.2f}, {d['outcome']})"
    if k == "card":
        return f"{m:>7} 🟨 {who} {d['card'].replace('_', ' ')}"
    if k == "substitution":
        return f"{m:>7} 🔁 {abbr[sig['side']]}: {d['on']} on for {d['off']}"
    if k == "distance":
        return f"{m:>7} 🏃 {who} passes {d['km']} km covered"
    return None


def status_line(st: MatchState, meta):
    h, a = meta["home"]["abbr"], meta["away"]["abbr"]
    wp = st.win_prob or {"home": 1 / 3, "draw": 1 / 3, "away": 1 / 3}
    poss = st.possession()["last5"]
    mom = st.momentum
    arrow = "◀◀" if mom < -40 else "◀ " if mom < -15 else "▶▶" if mom > 40 else " ▶" if mom > 15 else " ="
    th, ta = st.teams["home"], st.teams["away"]
    return (f"{st.display_minute:>7} {h} {st.score['home']}-{st.score['away']} {a} | "
            f"WP {100*wp['home']:3.0f}/{100*wp['draw']:3.0f}/{100*wp['away']:3.0f} {bar(wp['home'], 10)} | "
            f"xG {th['xg']:.2f}-{ta['xg']:.2f} | poss5 {poss[0]:.0f}% | momentum {mom:+4.0f} {arrow} | chaos {st.chaos:3.0f}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="matchlens")
    ap.add_argument("path")
    ap.add_argument("--speed", type=float, default=60.0)
    ap.add_argument("--alerts-only", action="store_true")
    ap.add_argument("--no-minor", action="store_true", help="hide long-pass / hard-pass / distance alerts")
    a = ap.parse_args(argv)
    m = load_match(a.path)
    meta = m["metadata"]
    st = MatchState(meta, models=load_models())
    print(f"{meta['home']['name']} vs {meta['away']['name']} — {meta['venue']['stadium']}")
    last_min = None
    try:
        for ev in iter_live(m["events"], speed=a.speed):
            for sig in st.update(ev):
                if a.no_minor and sig.get("alert") in ("long_pass", "hard_pass", "distance"):
                    continue
                line = fmt_alert(sig, meta)
                if line:
                    print(line, flush=True)
            if not a.alerts_only and ev["minute"] != last_min and ev["minute"] % 5 == 0:
                last_min = ev["minute"]
                print(status_line(st, meta), flush=True)
        print(status_line(st, meta))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

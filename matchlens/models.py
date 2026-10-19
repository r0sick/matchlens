"""Model wrappers: pass difficulty, win probability, next goal.

All three are multinomial/binary logistic models exported as plain JSON
coefficients, so inference needs only the standard library and every
prediction can be explained term by term.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

MODEL_DIR = Path(__file__).parent / "model_files"
BOX_X, BOX_Y0, BOX_Y1 = 88.5, 13.84, 54.16
SET_PIECES = {"corner", "free_kick", "throw_in", "goal_kick", "gk_throw", "kick_off"}

# --------------------------------------------------------------------------- pass difficulty
PASS_FEATURES = ["length", "length_sq", "under_pressure", "defenders_in_lane", "log_space", "height_low",
                 "height_high", "forward", "start_x", "end_x", "into_box", "through_ball", "cross",
                 "long_ball", "switch", "set_piece"]

PASS_REASON_TEXT = {
    "length": "long distance", "length_sq": "long distance", "under_pressure": "under pressure",
    "defenders_in_lane": "defenders in the passing lane", "log_space": "tight space for the receiver",
    "height_low": "driven ball", "height_high": "lofted ball", "forward": "played forward",
    "start_x": "from deep", "end_x": "into the attacking zone", "into_box": "into the box",
    "through_ball": "through ball", "cross": "cross", "long_ball": "long ball", "switch": "switch of play",
    "set_piece": "set piece",
}


def pass_features(ev: dict) -> dict:
    d = ev["details"]
    x, y = ev["location"]
    ex, ey = ev["end_location"]
    ln = d.get("length_m") or math.hypot(ex - x, ey - y)
    ptype = d.get("pass_type")
    return {
        "length": ln / 10.0,
        "length_sq": (ln / 10.0) ** 2,
        "under_pressure": float(bool(d.get("under_pressure"))),
        "defenders_in_lane": float(d.get("defenders_in_lane") or 0),
        "log_space": math.log(max(0.3, d.get("receiver_space_m") or 5.0) + 0.5),
        "height_low": float(d.get("height") == "low"),
        "height_high": float(d.get("height") == "high"),
        "forward": (ex - x) / max(ln, 1.0),
        "start_x": x / 105.0,
        "end_x": ex / 105.0,
        "into_box": float(ex >= BOX_X and BOX_Y0 <= ey <= BOX_Y1 and not (x >= BOX_X and BOX_Y0 <= y <= BOX_Y1)),
        "through_ball": float(ptype == "through_ball"),
        "cross": float(bool(d.get("cross"))),
        "long_ball": float(ptype == "long_ball"),
        "switch": float(bool(d.get("switch"))),
        "set_piece": float(ptype in SET_PIECES),
    }


class PassModel:
    def __init__(self, spec: dict):
        self.coef = spec["coef"]
        self.intercept = spec["intercept"]
        self.means = spec["feature_means"]

    def prob_complete(self, f: dict) -> float:
        z = self.intercept + sum(self.coef[k] * f[k] for k in self.coef)
        return 1.0 / (1.0 + math.exp(-z))

    def difficulty(self, ev: dict):
        """0 (trivial) .. 100 (near impossible) plus the two biggest reasons."""
        f = pass_features(ev)
        p = self.prob_complete(f)
        contrib = {k: -self.coef[k] * (f[k] - self.means[k]) for k in self.coef}
        # merge the two length terms
        contrib["length"] = contrib.get("length", 0) + contrib.pop("length_sq", 0)
        top = sorted((c, k) for k, c in contrib.items() if c > 0.15)[::-1][:2]
        return int(round(100 * (1 - p))), [PASS_REASON_TEXT[k] for _, k in top]


# --------------------------------------------------------------------------- win / next goal
def expand(f: dict, names: list[str]) -> list[float]:
    """Engineered terms for the in-game models (time interactions matter most)."""
    tl = f["time_left"]
    gd = f["goal_diff"]
    terms = {
        "gd": gd, "gd_late": gd * (1 - tl), "gd_late2": gd * (1 - tl) ** 2,
        "abs_gd_late": abs(gd) * (1 - tl),
        "xg_diff": f["xg_diff"] * tl, "xg_diff_15": f["xg_diff_15"] * tl,
        "shots_diff_15": f["shots_diff_15"] * tl,
        "red_diff": f["red_diff"] * tl,
        "strength": f["strength_diff"] * tl, "strength_raw": f["strength_diff"],
        "momentum": f["momentum"] * tl, "tilt": f["tilt_10"] * tl, "poss": f["poss_5"] * tl,
        "time_left": tl, "time_left2": tl * tl,
        "level_late": float(gd == 0) * (1 - tl),
        "goals_total": (f["home_goals"] + f["away_goals"]) * tl,
    }
    return [terms[n] for n in names]


class MultiLogit:
    def __init__(self, spec: dict):
        self.classes = spec["classes"]
        self.terms = spec["terms"]
        self.coef = spec["coef"]            # class -> list
        self.intercept = spec["intercept"]  # class -> float
        self.mean = spec["scaler_mean"]
        self.scale = spec["scaler_scale"]

    def predict(self, f: dict) -> dict:
        x = expand(f, self.terms)
        x = [(v - m) / s for v, m, s in zip(x, self.mean, self.scale)]
        z = {c: self.intercept[c] + sum(w * v for w, v in zip(self.coef[c], x)) for c in self.classes}
        mx = max(z.values())
        e = {c: math.exp(v - mx) for c, v in z.items()}
        tot = sum(e.values())
        return {c: e[c] / tot for c in self.classes}

    def explain(self, f: dict, cls: str, top=3):
        x = expand(f, self.terms)
        x = [(v - m) / s for v, m, s in zip(x, self.mean, self.scale)]
        contrib = [(w * v, n) for w, v, n in zip(self.coef[cls], x, self.terms)]
        return sorted(contrib, key=lambda c: -abs(c[0]))[:top]


class ChaosModel:
    """Linear map from observable match rhythm to a 0..100 chaos index (fit on simulated ground truth)."""

    def __init__(self, spec: dict):
        self.coef = spec["coef"]
        self.intercept = spec["intercept"]

    def predict(self, obs: dict) -> float:
        v = self.intercept + sum(self.coef[k] * obs[k] for k in self.coef)
        return max(0.0, min(100.0, 100.0 * v))


class Models:
    def __init__(self, pass_model=None, win_model=None, next_goal_model=None, chaos_model=None):
        self.pass_model = pass_model
        self.win_model = win_model
        self.next_goal_model = next_goal_model
        self.chaos_model = chaos_model


def load_models(directory: str | Path = MODEL_DIR) -> Models:
    directory = Path(directory)

    def rd(name):
        p = directory / name
        return json.loads(p.read_text()) if p.exists() else None
    pm, wm, ng, ch = rd("pass_difficulty.json"), rd("win_prob.json"), rd("next_goal.json"), rd("chaos_index.json")
    return Models(PassModel(pm) if pm else None, MultiLogit(wm) if wm else None, MultiLogit(ng) if ng else None,
                  ChaosModel(ch) if ch else None)

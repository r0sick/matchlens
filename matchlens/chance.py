"""Live goal chance: the probability that the team on the ball scores before it loses the ball.

Updated on every touch (pass, carry, dribble, cross, set piece) of the team in possession, from where the
ball is now and how the move got there. It is the live, "while the play is happening" counterpart of xG, which
only exists once a shot is taken. Logistic model, trained on simulated matches that never overlap the demo or
season data (tools/train_chance_model.py); coefficients live in model_files/goal_chance.json.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

MODEL_FILE = Path(__file__).parent / "model_files" / "goal_chance.json"
BALL_EVENTS = {"pass", "carry", "dribble"}
GOAL_X, GOAL_Y = 105.0, 34.0
BOX_X, BOX_Y0, BOX_Y1 = 88.5, 13.84, 54.16


def ball_after(ev: dict):
    """Where the ball is after this action, in the attacking team's frame (x 0 -> 105 towards goal)."""
    if ev["type"] == "pass":
        return ev["end_location"] if ev["outcome"] == "complete" and ev.get("end_location") else None
    if ev["type"] in ("carry", "dribble"):
        if ev["type"] == "dribble" and ev["outcome"] != "complete":
            return None
        return ev.get("end_location") or ev.get("location")
    return None


def features(ev: dict, ctx: dict) -> dict | None:
    pos = ball_after(ev)
    if pos is None:
        return None
    x, y = pos
    dx, dy = GOAL_X - x, abs(y - GOAL_Y)
    dist = math.hypot(dx, dy)
    # angle subtended by the goal mouth (7.32 m) from the ball
    a = math.atan2(7.32 * dx, dx * dx + dy * dy - (7.32 / 2) ** 2)
    angle = a if a >= 0 else a + math.pi
    d = ev.get("details") or {}
    pattern = ctx.get("pattern") or ev.get("play_pattern")
    in_box = float(x >= BOX_X and BOX_Y0 <= y <= BOX_Y1)
    return {
        "dist": dist / 10.0, "dist_sq": (dist / 10.0) ** 2, "angle": angle, "in_box": in_box,
        "box_angle": in_box * angle, "near": math.exp(-dist / 12.0), "close": math.exp(-dist / 5.0),
        "close_angle": math.exp(-dist / 5.0) * angle, "final_third": float(x >= 70), "x": x / 105.0, "y_c": dy / 34.0,
        "cross": float(bool(d.get("cross"))), "through": float(d.get("pass_type") == "through_ball"),
        "pressure": float(bool(d.get("under_pressure"))), "carry": float(ev["type"] != "pass"),
        "counter": float(pattern == "from_counter"), "corner": float(pattern == "from_corner"),
        "free_kick": float(pattern == "from_free_kick"), "penalty": float(pattern == "from_penalty"),
        "actions": math.log1p(ctx.get("actions", 0)), "seconds": min(60.0, ctx.get("seconds", 0.0)) / 60.0,
    }


class ChanceModel:
    def __init__(self, spec: dict):
        self.terms, self.coef, self.intercept = spec["terms"], spec["coef"], spec["intercept"]
        self.mean, self.scale = spec["scaler_mean"], spec["scaler_scale"]

    def predict(self, f: dict) -> float:
        z = self.intercept + sum(w * (f[k] - m) / s for k, w, m, s in zip(self.terms, self.coef, self.mean, self.scale))
        return 1.0 / (1.0 + math.exp(-z))


def load_chance_model(path: Path = MODEL_FILE) -> ChanceModel | None:
    return ChanceModel(json.loads(path.read_text())) if path.exists() else None


class ChanceTracker:
    """Follows possessions in a live match and returns the current goal chance after each touch."""

    def __init__(self, meta: dict, model: ChanceModel | None):
        self.model = model
        self.side_of = {meta["home"]["team_id"]: "home", meta["away"]["team_id"]: "away"}
        self.poss = None
        self.ctx = {}
        self.current = None          # {"side", "p", "player", "t"}

    def update(self, ev: dict) -> dict | None:
        if not self.model:
            return None
        pid = ev.get("possession_id")
        if pid is not None and pid != self.poss:
            self.poss, self.ctx = pid, {"actions": 0, "start": ev["match_time_s"], "pattern": ev.get("play_pattern")}
            self.current = None
        if ev["type"] in ("goal", "period_end", "match_end", "kick_off"):
            self.current = None
            return None
        if ev["type"] not in BALL_EVENTS or ev.get("team_id") != ev.get("possession_team_id"):
            return None
        self.ctx["actions"] += 1
        self.ctx["seconds"] = ev["match_time_s"] - self.ctx["start"]
        f = features(ev, self.ctx)
        if f is None:                                            # ball lost or not under control
            self.current = None
            return None
        self.current = {"side": self.side_of.get(ev["team_id"]), "p": round(self.model.predict(f), 4),
                        "player": ev.get("player_name"), "t": round(ev["match_time_s"], 2)}
        return self.current

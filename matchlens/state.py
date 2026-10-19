"""Live match state: turns the event stream into football statistics, one event at a time.

Usage:
    state = MatchState(metadata, models=load_models())
    for ev in feed:
        signals = state.update(ev)      # alerts and probability changes caused by this event
        view = state.snapshot()         # full current picture for the UI

Everything here is computed only from events seen so far (no look-ahead), so it
behaves identically on a live feed and on a replay. Note that `key_pass` and
`assist` flags on pass events are post-hoc annotations from the provider; this
module ignores them and derives key passes and assists when the shot or goal
arrives.
"""
from __future__ import annotations

import math
from collections import defaultdict, deque

SIDES = ("home", "away")
FINAL_THIRD_X = 70.0
BOX_X, BOX_Y0, BOX_Y1 = 88.5, 13.84, 54.16

# Alert thresholds (tune for the broadcast)
SPRINT_ALERT_KMH = 35.0      # plus any new match top speed
ROCKET_SHOT_KMH = 105.0
LONG_PASS_M = 60.0
HARD_PASS_DIFFICULTY = 75
BIG_CHANCE_XG = 0.30
DISTANCE_MILESTONES_KM = (5, 10, 12)

# Momentum: exponentially decaying "threat" per team
MOMENTUM_HALF_LIFE_S = 180.0
THREAT = {"final_third_pass": 0.25, "box_entry": 1.0, "corner": 0.6, "shot": 1.0, "xg": 6.0}


def other(side):
    return "away" if side == "home" else "home"


def in_box(x, y):
    return x >= BOX_X and BOX_Y0 <= y <= BOX_Y1


class Rolling:
    """Time-windowed sums per side."""

    def __init__(self, window_s):
        self.window = window_s
        self.items = deque()          # (t, side, value)
        self.sum = {"home": 0.0, "away": 0.0}

    def add(self, t, side, v=1.0):
        self.items.append((t, side, v))
        self.sum[side] += v

    def advance(self, t):
        while self.items and self.items[0][0] < t - self.window:
            _, s, v = self.items.popleft()
            self.sum[s] -= v

    def share(self, side, default=50.0):
        tot = self.sum["home"] + self.sum["away"]
        return default if tot <= 1e-9 else 100.0 * self.sum[side] / tot


def new_team():
    return defaultdict(float)


def new_player(p, side):
    d = defaultdict(float)
    d.update({"player_id": p["player_id"], "name": p["short_name"], "shirt": p["shirt"],
              "position": p["position"], "group": p["group"], "side": side})
    return d


class MatchState:
    def __init__(self, metadata: dict, models=None):
        self.meta = metadata
        self.models = models
        self.match_id = metadata["match_id"]
        self.team_id = {metadata["home"]["team_id"]: "home", metadata["away"]["team_id"]: "away"}
        self.teams = {s: new_team() for s in SIDES}
        self.players = {}
        self.on_pitch = {s: set() for s in SIDES}
        for s in SIDES:
            for p in metadata[s]["starting_xi"]:
                self.players[p["player_id"]] = new_player(p, s)
                self.players[p["player_id"]]["minutes_on"] = 0
                self.on_pitch[s].add(p["player_id"])
            for p in metadata[s]["bench"]:
                self.players[p["player_id"]] = new_player(p, s)
        self.strength = {s: sum(p["overall"] for p in metadata[s]["starting_xi"]) / 11 for s in SIDES}

        self.score = {"home": 0, "away": 0}
        self.reds = {"home": 0, "away": 0}
        self.t = 0.0
        self.minute = 0
        self.period = 1
        self.clock = "00:00"
        self.display_minute = "1'"
        self.finished = False

        # possession clock
        self.poss_side = None
        self.last_t = 0.0
        self.poss_total = {"home": 0.0, "away": 0.0}
        self.poss_5 = Rolling(300)
        # territory & pressing
        self.tilt_total = {"home": 0, "away": 0}
        self.tilt_10 = Rolling(600)
        self.ppda_passes = {"home": 0, "away": 0}       # opponent passes allowed (key = pressing side)
        self.ppda_def = {"home": 0, "away": 0}          # defensive actions by pressing side
        self.ppda_p15 = Rolling(900)
        self.ppda_d15 = Rolling(900)
        # rhythm
        self.turnovers_5 = Rolling(300)
        self.fouls_5 = Rolling(300)
        self.passes_5 = Rolling(300)
        self.fail_5 = Rolling(300)
        self.xg_15 = Rolling(900)
        self.shots_15 = Rolling(900)
        # momentum
        self.threat = {"home": 0.0, "away": 0.0}
        self.threat_t = 0.0
        self.momentum = 0.0
        self.chaos = 0.0
        self.chaos_obs = {}
        # series for charts (one point per match minute)
        self.series = []
        self._last_series_min = -1
        # probabilities
        self.win_prob = None
        self.next_goal = None
        self.last_pass = {}           # side -> pass event (for xA attribution sanity)
        self.top_speed = {"kmh": 0.0, "player_id": None, "name": None}
        self.dist_flags = defaultdict(set)

    # ------------------------------------------------------------------ helpers
    def side_of(self, ev):
        return ev.get("team_side") or self.team_id.get(ev.get("team_id"))

    def _p(self, pid):
        return self.players.get(pid)

    def _decay_threat(self, t):
        dt = max(0.0, t - self.threat_t)
        if dt:
            f = 0.5 ** (dt / MOMENTUM_HALF_LIFE_S)
            for s in SIDES:
                self.threat[s] *= f
            self.threat_t = t

    def _add_threat(self, side, v):
        self.threat[side] += v

    def _update_derived(self):
        h, a = self.threat["home"], self.threat["away"]
        self.momentum = 100.0 * (h - a) / (h + a + 2.0)
        # chaos: turnovers + fouls per minute and pass failure share, scaled to ~0..100
        mins = 5.0
        turn = (self.turnovers_5.sum["home"] + self.turnovers_5.sum["away"]) / mins
        fouls = (self.fouls_5.sum["home"] + self.fouls_5.sum["away"]) / mins
        passes = self.passes_5.sum["home"] + self.passes_5.sum["away"]
        fail = (self.fail_5.sum["home"] + self.fail_5.sum["away"]) / passes if passes else 0.2
        self.chaos_obs = {"turnovers_pm": turn, "fouls_pm": fouls, "pass_fail_rate": fail}
        if self.models and self.models.chaos_model:
            self.chaos = self.models.chaos_model.predict(self.chaos_obs)
        else:
            raw = 0.35 * (turn - 2.6) / 0.9 + 0.15 * (fouls - 0.25) / 0.25 + 0.50 * (fail - 0.2) / 0.06
            self.chaos = max(0.0, min(100.0, 30 + 15 * raw))

    # ------------------------------------------------------------------ main
    def update(self, ev: dict) -> list[dict]:
        signals = []
        t = ev["match_time_s"]
        etype = ev["type"]
        side = self.side_of(ev)
        d = ev.get("details") or {}
        pid = ev.get("player_id")
        P = self._p(pid) if pid else None

        # --- clock and possession time (gaps > 8 s treated as dead ball)
        if self.poss_side and t > self.last_t:
            dt = min(t - self.last_t, 8.0)
            self.poss_total[self.poss_side] += dt
            self.poss_5.add(t, self.poss_side, dt)
        self.last_t = max(self.last_t, t)
        ps = self.team_id.get(ev.get("possession_team_id"))
        if ps:
            self.poss_side = ps
        self.t = t
        self.period = ev["period"]
        self.minute = ev["minute"]
        self.clock = ev["clock"]
        self.display_minute = ev["display_minute"]
        for r in (self.poss_5, self.tilt_10, self.ppda_p15, self.ppda_d15, self.turnovers_5,
                  self.fouls_5, self.passes_5, self.fail_5, self.xg_15, self.shots_15):
            r.advance(t)
        self._decay_threat(t)

        T = self.teams[side] if side else None
        loc = ev.get("location")

        if etype == "pass":
            ok = ev["outcome"] == "complete"
            T["passes"] += 1
            P["passes"] += 1
            self.passes_5.add(t, side)
            ptype = d.get("pass_type")
            if ok:
                T["passes_complete"] += 1
                P["passes_complete"] += 1
            else:
                self.fail_5.add(t, side)
            if ptype == "corner":
                T["corners"] += 1
                self._add_threat(side, THREAT["corner"])
            if d.get("cross"):
                T["crosses"] += 1
                if ok:
                    T["crosses_complete"] += 1
            x, y = loc
            ex, ey = ev["end_location"]
            if x >= FINAL_THIRD_X:
                self.tilt_total[side] += 1
                self.tilt_10.add(t, side)
            if ok and ex >= FINAL_THIRD_X > x:
                T["final_third_entries"] += 1
                self._add_threat(side, THREAT["final_third_pass"])
            if ok and in_box(ex, ey) and not in_box(x, y):
                T["box_entries"] += 1
                P["passes_into_box"] += 1
                self._add_threat(side, THREAT["box_entry"])
            if ok and d.get("progressive_distance_m", 0) >= 10 and ex > 35:
                P["progressive_passes"] += 1
            # PPDA: passes by `side` in its own 60% count against the opponent's press
            if x < 63:
                self.ppda_passes[other(side)] += 1
                self.ppda_p15.add(t, other(side))
            # pass quality
            if self.models and self.models.pass_model:
                diff, reasons = self.models.pass_model.difficulty(ev)
                ev.setdefault("derived", {})["pass_difficulty"] = diff
                ev["derived"]["difficulty_reasons"] = reasons
                P["difficulty_sum"] += diff
                if ok:
                    P["hard_passes_complete"] += diff >= HARD_PASS_DIFFICULTY
                    if diff >= HARD_PASS_DIFFICULTY:
                        signals.append(self._alert("hard_pass", ev, {
                            "difficulty": diff, "reasons": reasons,
                            "length_m": d.get("length_m"), "recipient": d.get("recipient_name")}))
            if ok and d.get("length_m", 0) >= LONG_PASS_M:
                signals.append(self._alert("long_pass", ev, {"length_m": d["length_m"],
                                                             "ball_speed_kmh": d.get("ball_speed_kmh"),
                                                             "recipient": d.get("recipient_name")}))
            self.last_pass[side] = ev

        elif etype == "carry":
            ex, ey = ev["end_location"]
            if in_box(ex, ey) and not in_box(*loc):
                T["box_entries"] += 1
                self._add_threat(side, THREAT["box_entry"])
            if d.get("progressive_m", 0) >= 10:
                P["progressive_carries"] += 1

        elif etype == "shot":
            xg = d["xg"]
            T["shots"] += 1
            T["xg"] += xg
            P["shots"] += 1
            P["xg"] += xg
            self.xg_15.add(t, side, xg)
            self.shots_15.add(t, side)
            self._add_threat(side, THREAT["shot"] + THREAT["xg"] * xg)
            if d["on_target"]:
                T["shots_on_target"] += 1
                P["shots_on_target"] += 1
            if ev["outcome"] == "blocked":
                T["shots_blocked"] += 1
            if d.get("big_chance"):
                T["big_chances"] += 1
            kp = self._p(d.get("key_pass_player_id"))
            if kp:
                kp["key_passes"] += 1
                kp["xa"] += xg
            if d.get("shot_speed_kmh", 0) >= ROCKET_SHOT_KMH:
                signals.append(self._alert("rocket_shot", ev, {"shot_speed_kmh": d["shot_speed_kmh"],
                                                               "outcome": ev["outcome"]}))
            if xg >= BIG_CHANCE_XG and ev["outcome"] != "goal":
                signals.append(self._alert("big_chance_missed", ev, {"xg": xg, "outcome": ev["outcome"]}))

        elif etype == "goal":
            self.score[side] += 1
            T["goals"] += 1
            P["goals"] += 1
            ap = self._p(d.get("assist_player_id"))
            if ap:
                ap["assists"] += 1
            gk = self._gk(other(side))
            if gk:
                gk["goals_conceded"] += 1
            signals.append(self._alert("goal", ev, {"score": dict(self.score), "xg": d.get("xg"),
                                                    "assist": d.get("assist_player_name")}))

        elif etype == "goalkeeper" and d.get("action") == "save":
            T["saves"] += 1
            P["saves"] += 1

        elif etype == "tackle":
            T["tackles"] += 1
            P["tackles"] += 1
            if ev["outcome"] == "won":
                T["tackles_won"] += 1
                P["tackles_won"] += 1
                victim = self._p(d.get("opponent_id"))
                if victim:
                    victim["dispossessed"] += 1
            if loc and loc[0] > 42:
                self.ppda_def[side] += 1
                self.ppda_d15.add(t, side)

        elif etype in ("interception", "ball_recovery"):
            T[etype + "s"] += 1
            P[etype + "s"] += 1
            if etype == "interception" and loc and loc[0] > 42:
                self.ppda_def[side] += 1
                self.ppda_d15.add(t, side)
            if loc and loc[0] >= 60:
                T["high_turnovers"] += 1

        elif etype == "pressure":
            T["pressures"] += 1
            P["pressures"] += 1

        elif etype == "dribble":
            T["dribbles"] += 1
            P["dribbles"] += 1
            if ev["outcome"] == "complete":
                T["dribbles_complete"] += 1
                P["dribbles_complete"] += 1

        elif etype == "aerial_duel":
            P["aerials"] += 1
            if ev["outcome"] == "won":
                P["aerials_won"] += 1
                T["aerials_won"] += 1

        elif etype == "clearance":
            P["clearances"] += 1
            T["clearances"] += 1

        elif etype == "foul":
            T["fouls"] += 1
            P["fouls"] += 1
            self.fouls_5.add(t, side)
            if loc and loc[0] > 42:
                self.ppda_def[side] += 1
                self.ppda_d15.add(t, side)

        elif etype == "card":
            card = d["card"]
            if card == "yellow":
                T["yellow"] += 1
                P["yellow"] += 1
            else:
                T["red"] += 1
                P["red"] += 1
                self.reds[side] += 1
                self.on_pitch[side].discard(pid)
                if P:
                    P["minutes_off"] = self.minute
            signals.append(self._alert("card", ev, {"card": card}))

        elif etype == "offside":
            T["offsides"] += 1

        elif etype == "possession_change":
            self.turnovers_5.add(t, side)

        elif etype == "substitution":
            off, on = d["player_off_id"], d["player_on_id"]
            self.on_pitch[side].discard(off)
            self.on_pitch[side].add(on)
            if off in self.players:
                self.players[off]["minutes_off"] = self.minute
            if on in self.players:
                self.players[on]["minutes_on"] = self.minute
            T["subs"] += 1
            signals.append(self._alert("substitution", ev, {"on": d["player_on_name"], "off": d["player_off_name"],
                                                            "reason": d.get("reason")}))

        elif etype == "sprint":
            kmh = d["top_speed_kmh"]
            P["sprints"] += 1
            P["top_speed_kmh"] = max(P["top_speed_kmh"], kmh)
            T["sprints"] += 1
            record = kmh > self.top_speed["kmh"]
            if record:
                self.top_speed = {"kmh": kmh, "player_id": pid, "name": ev["player_name"], "side": side}
            if kmh >= SPRINT_ALERT_KMH or (record and kmh >= 32.0):
                signals.append(self._alert("speed", ev, {"top_speed_kmh": kmh, "match_record": record,
                                                         "distance_m": d.get("distance_m")}))

        elif etype == "physical_snapshot":
            tot = 0.0
            for row in d["players"]:
                Q = self._p(row["player_id"])
                if not Q:
                    continue
                Q["distance_m"] = row["distance_m"]
                Q["hi_run_m"] = row["hi_run_m"]
                Q["stamina_pct"] = row["stamina_pct"]
                for km in DISTANCE_MILESTONES_KM:
                    if row["distance_m"] >= km * 1000 and km not in self.dist_flags[row["player_id"]]:
                        self.dist_flags[row["player_id"]].add(km)
                        if km >= 10:
                            signals.append({"kind": "alert", "alert": "distance", "t": t,
                                            "display_minute": ev["display_minute"], "side": side,
                                            "player_id": row["player_id"], "player_name": row["player_name"],
                                            "data": {"km": km}})
            T["distance_km"] = sum(Q.get("distance_m", 0) for Q in self.players.values()
                                   if Q["side"] == side) / 1000

        elif etype == "match_end":
            self.finished = True

        self._update_derived()

        # --- probabilities: refresh on game-state changes and on every new match minute
        new_min = self.minute != self._last_series_min
        if self.models and self.models.win_model and (etype in ("goal", "card", "shot", "match_end") or new_min):
            old = self.win_prob
            self.win_prob = self.models.win_model.predict(self.features())
            if self.models.next_goal_model:
                self.next_goal = self.models.next_goal_model.predict(self.features())
            if self.finished:
                h, a = self.score["home"], self.score["away"]
                self.win_prob = {"home": float(h > a), "draw": float(h == a), "away": float(a > h)}
            if old and etype in ("goal", "card", "shot"):
                swing = {k: round(100 * (self.win_prob[k] - old[k]), 1) for k in old}
                if max(abs(v) for v in swing.values()) >= 3:
                    signals.append({"kind": "win_prob_swing", "t": t, "display_minute": ev["display_minute"],
                                    "cause_event_id": ev["event_id"], "cause": etype,
                                    "before": {k: round(v, 3) for k, v in old.items()},
                                    "after": {k: round(v, 3) for k, v in self.win_prob.items()},
                                    "swing_pts": swing})
        if new_min:
            self._last_series_min = self.minute
            self.series.append(self._series_point())
        return signals

    # ------------------------------------------------------------------ outputs
    def _gk(self, side):
        for pid in self.on_pitch[side]:
            if self.players[pid]["group"] == "GK":
                return self.players[pid]
        return None

    def _alert(self, kind, ev, data):
        return {"kind": "alert", "alert": kind, "t": ev["match_time_s"], "display_minute": ev["display_minute"],
                "event_id": ev["event_id"], "side": self.side_of(ev), "player_id": ev.get("player_id"),
                "player_name": ev.get("player_name"), "data": data}

    def possession(self):
        tot = self.poss_total["home"] + self.poss_total["away"]
        h = 50.0 if tot == 0 else 100 * self.poss_total["home"] / tot
        return {"total": [round(h, 1), round(100 - h, 1)],
                "last5": [round(self.poss_5.share("home"), 1), round(self.poss_5.share("away"), 1)]}

    def field_tilt(self):
        tot = self.tilt_total["home"] + self.tilt_total["away"]
        h = 50.0 if tot == 0 else 100 * self.tilt_total["home"] / tot
        return {"total": [round(h, 1), round(100 - h, 1)],
                "last10": [round(self.tilt_10.share("home"), 1), round(self.tilt_10.share("away"), 1)]}

    def ppda(self):
        out = {}
        for s in SIDES:
            out[s] = round(self.ppda_passes[s] / max(1, self.ppda_def[s]), 1)
            out[s + "_last15"] = round(self.ppda_p15.sum[s] / max(1.0, self.ppda_d15.sum[s]), 1)
        return out

    def player_rating(self, Q) -> float:
        """Simple, explainable live rating (6.0 baseline)."""
        if Q["group"] != "GK" and Q["passes"] + Q["shots"] + Q["tackles"] + Q["pressures"] == 0:
            return 6.0
        # all-round contribution, damped so a normal game lands around 6.5-7.5 (calibrated on the simulated season)
        perf = 0.15 * Q["key_passes"] + 0.6 * Q["xg"] + 0.4 * Q["xa"]
        perf += 0.12 * Q["shots_on_target"] + 0.10 * Q["tackles_won"] + 0.10 * Q["interceptions"]
        perf += 0.08 * Q["dribbles_complete"] + 0.05 * Q["aerials_won"] + 0.04 * Q["clearances"]
        perf += 0.04 * Q["progressive_passes"] + 0.03 * Q["progressive_carries"] + 0.05 * Q["passes_into_box"]
        perf += 0.004 * Q["passes_complete"] - 0.015 * (Q["passes"] - Q["passes_complete"]) - 0.06 * Q["dispossessed"]
        if Q["group"] == "GK":
            perf += 0.35 * Q["saves"]
        # decisive moments count in full
        r = 6.0 + 0.55 * perf + 1.0 * Q["goals"] + 0.6 * Q["assists"] - 0.4 * Q["yellow"] - 1.5 * Q["red"]
        if Q["group"] == "GK":
            r -= 0.30 * Q["goals_conceded"]
        return round(max(3.0, min(10.0, r)), 1)

    def player_view(self, pid):
        Q = self.players[pid]
        v = {k: (round(v, 3) if isinstance(v, float) else v) for k, v in Q.items() if k != "difficulty_sum"}
        v["pass_accuracy_pct"] = round(100 * Q["passes_complete"] / Q["passes"], 1) if Q["passes"] else None
        v["avg_pass_difficulty"] = round(Q["difficulty_sum"] / Q["passes"], 1) if Q["passes"] and Q["difficulty_sum"] else None
        v["rating"] = self.player_rating(Q)
        v["on_pitch"] = pid in self.on_pitch[Q["side"]]
        return v

    def team_view(self, side):
        T = self.teams[side]
        v = {k: round(v, 3) for k, v in T.items()}
        v["pass_accuracy_pct"] = round(100 * T["passes_complete"] / T["passes"], 1) if T["passes"] else None
        v["goals"] = self.score[side]
        return v

    def features(self) -> dict:
        """Model inputs, always from the home team's perspective."""
        minute_f = min(self.t / 60.0, 98.0)
        return {
            "minute": minute_f,
            "time_left": max(0.0, 95.0 - minute_f) / 95.0,
            "goal_diff": self.score["home"] - self.score["away"],
            "home_goals": self.score["home"],
            "away_goals": self.score["away"],
            "xg_diff": self.teams["home"]["xg"] - self.teams["away"]["xg"],
            "xg_diff_15": self.xg_15.sum["home"] - self.xg_15.sum["away"],
            "shots_diff_15": self.shots_15.sum["home"] - self.shots_15.sum["away"],
            "red_diff": self.reds["home"] - self.reds["away"],
            "strength_diff": self.strength["home"] - self.strength["away"],
            "momentum": self.momentum / 100.0,
            "tilt_10": (self.tilt_10.share("home") - 50) / 50,
            "poss_5": (self.poss_5.share("home") - 50) / 50,
        }

    def _series_point(self):
        p = {"minute": self.minute, "t_min": round(self.t / 60.0, 2), "score": [self.score["home"], self.score["away"]],
             "xg": [round(self.teams["home"]["xg"], 2), round(self.teams["away"]["xg"], 2)],
             "momentum": round(self.momentum, 1), "chaos": round(self.chaos, 1),
             "possession_last5": self.possession()["last5"], "field_tilt_last10": self.field_tilt()["last10"]}
        if self.win_prob:
            p["win_prob"] = {k: round(v, 3) for k, v in self.win_prob.items()}
        return p

    def snapshot(self, include_players=True) -> dict:
        snap = {
            "match_id": self.match_id, "period": self.period, "clock": self.clock,
            "display_minute": self.display_minute, "finished": self.finished,
            "score": dict(self.score),
            "teams": {s: self.team_view(s) for s in SIDES},
            "possession": self.possession(), "field_tilt": self.field_tilt(), "ppda": self.ppda(),
            "momentum": round(self.momentum, 1), "chaos": round(self.chaos, 1),
            "win_prob": {k: round(v, 3) for k, v in self.win_prob.items()} if self.win_prob else None,
            "next_goal": {k: round(v, 3) for k, v in self.next_goal.items()} if self.next_goal else None,
            "top_speed": self.top_speed,
            "series": self.series,
        }
        if include_players:
            snap["players"] = {pid: self.player_view(pid) for pid, Q in self.players.items()
                               if pid in self.on_pitch[Q["side"]] or Q.get("minutes_off") is not None
                               or Q["passes"] or Q["shots"]}
        return snap

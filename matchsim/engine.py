"""Event-level football match simulator.

A possession-chain engine: on every touch the ball carrier may be pressed, then
chooses an action (carry + pass, dribble, cross, shot, clearance) whose outcome
depends on player attributes, tactical style, spatial context computed from both
teams' shapes, fatigue, a latent momentum process and a latent "chaos" level.

Output is a list of time-stamped, football-realistic events plus metadata and a
hidden ground-truth timeline (momentum, chaos, tactical intent) that downstream
explainability models can be validated against.

Coordinate convention (StatsBomb-like): every event location is given in the
ACTING team's attacking frame, x in [0,105] toward the opponent goal, y in [0,68]
from the left touchline to the right touchline when facing that goal. Each event
also carries `location_abs`, a fixed broadcast frame where x=0 is the left goal
line on the TV picture and the home team attacks right in the first half.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from .league import Club, Player, FORMATIONS, ROLE_GROUP

L, W = 105.0, 68.0
GOAL_Y = 34.0
POST_HALF = 3.66
BOX_X = 88.5
BOX_Y0, BOX_Y1 = 13.84, 54.16
SCHEMA_VERSION = "1.0"

# mean running speed (m/s over the whole match) and sprint rate (per minute)
RUN_RATE = {"GK": 0.92, "CB": 1.70, "FB": 1.84, "DM": 1.95, "CM": 2.00, "WM": 1.90,
            "AM": 1.89, "W": 1.80, "ST": 1.74}
SPRINT_RATE = {"GK": 0.005, "CB": 0.09, "FB": 0.21, "DM": 0.11, "CM": 0.14, "WM": 0.20,
               "AM": 0.18, "W": 0.25, "ST": 0.23}
ATTACK_GROUPS = {"ST", "W", "AM"}

WEATHER = [("clear", 0.0), ("cloudy", 0.0), ("light_rain", 0.12), ("heavy_rain", 0.30), ("windy", 0.18)]

REFEREES = [("Martin Halloway", "ENG"), ("Javier Ordóñez", "ESP"), ("Clément Vasseur", "FRA"),
            ("Tobias Rennert", "GER"), ("Luca Ferrandi", "ITA"), ("Rui Bettencourt", "POR"),
            ("Pieter Ruijsdael", "NED"), ("Grace Adeyemi-Holt", "ENG")]


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def sigmoid(z):
    return 1.0 / (1.0 + math.exp(-z))


def shot_geometry(x, y):
    dist = math.hypot(L - x, GOAL_Y - y)
    a1 = math.atan2(GOAL_Y - POST_HALF - y, L - x)
    a2 = math.atan2(GOAL_Y + POST_HALF - y, L - x)
    angle = abs(a2 - a1)
    return dist, angle


def expected_goals(x, y, body="foot", big_chance=False, pressed=False, pattern="regular_play",
                   direct_fk=False, penalty=False):
    """Simple logistic xG model on distance and goal-mouth angle."""
    if penalty:
        return 0.78
    dist, angle = shot_geometry(x, y)
    z = -1.45 + 1.60 * angle - 0.11 * dist
    if body == "head":
        z -= 0.95
    if big_chance:
        z += 0.50
    if pressed:
        z -= 0.30
    if pattern == "from_counter":
        z += 0.25
    if direct_fk:
        z = -2.9 + 0.6 * angle
    return clamp(sigmoid(z), 0.005, 0.95)


@dataclass
class TeamState:
    club: Club
    side: str                         # "home" / "away"
    on_pitch: list = field(default_factory=list)
    bench: list = field(default_factory=list)
    role_of: dict = field(default_factory=dict)       # player_id -> role
    base: dict = field(default_factory=dict)          # role -> (x, y)
    style: dict = field(default_factory=dict)         # live tactical style (mutable)
    stamina: dict = field(default_factory=dict)       # player_id -> 0..100
    yellow: set = field(default_factory=set)
    sent_off: set = field(default_factory=set)
    subs_used: int = 0
    sub_windows: int = 0
    pending_subs: int = 0
    forced_sub: list = field(default_factory=list)
    unused: list = field(default_factory=list)
    goals: int = 0
    phys: dict = field(default_factory=dict)          # player_id -> physical accumulators
    possession_s: float = 0.0
    minutes: dict = field(default_factory=dict)       # player_id -> [on_min, off_min]

    @property
    def id(self):
        return self.club.club_id

    def outfield(self):
        return [p for p in self.on_pitch if self.role_of[p.player_id] != "GK"]

    def gk(self):
        for p in self.on_pitch:
            if self.role_of[p.player_id] == "GK":
                return p
        return self.on_pitch[0]


class MatchEngine:
    def __init__(self, home: Club, away: Club, seed: int = 1, match_id: str | None = None,
                 kickoff_utc: str = "2026-10-24T15:00:00Z", competition: dict | None = None,
                 pre_match: dict | None = None, rotation: float = 0.15):
        self.rng = random.Random(seed)
        self.seed = seed
        self.match_id = match_id or f"M{seed:06d}"
        self.kickoff_utc = kickoff_utc
        self.competition = competition or {"name": "Aurora League", "season": "2026/27", "matchday": 1}
        self.pre_match = pre_match or {}
        self.home = self._init_team(home, "home", rotation)
        self.away = self._init_team(away, "away", rotation)
        self.events: list[dict] = []
        self.period = 1
        self.t = 0.0
        self.period_offset = 0.0           # continuous match time at start of the period
        self.poss: TeamState = self.home
        self.carrier: Player | None = None
        self.bx, self.by = 52.5, 34.0
        self.pattern = "from_kick_off"
        self.counter = 0
        self.possession_id = 0
        self.poss_start_t = 0.0
        self.poss_passes = 0
        self.poss_start_x = 52.5
        self.last_pass = None
        self.home_adv = 0.12               # long-run momentum level for the home side
        self.mom = 0.0                     # + favours home
        self.chaos = 0.15
        self.next_minute = 1
        self.gt_timeline: list[dict] = []
        self.period_counts = {"subs": 0, "goals": 0, "cards": 0, "injuries": 0}
        w = self.rng.choices(WEATHER, [0.35, 0.3, 0.17, 0.06, 0.12])[0]
        self.weather = {"condition": w[0], "temp_c": round(self.rng.uniform(4, 24), 1),
                        "wind_kmh": round(self.rng.uniform(25, 45) if w[0] == "windy" else self.rng.uniform(2, 18), 1),
                        "_penalty": w[1]}
        ref = self.rng.choice(REFEREES)
        self.referee = {"name": ref[0], "nationality": ref[1],
                        "strictness": round(self.rng.uniform(0.35, 0.85), 2)}
        # home attacks right (toward abs x=105) in period 1
        self.home_attacks_right_p1 = True

    # ------------------------------------------------------------------ setup
    def _init_team(self, club: Club, side: str, rotation: float) -> TeamState:
        ts = TeamState(club=club, side=side, style=dict(club.style))
        roles = FORMATIONS[club.formation]
        starters = list(club.squad[:11])
        bench = list(club.squad[11:])
        # light rotation: swap a few starters with same-group bench players
        for i, p in enumerate(starters):
            if p.group == "GK" or self.rng.random() > rotation:
                continue
            alts = [b for b in bench if b.group == p.group]
            if alts:
                b = self.rng.choice(alts)
                bench.remove(b)
                bench.append(p)
                starters[i] = b
        for (role, x, y), p in zip(roles, starters):
            ts.role_of[p.player_id] = role
            ts.base[role] = (x, y)
        ts.on_pitch = starters
        ts.bench = bench
        for p in club.squad:
            ts.stamina[p.player_id] = 100.0
            ts.phys[p.player_id] = {"distance_m": 0.0, "hi_run_m": 0.0, "sprints": 0, "top_speed_kmh": 0.0}
        for p in starters:
            ts.minutes[p.player_id] = [0, None]
        return ts

    def other(self, ts: TeamState) -> TeamState:
        return self.away if ts is self.home else self.home

    def m_for(self, ts: TeamState) -> float:
        return self.mom if ts is self.home else -self.mom

    # ---------------------------------------------------------------- geometry
    def attacks_right(self, ts: TeamState) -> bool:
        home_right = self.home_attacks_right_p1 if self.period == 1 else not self.home_attacks_right_p1
        return home_right if ts is self.home else not home_right

    def to_abs(self, ts: TeamState, x, y):
        if self.attacks_right(ts):
            return round(x, 1), round(y, 1)
        return round(L - x, 1), round(W - y, 1)

    def shape_pos(self, ts: TeamState, p: Player, ball_x, ball_y, in_poss=True, jitter=3.0):
        role = ts.role_of[p.player_id]
        bx, by = ts.base[role]
        st = ts.style
        if in_poss:
            if role == "GK":
                x = 5 + max(0.0, ball_x - 35) * 0.22
                y = 34 + (ball_y - 34) * 0.1
            else:
                x = bx + (ball_x - 50) * 0.55 + (st["line_height"] - 0.5) * 6
                if x > 86:      # attackers hold the offside line / edge of the box
                    x = 86 + (x - 86) * 0.35
                y = 34 + (by - 34) * (0.85 + 0.3 * st["width"]) + (ball_y - 34) * 0.15
                if ROLE_GROUP[role] in ("W", "WM") and ball_x > 70:   # wide forwards attack the box
                    y = 34 + (y - 34) * (0.62 + 0.25 * st["width"])
        else:
            if role == "GK":
                x = 3 + max(0.0, ball_x - 50) * 0.18
                y = 34 + (ball_y - 34) * 0.15
            else:
                x = 6 + (bx - 5) * 0.42 + st["line_height"] * 14 + (ball_x - 50) * 0.45
                y = 34 + (by - 34) * 0.7 + (ball_y - 34) * 0.35
        if jitter:
            x += self.rng.gauss(0, jitter)
            y += self.rng.gauss(0, jitter)
        return clamp(x, 1.0, 104.0), clamp(y, 1.0, 67.0)

    def defender_positions(self, dfn: TeamState, x, y):
        """Defending players' positions converted into the attacking team's frame."""
        out = []
        for p in dfn.on_pitch:
            dx, dy = self.shape_pos(dfn, p, L - x, W - y, in_poss=False, jitter=2.5)
            out.append((p, L - dx, W - dy))
        return out

    def nearest_defender(self, dfn: TeamState, x, y, exclude_gk=True):
        best, bd = None, 1e9
        for p, px, py in self.defender_positions(dfn, x, y):
            if exclude_gk and dfn.role_of[p.player_id] == "GK":
                continue
            d = math.hypot(px - x, py - y)
            if d < bd:
                best, bd = p, d
        return best, bd

    @staticmethod
    def _seg_dist(px, py, ax, ay, bx, by):
        vx, vy = bx - ax, by - ay
        L2 = vx * vx + vy * vy
        if L2 == 0:
            return math.hypot(px - ax, py - ay), 0.0
        t = clamp(((px - ax) * vx + (py - ay) * vy) / L2, 0.0, 1.0)
        return math.hypot(px - (ax + t * vx), py - (ay + t * vy)), t

    # ------------------------------------------------------------------ timing
    def match_time(self):
        return round(self.period_offset + self.t, 2)

    def clock(self, t=None):
        t = self.t if t is None else t
        base = 0 if self.period == 1 else 45 * 60
        total = base + t
        mm, ss = int(total // 60), int(total % 60)
        reg_end = 45 if self.period == 1 else 90
        if mm >= reg_end:
            display = f"{reg_end}+{mm - reg_end + 1}'"
        else:
            display = f"{mm + 1}'"
        return f"{mm:02d}:{ss:02d}", mm, ss, display

    # ------------------------------------------------------------------ emit
    def emit(self, etype, ts: TeamState | None, player: Player | None, loc=None, end=None,
             outcome=None, details=None, t=None, dur=None):
        t = self.t if t is None else t
        clk, mm, ss, disp = self.clock(t)
        ev = {
            "event_id": f"{self.match_id}-{len(self.events) + 1:05d}",
            "match_id": self.match_id,
            "seq": None,
            "period": self.period,
            "t": round(t, 2),
            "match_time_s": round(self.period_offset + t, 2),
            "clock": clk, "minute": mm, "second": ss, "display_minute": disp,
            "type": etype,
            "team_id": ts.id if ts else None,
            "team_side": ts.side if ts else None,
            "player_id": player.player_id if player else None,
            "player_name": player.short_name if player else None,
            "shirt": player.shirt if player else None,
            "possession_id": self.possession_id,
            "possession_team_id": self.poss.id if self.poss else None,
            "play_pattern": self.pattern,
            "location": [round(loc[0], 1), round(loc[1], 1)] if loc else None,
            "location_abs": list(self.to_abs(ts, *loc)) if (loc and ts) else None,
            "end_location": [round(end[0], 1), round(end[1], 1)] if end else None,
            "end_location_abs": list(self.to_abs(ts, *end)) if (end and ts) else None,
            "duration_s": round(dur, 2) if dur is not None else None,
            "outcome": outcome,
            "score": {"home": self.home.goals, "away": self.away.goals},
            "details": details or {},
        }
        self.events.append(ev)
        return ev

    # ------------------------------------------------------------ possession
    def change_possession(self, new: TeamState, carrier: Player, x, y, reason: str,
                          pattern: str = "regular_play", allow_counter=True):
        old = self.poss
        dur = self.t - self.poss_start_t
        self.emit("possession_change", new, carrier, loc=(x, y), details={
            "from_team_id": old.id, "to_team_id": new.id, "reason": reason,
            "previous_possession": {"possession_id": self.possession_id,
                                    "duration_s": round(max(dur, 0.0), 1),
                                    "passes": self.poss_passes,
                                    "start_x": round(self.poss_start_x, 1),
                                    "end_x_in_own_frame": round(L - x, 1)}})
        self.possession_id += 1
        self.poss = new
        self.carrier = carrier
        self.bx, self.by = x, y
        self.poss_start_t = self.t
        self.poss_passes = 0
        self.poss_start_x = x
        self.last_pass = None
        self.pattern = pattern
        self.counter = 0
        if allow_counter and pattern == "regular_play" and x < 60:
            opp_line = old.style["line_height"]
            p_counter = (0.06 + 0.30 * new.style["directness"]) * (0.4 + opp_line) * (1 + 0.5 * self.chaos)
            if self.rng.random() < p_counter:
                self.counter = self.rng.randint(2, 5)
                self.pattern = "from_counter"

    def spend(self, seconds, in_play=True):
        self.t += seconds
        if in_play:
            self.poss.possession_s += seconds
        self.tick()

    def dead(self, seconds):
        """Dead-ball time; substitutions happen here."""
        self.t += seconds
        self.tick()
        for ts in (self.home, self.away):
            if ts.forced_sub or ts.pending_subs:
                self.make_subs(ts)

    # ------------------------------------------------------------ minute tick
    def tick(self):
        while self.t >= self.next_minute * 60:
            self.minute_update(self.next_minute)
            self.next_minute += 1

    def minute_update(self, m_in_period):
        abs_min = m_in_period + (45 if self.period == 2 else 0)
        rng = self.rng
        # latent processes
        self.mom = clamp(0.90 * self.mom + 0.1 * (self.home_adv + 0.35 * self.quality(self.home)) + rng.gauss(0, 0.08), -1, 1)
        base_chaos = 0.12 + 0.12 * (self.home.style["press"] + self.away.style["press"]) / 2
        late = 0.06 if abs_min > 78 and abs(self.home.goals - self.away.goals) <= 1 else 0
        self.chaos = clamp(0.88 * self.chaos + 0.12 * base_chaos + late + rng.gauss(0, 0.02), 0, 1)
        # tactical reactions (hidden intent)
        for ts in (self.home, self.away):
            diff = ts.goals - self.other(ts).goals
            base = ts.club.style
            if abs_min >= 55 and diff < 0:
                push = min(1.0, (abs_min - 50) / 35) * (1 if diff == -1 else 0.7)
                ts.style["press"] = clamp(base["press"] + 0.18 * push, 0, 1)
                ts.style["directness"] = clamp(base["directness"] + 0.22 * push, 0, 1)
                ts.style["line_height"] = clamp(base["line_height"] + 0.15 * push, 0, 1)
                ts.style["tempo"] = clamp(base["tempo"] + 0.15 * push, 0, 1)
            elif abs_min >= 60 and diff > 0:
                sit = min(1.0, (abs_min - 55) / 30)
                ts.style["press"] = clamp(base["press"] - 0.15 * sit, 0, 1)
                ts.style["line_height"] = clamp(base["line_height"] - 0.18 * sit, 0, 1)
                ts.style["possession"] = clamp(base["possession"] - 0.05 * sit, 0, 1)
            # substitution planning
            if abs_min >= 55 and ts.subs_used < 5 and ts.sub_windows < 3 and not ts.pending_subs:
                p = 0.045 + (0.04 if diff < 0 else 0) + (0.03 if abs_min > 70 else 0)
                if rng.random() < p:
                    ts.pending_subs = min(5 - ts.subs_used, rng.choice([1, 1, 2, 2, 3]))
        # physical model
        for ts in (self.home, self.away):
            in_poss = ts is self.poss
            for p in ts.on_pitch:
                g = ROLE_GROUP.get(ts.role_of[p.player_id], p.group)
                stam = ts.stamina[p.player_id]
                intensity = 1.0 + 0.18 * (ts.style["press"] - 0.5) + 0.10 * self.chaos + \
                    0.06 * (ts.style["tempo"] - 0.5) + rng.gauss(0, 0.06)
                intensity *= 0.80 + 0.20 * stam / 100
                dist = RUN_RATE[g] * 60 * intensity
                ph = ts.phys[p.player_id]
                ph["distance_m"] += dist
                ph["hi_run_m"] += dist * clamp(0.07 + 0.04 * (g in ("W", "FB", "ST")) + rng.gauss(0, 0.02), 0.01, 0.2)
                lam = 0.8 * SPRINT_RATE[g] * (0.7 + 0.3 * stam / 100) * (1.1 if (in_poss and g in ATTACK_GROUPS) else 1.0)
                n = self._poisson(lam)
                for _ in range(n):
                    self.emit_sprint(ts, p, t=(m_in_period - 1) * 60 + rng.uniform(0, 59.9))
                drain = 0.95 * (1.15 - (p.attrs["stamina"] - 50) / 110) * intensity
                ts.stamina[p.player_id] = clamp(stam - drain, 5, 100)
        # snapshots every 5 minutes
        if m_in_period % 5 == 0:
            for ts in (self.home, self.away):
                self.emit("physical_snapshot", ts, None, t=m_in_period * 60 - 0.01, details={
                    "players": [{"player_id": p.player_id, "player_name": p.short_name,
                                 "distance_m": round(ts.phys[p.player_id]["distance_m"]),
                                 "hi_run_m": round(ts.phys[p.player_id]["hi_run_m"]),
                                 "sprints": ts.phys[p.player_id]["sprints"],
                                 "top_speed_kmh": round(ts.phys[p.player_id]["top_speed_kmh"], 1),
                                 "stamina_pct": round(ts.stamina[p.player_id])}
                                for p in ts.on_pitch]})
        self.gt_timeline.append({
            "minute": abs_min, "period": self.period,
            "momentum_home": round(self.mom, 3), "chaos": round(self.chaos, 3),
            "home_style": {k: round(v, 2) for k, v in self.home.style.items()},
            "away_style": {k: round(v, 2) for k, v in self.away.style.items()},
            "home_avg_stamina": round(sum(self.home.stamina[p.player_id] for p in self.home.on_pitch) / len(self.home.on_pitch), 1),
            "away_avg_stamina": round(sum(self.away.stamina[p.player_id] for p in self.away.on_pitch) / len(self.away.on_pitch), 1),
            "score": [self.home.goals, self.away.goals],
        })

    def _poisson(self, lam):
        l, k, p = math.exp(-lam), 0, 1.0
        while True:
            p *= self.rng.random()
            if p < l:
                return k
            k += 1

    def emit_sprint(self, ts, p, t=None, top=None, dist=None, loc=None):
        rng = self.rng
        top = top or clamp(24.5 + (p.attrs["pace"] - 50) * 0.21 + rng.gauss(0, 1.3), 24.0, 36.8)
        top *= 0.94 + 0.06 * ts.stamina[p.player_id] / 100
        dist = dist or rng.uniform(12, 45)
        if loc is None and p in ts.on_pitch:
            if ts is self.poss:
                loc = self.shape_pos(ts, p, self.bx, self.by, in_poss=True, jitter=4)
            else:
                loc = self.shape_pos(ts, p, L - self.bx, W - self.by, in_poss=False, jitter=4)
        ph = ts.phys[p.player_id]
        ph["sprints"] += 1
        ph["top_speed_kmh"] = max(ph["top_speed_kmh"], top)
        self.emit("sprint", ts, p, loc=loc, t=t, dur=dist / (top / 3.6 * 0.85), details={
            "top_speed_kmh": round(top, 1), "distance_m": round(dist, 1),
            "session_top_speed_kmh": round(ph["top_speed_kmh"], 1),
            "sprint_count": ph["sprints"]})

    # ------------------------------------------------------------ substitutions
    def make_subs(self, ts: TeamState):
        n_planned = ts.pending_subs
        forced = list(ts.forced_sub)
        ts.forced_sub = []
        if ts.subs_used >= 5 or (ts.sub_windows >= 3 and not forced):
            ts.pending_subs = 0
            return
        diff = ts.goals - self.other(ts).goals
        outs = list(forced)
        cands = [p for p in ts.outfield() if p not in outs]
        cands.sort(key=lambda p: ts.stamina[p.player_id] - (25 if p.player_id in ts.yellow else 0)
                   - (8 if p.group in ATTACK_GROUPS else 0))
        while len(outs) < len(forced) + n_planned and cands:
            outs.append(cands.pop(0))
        ts.pending_subs = 0
        ts.sub_windows += 1
        for off in outs:
            if ts.subs_used >= 5:
                break
            role = ts.role_of[off.player_id]
            g = ROLE_GROUP[role]
            want = [g]
            if diff < 0 and g in ("DM", "CM", "CB", "FB"):
                want = ["ST", "W", "AM"] + want       # attacking change when chasing
            elif diff > 0 and g in ATTACK_GROUPS:
                want = ["CM", "DM", "WM"] + want      # shore up when leading
            fallback = {"GK": ["GK"], "CB": ["CB", "DM"], "FB": ["FB", "WM", "CB"], "DM": ["DM", "CM"],
                        "CM": ["CM", "DM", "AM"], "WM": ["WM", "W", "FB"], "AM": ["AM", "CM", "W"],
                        "W": ["W", "WM", "AM"], "ST": ["ST", "W", "AM"]}[g]
            on = None
            for grp in want + fallback:
                opts = [b for b in ts.bench if b.group == grp]
                if opts:
                    on = max(opts, key=lambda b: b.overall())
                    break
            if on is None:
                if g == "GK":
                    continue
                opts = [b for b in ts.bench if b.group != "GK"]
                if not opts:
                    continue
                on = opts[0]
            ts.bench.remove(on)
            ts.on_pitch[ts.on_pitch.index(off)] = on
            ts.role_of[on.player_id] = role
            ts.stamina[on.player_id] = 100.0
            clk_min = self.clock()[1]
            ts.minutes[off.player_id][1] = clk_min
            ts.minutes[on.player_id] = [clk_min, None]
            ts.subs_used += 1
            self.period_counts["subs"] += 1
            if self.carrier is off:
                self.carrier = on
            self.emit("substitution", ts, off, details={
                "player_off_id": off.player_id, "player_off_name": off.short_name,
                "player_on_id": on.player_id, "player_on_name": on.short_name,
                "player_on_shirt": on.shirt, "role": role,
                "reason": "injury" if off in forced else "tactical",
                "player_off_stamina_pct": round(ts.stamina[off.player_id]),
                "subs_used": ts.subs_used})
            self.t += self.rng.uniform(8, 20)

    # ------------------------------------------------------------ helpers
    def strength(self, ts):
        xi = ts.on_pitch
        return sum(p.overall() for p in xi) / 11.0      # missing players (red cards) count as zero

    def quality(self, ts):
        """Relative squad quality in roughly [-1, 1]: 10 overall points = 1.0."""
        return clamp((self.strength(ts) - self.strength(self.other(ts))) / 10.0, -1.5, 1.5)

    def fatigue(self, ts, p):
        return max(0.0, (60 - ts.stamina[p.player_id]) / 60)

    def press_prob(self, att, dfn, x):
        st = dfn.style
        # high press is most visible when the opponent builds from the back
        zone = 1.25 if x < 35 else 1.0 if x < 70 else 0.9 if x < BOX_X else 1.5
        p = (0.08 + 0.25 * st["press"] * zone) * (1 + 0.6 * self.chaos) + 0.06 * self.m_for(dfn)
        return clamp(p, 0.03, 0.7)

    def pick(self, ts, groups, exclude=None, key="overall"):
        opts = [p for p in ts.on_pitch if ROLE_GROUP[ts.role_of[p.player_id]] in groups and p is not exclude]
        if not opts:
            opts = [p for p in ts.outfield() if p is not exclude] or ts.on_pitch
        if key == "overall":
            return self.rng.choice(opts)
        return max(opts, key=lambda p: p.attrs[key] + self.rng.gauss(0, 4))

    def side_player(self, ts, y, groups=("FB", "WM", "W")):
        side = "L" if y < 34 else "R"
        opts = [p for p in ts.on_pitch if ROLE_GROUP[ts.role_of[p.player_id]] in groups
                and ts.role_of[p.player_id].startswith(side)]
        return self.rng.choice(opts) if opts else self.pick(ts, groups)

    # ------------------------------------------------------------ match flow
    def run(self) -> dict:
        self.emit("match_start", None, None, details={"home_team_id": self.home.id, "away_team_id": self.away.id})
        self.play_period(1)
        p1_len = self.t
        self.period_offset = p1_len
        self.period = 2
        self.t = 0.0
        self.next_minute = 1
        for ts in (self.home, self.away):     # half-time recovery
            for p in ts.on_pitch:
                ts.stamina[p.player_id] = min(100, ts.stamina[p.player_id] + 8)
            if self.rng.random() < 0.15 and ts.subs_used < 5:
                ts.pending_subs = 1
        self.play_period(2)
        clk_min = self.clock()[1]
        for ts in (self.home, self.away):
            for pid, mm in ts.minutes.items():
                if mm[1] is None:
                    mm[1] = clk_min + 1
        self.emit("match_end", None, None, details={"final_score": {"home": self.home.goals, "away": self.away.goals}})
        self.events.sort(key=lambda e: (e["match_time_s"], int(e["event_id"].rsplit("-", 1)[1])))
        for i, e in enumerate(self.events, start=1):
            e["seq"] = i
        return {"metadata": self.metadata(), "events": self.events, "ground_truth": self.ground_truth()}

    def play_period(self, period):
        self.period_counts = {"subs": 0, "goals": 0, "cards": 0, "injuries": 0}
        starter = self.home if period == 1 else self.away
        self.emit("period_start", None, None, details={"period": period,
                                                        "home_attacks": "right" if self.attacks_right(self.home) else "left"})
        if period == 2:
            for ts in (self.home, self.away):
                if ts.pending_subs or ts.forced_sub:
                    self.make_subs(ts)
        self.kick_off(starter)
        reg = 45 * 60
        added = None
        while True:
            if added is None and self.t >= reg:
                pc = self.period_counts
                base = 1 if period == 1 else 3
                added = round(base + 0.35 * pc["subs"] + 0.5 * pc["goals"] + 0.25 * pc["cards"]
                              + 1.0 * pc["injuries"] + self.rng.gauss(0, 0.7))
                added = int(clamp(added, 1, 5 if period == 1 else 9))
                self.emit("added_time", None, None, details={"minutes": added, "period": period})
            if added is not None and self.t >= reg + added * 60:
                # let a promising attack finish (up to 40s)
                if not (self.bx > 70 and self.t < reg + added * 60 + 40):
                    break
            self.step()
        self.emit("period_end", None, None, details={"period": period})

    def kick_off(self, ts: TeamState):
        st = self.pick(ts, ("ST", "AM"))
        mid = self.pick(ts, ("CM", "DM", "AM"), exclude=st)
        if self.poss is not ts:
            self.possession_id += 1
        self.poss = ts
        self.poss_start_t = self.t
        self.poss_passes = 0
        self.pattern = "from_kick_off"
        self.counter = 0
        self.emit("kick_off", ts, st, loc=(52.5, 34.0))
        tx, ty = 52.5 - self.rng.uniform(6, 14), 34 + self.rng.uniform(-8, 8)
        self.pass_event(ts, st, mid, 52.5, 34.0, tx, ty, "ground", "kick_off", False, 0, 9.0, True)
        self.carrier, self.bx, self.by = mid, tx, ty
        self.spend(1.2)

    # ------------------------------------------------------------ one touch cycle
    def step(self):
        att, dfn = self.poss, self.other(self.poss)
        p = self.carrier
        if p not in att.on_pitch:
            p = self.carrier = self.rng.choice(att.outfield())
        x, y = self.bx, self.by
        rng = self.rng

        pressed = False
        if rng.random() < self.press_prob(att, dfn, x):
            presser, d = self.nearest_defender(dfn, x, y)
            if presser is not None:
                pressed = True
                pdur = rng.uniform(0.6, 2.2)
                if rng.random() < 0.012 + 0.012 * self.chaos:
                    self.emit("pressure", dfn, presser, loc=(L - x, W - y), dur=pdur,
                              details={"pressed_player_id": p.player_id, "pressed_player_name": p.short_name,
                                       "distance_to_ball_m": 0.5, "counterpress": False})
                    self.foul(att, dfn, p, presser, x, y)
                    return
                p_win = 0.03 + 0.04 * dfn.style["press"] + (0.06 if x >= BOX_X else 0)
                if rng.random() < p_win:
                    self.resolve_tackle(att, dfn, p, presser, x, y)
                    if self.poss is not att:
                        return
                self.emit("pressure", dfn, presser, loc=(L - x, W - y), dur=pdur,
                          details={"pressed_player_id": p.player_id, "pressed_player_name": p.short_name,
                                   "distance_to_ball_m": round(clamp(d * 0.35, 0.5, 4.0), 1),
                                   "counterpress": (self.t - self.poss_start_t) < 5})

        g = ROLE_GROUP[att.role_of[p.player_id]]
        xg_here = expected_goals(x, y)
        in_box = x >= BOX_X and BOX_Y0 <= y <= BOX_Y1
        wide = y < 15 or y > 53

        p_shot = 0.0
        if in_box:
            p_shot = clamp(0.045 + 0.33 * xg_here, 0, 0.32) * (1.2 if g in ATTACK_GROUPS else 0.7)
            if self.counter:
                p_shot *= 1.25
        elif x > 72 and 14 < y < 54:
            p_shot = (0.018 + 0.021 * (x > 80)) * (1.4 if p.attrs["shot_power"] > 80 else 1.0) * (1.2 if g in ATTACK_GROUPS | {"CM"} else 0.6)
        p_cross = 0.0
        if wide and x > 82:
            p_cross = 0.28
        elif wide and x > 70:
            p_cross = 0.06
        p_drib = clamp(0.006 + (p.attrs["dribbling"] - 70) * 0.001, 0.002, 0.04)
        if g in ("W", "AM") and x > 60:
            p_drib *= 1.8
        p_clear = 0.0
        if x < 22 and pressed:
            p_clear = 0.35
        elif x < 32 and pressed:
            p_clear = 0.06

        r = rng.random()
        if r < p_shot:
            self.do_shot(att, dfn, p, x, y, pressed)
        elif r < p_shot + p_cross:
            self.do_cross(att, dfn, p, x, y, pressed)
        elif r < p_shot + p_cross + p_clear:
            self.do_clearance_by_attacker(att, dfn, p, x, y)
        elif r < p_shot + p_cross + p_clear + p_drib:
            self.do_dribble(att, dfn, p, x, y, pressed)
        else:
            self.do_carry_and_pass(att, dfn, p, x, y, pressed)
        if self.counter:
            self.counter -= 1
            if self.counter == 0 and self.pattern == "from_counter":
                self.pattern = "regular_play"

    # ------------------------------------------------------------ actions
    def do_carry_and_pass(self, att, dfn, p, x, y, pressed):
        rng = self.rng
        st = att.style
        tempo_f = 1.30 - 0.45 * st["tempo"]
        if self.counter:
            tempo_f *= 0.65
        # ---- carry
        if rng.random() < (0.30 if pressed else 0.62):
            ln = min(rng.expovariate(1 / (9 if self.counter else 5.0)), 35 if self.counter else 22)
            if x >= BOX_X - 4:
                ln = min(ln * 0.5, 6.0)
            ang = rng.gauss(0, 0.55) if x < 92 else rng.gauss(math.copysign(1.2, 34 - y), 0.5)
            ex = clamp(x + ln * math.cos(ang), 1, 103)
            ey = clamp(y + ln * math.sin(ang), 1, 67)
            speed = rng.uniform(4.5, 7.5) if self.counter or ln > 12 else rng.uniform(2.0, 4.5)
            dur = max(0.6, ln / speed)
            # challenge during carry
            p_tk = 0.025 + (0.065 if pressed else 0) + 0.025 * self.chaos
            if rng.random() < p_tk:
                defender, _ = self.nearest_defender(dfn, ex, ey)
                self.emit("carry", att, p, loc=(x, y), end=(ex, ey), dur=dur * 0.6,
                          details={"distance_m": round(ln * 0.6, 1), "progressive_m": round((ex - x) * 0.6, 1)})
                self.spend(dur * 0.6)
                self.resolve_tackle(att, dfn, p, defender, ex, ey)
                return
            self.emit("carry", att, p, loc=(x, y), end=(ex, ey), dur=dur,
                      details={"distance_m": round(ln, 1), "progressive_m": round(ex - x, 1),
                               "speed_kmh": round(speed * 3.6, 1)})
            if self.counter and ln > 15:
                self.emit_sprint(att, p, loc=(x, y), dist=ln)
            self.spend(dur * tempo_f)
            x, y = ex, ey
            self.bx, self.by = x, y
            if x > 80:      # re-evaluate final-third options after the carry
                return
        # ---- pass
        recv, tx, ty, height, ptype = self.choose_pass(att, dfn, p, x, y, pressed)
        self.attempt_pass(att, dfn, p, recv, x, y, tx, ty, height, ptype, pressed, tempo_f)

    def choose_pass(self, att, dfn, p, x, y, pressed):
        rng = self.rng
        st = att.style
        m = self.m_for(att)
        directness = clamp(st["directness"] + 0.15 * m, 0, 1)
        # long ball / switch options
        p_long = 0.035 + 0.12 * directness + (0.15 if pressed and x < 35 else 0)
        if self.counter:
            p_long += 0.10
        if x < 75 and rng.random() < p_long:
            targets = [q for q in att.on_pitch if q is not p and ROLE_GROUP[att.role_of[q.player_id]] in ("ST", "W", "AM", "WM", "FB")]
            if targets:
                q = rng.choice(targets)
                tx, ty = self.shape_pos(att, q, x, y)
                if tx - x < 18 and rng.random() < 0.5:   # diagonal switch
                    ty = 68 - y + rng.gauss(0, 6)
                    tx = x + rng.uniform(5, 20)
                else:
                    tx = max(tx, x + rng.uniform(18, 40))
                return q, clamp(tx, 2, 103), clamp(ty, 1, 67), "high", "long_ball" if tx - x >= 18 else "switch"
        fwd = 0.25 + 0.9 * directness + (1.6 if self.counter else 0) + 0.25 * m
        recycle = 0.45 + 0.65 * st["possession"]
        best, weights = [], []
        for q in att.on_pitch:
            if q is p:
                continue
            qx, qy = self.shape_pos(att, q, x, y)
            d = math.hypot(qx - x, qy - y)
            if d < 4:
                continue
            dx = qx - x
            w = math.exp(-d / (13 + 8 * directness))
            w *= 1 + fwd * max(0.0, dx) / 12
            if dx < -4:
                w *= recycle * (1.3 if pressed else 1.0)
            role = att.role_of[q.player_id]
            if role == "GK":
                w *= 0.30 if x < 30 else 0.03
            best.append((q, qx, qy))
            weights.append(w)
        if not best:
            q = rng.choice([o for o in att.outfield() if o is not p])
            qx, qy = self.shape_pos(att, q, x, y)
            best, weights = [(q, qx + 6, qy)], [1.0]
        q, qx, qy = rng.choices(best, weights)[0]
        ptype = "ground_pass"
        dx = qx - x
        g = ROLE_GROUP[att.role_of[q.player_id]]
        if g in ("ST", "W", "AM") and dx > 8 and qx > 65 and rng.random() < 0.35 + 0.3 * (self.counter > 0):
            qx += rng.uniform(3, 9)                   # into space ahead of the runner
            ptype = "through_ball"
        ln = math.hypot(qx - x, qy - y)
        height = "ground"
        if ln > 32:
            height = "high" if rng.random() < 0.75 else "low"
        elif ln > 20:
            height = rng.choices(["ground", "low", "high"], [0.55, 0.25, 0.20])[0]
        return q, clamp(qx, 1, 104), clamp(qy, 1, 67), height, ptype

    def attempt_pass(self, att, dfn, p, recv, x, y, tx, ty, height, ptype, pressed, tempo_f=1.0,
                     restart=None):
        rng = self.rng
        ln = math.hypot(tx - x, ty - y)
        defs = self.defender_positions(dfn, x, y)
        lane = 0
        for dp, px, py in defs:
            if dfn.role_of[dp.player_id] == "GK":
                continue
            d, tt = self._seg_dist(px, py, x, y, tx, ty)
            if 0.12 < tt < 0.92 and d < (2.2 if height == "ground" else 1.0):
                lane += 1
        space = min(math.hypot(px - tx, py - ty) for _, px, py in defs)
        space = max(0.3, space + rng.gauss(0, 1.2))
        # offside: last outfield defender line in attacking frame
        line_x = max(px for dp, px, py in defs if dfn.role_of[dp.player_id] != "GK")
        line_x = max(line_x, 52.5)
        offside = False
        if restart not in ("throw_in", "corner", "goal_kick", "kick_off") and tx > line_x + 0.5 \
                and tx > 60 and tx - x > 5 and tx > line_x + 1.5:
            offside = rng.random() < clamp(0.005 + 0.008 * (tx - line_x), 0, 0.12)

        m = self.m_for(att)
        z = 3.55
        z -= 0.034 * max(0.0, ln - 8)
        z -= 0.85 if pressed else 0
        z -= 0.60 * lane
        z -= 0.55 if space < 2.5 else (-0.25 if space > 8 else 0)
        z -= {"ground": 0.0, "low": 0.35, "high": 0.85}[height]
        z -= 1.05 if (tx > BOX_X and BOX_Y0 - 3 < ty < BOX_Y1 + 3) else 0
        z -= 0.60 if ptype == "through_ball" else 0
        z += (p.attrs["passing"] - 75) * 0.045 + (p.attrs["vision"] - 75) * 0.012 * (ptype == "through_ball")
        z += 0.30 * m - 0.55 * self.chaos - 0.55 * self.fatigue(att, p) + 0.22 * self.quality(att)
        z -= self.weather["_penalty"] * (1.0 if height == "high" or ln > 25 else 0.5)
        if restart == "throw_in":
            z += 0.4
        if restart == "goal_kick" and height == "ground":
            z += 0.8
        p_ok = sigmoid(z)
        success = rng.random() < p_ok and not offside

        if height == "ground":
            v = 8.5 + ln * 0.32 + rng.gauss(0, 1.4)
        elif height == "low":
            v = 13 + ln * 0.22 + rng.gauss(0, 1.5)
        else:
            v = 14 + ln * 0.17 + rng.gauss(0, 1.6)
        v = clamp(v, 5.5, 34)
        flight = ln / v
        release_kmh = v * 3.6 * (1.18 if height == "ground" else 1.30)

        outcome = "complete" if success else ("offside" if offside else "incomplete")
        ev = self.pass_event(att, p, recv, x, y, tx, ty, height, ptype, pressed, lane, round(space, 1),
                             success, outcome=outcome, release_kmh=release_kmh, flight=flight,
                             restart=restart, p_ok=p_ok)
        self.spend(flight + 0.30 * tempo_f + (rng.uniform(0.2, 1.5) * tempo_f if not self.counter else 0.25))
        if success:
            self.poss_passes += 1
            self.last_pass = {"event": ev, "player": p, "t": self.t, "team": att}
            self.carrier, self.bx, self.by = recv, tx, ty
            if self.pattern not in ("from_counter",) and restart is None and self.poss_passes > 3:
                self.pattern = self.pattern if self.pattern == "regular_play" else "regular_play"
            if height == "high" and rng.random() < 0.12:
                dp, _ = self.nearest_defender(dfn, tx, ty)
                if dp:
                    self.aerial_duel(att, recv, dfn, dp, tx, ty, attacker_wins=True)
            return True
        if offside:
            self.emit("offside", att, recv, loc=(tx, ty), details={"pass_event_id": ev["event_id"],
                                                                   "defensive_line_x": round(line_x, 1)})
            dp = dfn.gk() if rng.random() < 0.5 else self.pick(dfn, ("CB",))
            self.change_possession(dfn, dp, L - tx, W - ty, "offside", "from_free_kick", allow_counter=False)
            self.dead(rng.uniform(10, 20))
            return False
        self.failed_pass(att, dfn, recv, x, y, tx, ty, height, lane)
        return False

    def pass_event(self, att, p, recv, x, y, tx, ty, height, ptype, pressed, lane, space, success,
                   outcome="complete", release_kmh=None, flight=None, restart=None, p_ok=None):
        ln = math.hypot(tx - x, ty - y)
        ang = math.degrees(math.atan2(ty - y, tx - x))
        prog = max(0.0, math.hypot(L - x, GOAL_Y - y) - math.hypot(L - tx, GOAL_Y - ty))
        if release_kmh is None:
            v = clamp(8.5 + ln * 0.32, 5.5, 34)
            release_kmh = v * 3.6 * 1.18
            flight = ln / v
        details = {
            "recipient_id": recv.player_id if recv else None,
            "recipient_name": recv.short_name if recv else None,
            "length_m": round(ln, 1), "angle_deg": round(ang, 1),
            "height": height, "pass_type": ptype if restart is None else restart,
            "body_part": "head" if height == "high" and self.rng.random() < 0.02 else
            ("right_foot" if p.foot != "left" else "left_foot"),
            "under_pressure": bool(pressed),
            "defenders_in_lane": lane,
            "receiver_space_m": space,
            "progressive_distance_m": round(prog, 1),
            "into_final_third": x < 70 <= tx,
            "into_box": not (x >= BOX_X and BOX_Y0 <= y <= BOX_Y1) and tx >= BOX_X and BOX_Y0 <= ty <= BOX_Y1,
            "ball_speed_kmh": round(release_kmh, 1),
            "flight_time_s": round(flight, 2),
            "switch": abs(ty - y) > 30,
            "cross": ptype == "cross",
            "key_pass": False, "assist": False,
        }
        if p_ok is not None:
            details["provider_completion_prob"] = round(p_ok, 3)
        return self.emit("pass", att, p, loc=(x, y), end=(tx, ty), outcome=outcome,
                         dur=flight, details=details)

    def failed_pass(self, att, dfn, recv, x, y, tx, ty, height, lane):
        rng = self.rng
        # ball out of play?
        p_out = 0.30 if height != "ground" else 0.10
        if tx > 101 or ty < 2 or ty > 66:
            p_out += 0.4
        if rng.random() < p_out:
            if tx > 98 and rng.random() < 0.7:
                self.emit("ball_out", att, None, loc=(min(tx, 105), ty), details={"restart": "goal_kick"})
                self.change_possession(dfn, dfn.gk(), 5.5, rng.choice([24.0, 44.0]), "out_of_play",
                                       "from_goal_kick", allow_counter=False)
                self.dead(rng.uniform(17, 30))
                self.goal_kick(dfn)
                return
            side_y = 0.0 if ty < 34 else 68.0
            ox = clamp(tx + rng.gauss(0, 4), 2, 103)
            self.emit("ball_out", att, None, loc=(ox, side_y), details={"restart": "throw_in"})
            thrower = self.side_player(dfn, W - side_y)
            self.change_possession(dfn, thrower, L - ox, W - side_y, "out_of_play", "from_throw_in",
                                   allow_counter=False)
            self.dead(rng.uniform(14, 28))
            self.throw_in(dfn)
            return
        # intercepted / recovered in play
        dp, _ = self.nearest_defender(dfn, (x + tx) / 2 if lane else tx, (y + ty) / 2 if lane else ty)
        if dp is None:
            dp = self.rng.choice(dfn.outfield())
        if height == "high" and rng.random() < 0.55:
            self.aerial_duel(att, recv, dfn, dp, tx, ty, attacker_wins=False)
            rx, ry = tx + rng.gauss(0, 3), ty + rng.gauss(0, 3)
        elif lane and rng.random() < 0.75:
            f = rng.uniform(0.35, 0.85)
            rx, ry = x + (tx - x) * f, y + (ty - y) * f
        else:
            rx, ry = tx, ty
        rx, ry = clamp(rx, 1, 104), clamp(ry, 1, 67)
        etype = "interception" if height != "high" and (lane or rng.random() < 0.05) else "ball_recovery"
        self.emit(etype, dfn, dp, loc=(L - rx, W - ry), outcome="won")
        self.change_possession(dfn, dp, L - rx, W - ry, etype)
        self.spend(rng.uniform(0.4, 1.2))

    def aerial_duel(self, att, ap, dfn, dp, x, y, attacker_wins):
        if ap is None or dp is None:
            return
        self.emit("aerial_duel", att, ap, loc=(x, y), outcome="won" if attacker_wins else "lost",
                  details={"opponent_id": dp.player_id})
        self.emit("aerial_duel", dfn, dp, loc=(L - x, W - y), outcome="lost" if attacker_wins else "won",
                  details={"opponent_id": ap.player_id})

    def resolve_tackle(self, att, dfn, p, dp, x, y, dribble_ev=None):
        rng = self.rng
        if dp is None:
            return
        foul_p = 0.19 + 0.10 * dfn.style["press"] + 0.08 * self.chaos + 0.06 * self.fatigue(dfn, dp)
        if dp.player_id in dfn.yellow:
            foul_p *= 0.55
        if rng.random() < foul_p:
            self.foul(att, dfn, p, dp, x, y)
            return
        win = sigmoid((dp.attrs["tackling"] - p.attrs["dribbling"]) / 9 + 0.55)
        if rng.random() < win:
            self.emit("tackle", dfn, dp, loc=(L - x, W - y), outcome="won",
                      details={"opponent_id": p.player_id, "opponent_name": p.short_name})
            if rng.random() < 0.8:
                self.change_possession(dfn, dp, L - x, W - y, "tackle")
            else:   # loose ball back to attackers
                pass
            self.spend(rng.uniform(0.5, 1.5))
        else:
            self.emit("tackle", dfn, dp, loc=(L - x, W - y), outcome="lost",
                      details={"opponent_id": p.player_id, "opponent_name": p.short_name})
            self.spend(rng.uniform(0.4, 1.0))

    def do_dribble(self, att, dfn, p, x, y, pressed):
        rng = self.rng
        dp, _ = self.nearest_defender(dfn, x, y)
        if dp is None:
            return self.do_carry_and_pass(att, dfn, p, x, y, pressed)
        z = (p.attrs["dribbling"] - dp.attrs["tackling"]) / 10 - 0.25 - 0.4 * self.fatigue(att, p) \
            + 0.2 * self.m_for(att)
        ok = rng.random() < sigmoid(z)
        ln = rng.uniform(4, 11)
        ang = rng.gauss(0, 0.5) if x < 88 else rng.gauss(math.copysign(1.0, 34 - y), 0.5)
        ex, ey = clamp(x + ln * math.cos(ang), 1, 104), clamp(y + ln * math.sin(ang), 1, 67)
        self.emit("dribble", att, p, loc=(x, y), end=(ex, ey) if ok else None,
                  outcome="complete" if ok else "incomplete",
                  details={"opponent_id": dp.player_id, "opponent_name": dp.short_name,
                           "under_pressure": pressed, "nutmeg": ok and rng.random() < 0.06})
        if ok:
            self.emit("dribbled_past", dfn, dp, loc=(L - x, W - y), details={"by_player_id": p.player_id})
            self.bx, self.by = ex, ey
            self.spend(rng.uniform(1.2, 2.5))
            if rng.random() < 0.12:
                d2, _ = self.nearest_defender(dfn, ex, ey)
                self.foul(att, dfn, p, d2 or dp, ex, ey)
        else:
            self.spend(rng.uniform(0.5, 1.2))
            self.resolve_tackle(att, dfn, p, dp, x, y)
            if self.poss is att:     # tackle lost or loose ball – dribbler keeps it
                pass

    def do_clearance_by_attacker(self, att, dfn, p, x, y):
        """Under pressure deep in own half: hoof it."""
        rng = self.rng
        tx, ty = clamp(x + rng.uniform(30, 55), 30, 100), clamp(y + rng.gauss(0, 14), 2, 66)
        self.emit("clearance", att, p, loc=(x, y), end=(tx, ty),
                  details={"body_part": "head" if rng.random() < 0.3 else "foot", "under_pressure": True})
        self.spend(rng.uniform(1.8, 3.0))
        tgt = self.pick(att, ("ST", "W", "AM"))
        dp, _ = self.nearest_defender(dfn, tx, ty)
        win = rng.random() < sigmoid((tgt.attrs["aerial"] - (dp.attrs["aerial"] if dp else 70)) / 10 - 0.6)
        self.aerial_duel(att, tgt, dfn, dp, tx, ty, attacker_wins=win)
        if win and rng.random() < 0.55:
            self.carrier, self.bx, self.by = tgt, tx, ty
            self.pattern = "regular_play"
        else:
            rec = dp or self.rng.choice(dfn.outfield())
            self.emit("ball_recovery", dfn, rec, loc=(L - tx, W - ty), outcome="won")
            self.change_possession(dfn, rec, L - tx, W - ty, "clearance")

    def do_cross(self, att, dfn, p, x, y, pressed, restart=None):
        rng = self.rng
        tx = rng.uniform(92, 101)
        ty = rng.uniform(26, 42) if rng.random() < 0.7 else rng.uniform(20, 48)
        targets = [q for q in att.on_pitch if q is not p and ROLE_GROUP[att.role_of[q.player_id]] in ("ST", "W", "AM", "CB", "WM", "CM")]
        if restart != "corner":
            targets = [q for q in targets if ROLE_GROUP[att.role_of[q.player_id]] != "CB"] or targets
        weights = [q.attrs["aerial"] ** 2 * (2.0 if ROLE_GROUP[att.role_of[q.player_id]] in ("ST", "CB") else 1.0)
                   for q in targets]
        tgt = rng.choices(targets, weights)[0]
        dp, _ = self.nearest_defender(dfn, tx, ty)
        defenders_in_box = sum(1 for d, px, py in self.defender_positions(dfn, x, y) if px > BOX_X)
        z = -1.05 + (p.attrs["passing"] - 75) * 0.035 + (tgt.attrs["aerial"] - (dp.attrs["aerial"] if dp else 72)) * 0.03
        z -= 0.4 if pressed else 0
        z += 0.25 if restart == "corner" else 0
        z -= self.weather["_penalty"]
        ok = rng.random() < sigmoid(z)
        ln = math.hypot(tx - x, ty - y)
        v = clamp(17 + ln * 0.2 + rng.gauss(0, 2), 12, 32)
        ev = self.emit("pass", att, p, loc=(x, y), end=(tx, ty), outcome="complete" if ok else "incomplete",
                       dur=ln / v, details={
                           "recipient_id": tgt.player_id, "recipient_name": tgt.short_name,
                           "length_m": round(ln, 1), "angle_deg": round(math.degrees(math.atan2(ty - y, tx - x)), 1),
                           "height": "high", "pass_type": restart or "cross",
                           "body_part": "right_foot" if p.foot != "left" else "left_foot",
                           "under_pressure": pressed, "defenders_in_lane": 0,
                           "defenders_in_box": defenders_in_box,
                           "receiver_space_m": round(rng.uniform(0.5, 2.5), 1),
                           "progressive_distance_m": round(max(0.0, math.hypot(L - x, GOAL_Y - y) - math.hypot(L - tx, GOAL_Y - ty)), 1),
                           "into_final_third": False, "into_box": True,
                           "ball_speed_kmh": round(v * 3.6 * 1.3, 1), "flight_time_s": round(ln / v, 2),
                           "switch": False, "cross": True, "key_pass": False, "assist": False})
        self.spend(ln / v + 0.3)
        if dp is not None:
            self.aerial_duel(att, tgt, dfn, dp, tx, ty, attacker_wins=ok)
        if ok:
            self.poss_passes += 1
            self.last_pass = {"event": ev, "player": p, "t": self.t, "team": att}
            self.carrier, self.bx, self.by = tgt, tx, ty
            if rng.random() < 0.42:
                self.do_shot(att, dfn, tgt, tx, ty, pressed=rng.random() < 0.6, body="head")
            elif rng.random() < 0.5:
                pass   # controlled/knocked down: play continues from the box
            else:
                self.loose_ball_clear(att, dfn, tx, ty)
        else:
            self.loose_ball_clear(att, dfn, tx, ty, cross=True)

    def loose_ball_clear(self, att, dfn, x, y, cross=False):
        rng = self.rng
        dp, _ = self.nearest_defender(dfn, x, y)
        dp = dp or self.rng.choice(dfn.outfield())
        if cross and rng.random() < 0.2:
            gk = dfn.gk()
            self.emit("goalkeeper", dfn, gk, loc=(L - x, W - y), outcome="success",
                      details={"action": "claim", "shot_event_id": None})
            self.change_possession(dfn, gk, L - x, W - y, "goalkeeper_claim", allow_counter=False)
            self.spend(rng.uniform(2, 5))
            return
        cx, cy = clamp(L - x + rng.uniform(15, 45), 10, 75), clamp(W - y + rng.gauss(0, 14), 2, 66)
        self.emit("clearance", dfn, dp, loc=(L - x, W - y), end=(cx, cy),
                  details={"body_part": "head" if rng.random() < 0.6 else "foot", "under_pressure": True})
        self.spend(rng.uniform(1.5, 3.0))
        if rng.random() < (0.16 if cross else 0.10):      # out for a corner
            self.emit("ball_out", dfn, None, loc=(0.0, 0.0 if y > 34 else 68.0), details={"restart": "corner"})
            self.dead(rng.uniform(22, 35))
            self.corner(att, y)
            return
        # second ball
        if rng.random() < 0.42:
            rec = self.pick(att, ("CM", "DM", "AM", "FB"))
            self.emit("ball_recovery", att, rec, loc=(L - cx, W - cy), outcome="won")
            self.carrier, self.bx, self.by = rec, L - cx, W - cy
            self.pattern = "regular_play"
        else:
            rec = self.pick(dfn, ("CM", "DM", "ST", "W", "AM"))
            self.emit("ball_recovery", dfn, rec, loc=(cx, cy), outcome="won")
            self.change_possession(dfn, rec, cx, cy, "clearance")

    # ------------------------------------------------------------ shots
    def do_shot(self, att, dfn, p, x, y, pressed, body=None, pattern_override=None,
                direct_fk=False, penalty=False):
        rng = self.rng
        if body is None:
            body = "foot"
        big = False
        if not penalty and not direct_fk:
            dist, _ = shot_geometry(x, y)
            big = (self.counter and dist < 14 and not pressed and rng.random() < 0.6) or \
                  (dist < 9 and not pressed and rng.random() < 0.35)
        pattern = pattern_override or self.pattern
        xg = expected_goals(x, y, body, big, pressed, pattern, direct_fk, penalty)
        dist, angle = shot_geometry(x, y)
        gk = dfn.gk()
        fin = p.attrs["finishing"] if body == "foot" else (p.attrs["aerial"] + p.attrs["finishing"]) / 2
        p_goal = xg * (1 + (fin - 75) * 0.018) * (1 - (gk.attrs["keeping"] - 75) * 0.014)
        p_goal *= 1 - 0.35 * self.fatigue(att, p) + 0.10 * self.m_for(att) + 0.08 * self.quality(att)
        p_goal = clamp(p_goal, 0.003, 0.97)
        if penalty:
            p_block = 0.0
        elif direct_fk:
            p_block = 0.30
        else:
            p_block = clamp(0.30 * (1 - xg) * (1.3 if pressed else 1.0), 0.03, 0.40)
        r = rng.random()
        if r < p_goal:
            outcome = "goal"
        else:
            r2 = rng.random()
            if r2 < p_block:
                outcome = "blocked"
            elif r2 < p_block + 0.03:
                outcome = "post"
            elif r2 < p_block + 0.03 + (0.40 if not penalty else 0.6) * (1 - p_block):
                outcome = "saved"
            else:
                outcome = "off_target"
        if body == "head":
            spd = rng.uniform(38, 72)
        else:
            spd = 58 + (p.attrs["shot_power"] - 50) * 0.75 + rng.gauss(0, 9) - (dist < 8) * 12
            if direct_fk:
                spd = rng.uniform(85, 112)
            if penalty:
                spd = rng.uniform(85, 118)
        spd = clamp(spd, 30, 132)
        # goal-mouth end location: y across goal (abs to frame), z height
        if outcome in ("goal", "saved", "post"):
            gy = rng.uniform(GOAL_Y - POST_HALF + 0.2, GOAL_Y + POST_HALF - 0.2)
            gz = rng.uniform(0.05, 2.3)
            if outcome == "post":
                gy = rng.choice([GOAL_Y - POST_HALF, GOAL_Y + POST_HALF])
        elif outcome == "off_target":
            gy = rng.choice([rng.uniform(25, GOAL_Y - POST_HALF - 0.1), rng.uniform(GOAL_Y + POST_HALF + 0.1, 43)])
            gz = rng.uniform(0.1, 4.5)
        else:
            gy, gz = y + rng.gauss(0, 1), rng.uniform(0.1, 1.5)
        assist = None
        if self.last_pass and self.last_pass["team"] is att and self.t - self.last_pass["t"] < 12 \
                and self.last_pass["player"] is not p:
            assist = self.last_pass
            assist["event"]["details"]["key_pass"] = True
        technique = "penalty" if penalty else "free_kick" if direct_fk else \
            ("header" if body == "head" else rng.choices(["normal", "volley", "half_volley", "chip", "curler"],
                                                         [0.72, 0.08, 0.08, 0.03, 0.09])[0])
        shot_dur = max(0.15, (dist / (spd / 3.6)) if outcome != "blocked" else 0.3)
        ev = self.emit("shot", att, p, loc=(x, y), end=(L if outcome != "blocked" else min(L, x + 2), gy),
                       outcome=outcome, dur=shot_dur, details={
                           "xg": round(xg, 3), "body_part": body if body == "head" else
                           ("right_foot" if p.foot != "left" else "left_foot"),
                           "technique": technique, "shot_speed_kmh": round(spd, 1),
                           "distance_m": round(dist, 1), "angle_deg": round(math.degrees(angle), 1),
                           "under_pressure": bool(pressed), "big_chance": big,
                           "first_time": rng.random() < (0.55 if body == "head" else 0.3),
                           "end_z_m": round(gz, 2),
                           "on_target": outcome in ("goal", "saved"),
                           "key_pass_id": assist["event"]["event_id"] if assist else None,
                           "key_pass_player_id": assist["player"].player_id if assist else None,
                           "goalkeeper_id": gk.player_id})
        self.spend(shot_dur + 0.5)
        if outcome == "goal":
            if assist:
                assist["event"]["details"]["assist"] = True
            att.goals += 1
            self.period_counts["goals"] += 1
            self.emit("goal", att, p, loc=(x, y), details={
                "shot_event_id": ev["event_id"], "xg": round(xg, 3),
                "assist_player_id": assist["player"].player_id if assist else None,
                "assist_player_name": assist["player"].short_name if assist else None,
                "own_goal": False, "body_part": ev["details"]["body_part"], "technique": technique,
                "score_after": {"home": self.home.goals, "away": self.away.goals}})
            self.mom = clamp(self.mom + (0.30 if att is self.home else -0.30), -1, 1)
            self.chaos = clamp(self.chaos + 0.22, 0, 1)
            self.dead(rng.uniform(45, 75))
            self.kick_off(dfn)
            return
        self.mom = clamp(self.mom + (0.05 if att is self.home else -0.05) * (1 + 3 * xg), -1, 1)
        if outcome == "saved":
            hold = rng.random() < 0.55 - 0.15 * (spd > 95)
            self.emit("goalkeeper", dfn, gk, loc=(1.0, W - gy), outcome="success", details={
                "action": "save", "shot_event_id": ev["event_id"], "held": hold,
                "shot_xg": round(xg, 3), "shot_speed_kmh": round(spd, 1)})
            if hold:
                self.change_possession(dfn, gk, 3.0, W - gy, "goalkeeper_save", allow_counter=False)
                self.spend(rng.uniform(3, 8), in_play=False)
                self.gk_distribution(dfn)
            elif rng.random() < 0.55:
                self.emit("ball_out", dfn, gk, loc=(0.0, 0.0 if gy > 34 else 68.0), details={"restart": "corner"})
                self.dead(rng.uniform(22, 35))
                self.corner(att, gy)
            else:
                self.loose_ball_clear(att, dfn, rng.uniform(95, 102), gy + rng.gauss(0, 5))
        elif outcome == "blocked":
            dp, _ = self.nearest_defender(dfn, x, y)
            if dp:
                self.emit("block", dfn, dp, loc=(L - x - 1.5, W - y), details={"shot_event_id": ev["event_id"]})
            if rng.random() < 0.33:
                self.emit("ball_out", dfn, dp, loc=(0.0, 0.0 if y > 34 else 68.0), details={"restart": "corner"})
                self.dead(rng.uniform(22, 35))
                self.corner(att, y)
            else:
                self.loose_ball_clear(att, dfn, x + 2, y)
        else:   # off target / post
            if outcome == "post" and rng.random() < 0.45:
                self.loose_ball_clear(att, dfn, 101, gy)
                return
            self.emit("ball_out", att, None, loc=(L, gy), details={"restart": "goal_kick"})
            self.change_possession(dfn, gk, 5.5, rng.choice([24.0, 44.0]), "shot_off_target", "from_goal_kick",
                                   allow_counter=False)
            self.dead(rng.uniform(18, 32))
            self.goal_kick(dfn)

    # ------------------------------------------------------------ set pieces
    def corner(self, att, y_hint):
        rng = self.rng
        dfn = self.other(att)
        side_y = 0.5 if y_hint < 34 else 67.5
        taker = max([p for p in att.on_pitch if att.role_of[p.player_id] != "GK"],
                    key=lambda p: p.attrs["passing"] + p.attrs["vision"] + rng.gauss(0, 6))
        if self.poss is not att:
            self.possession_id += 1
            self.poss = att
            self.poss_start_t = self.t
            self.poss_passes = 0
        self.pattern = "from_corner"
        self.counter = 0
        self.bx, self.by = 104.5, side_y
        if rng.random() < 0.18:   # short corner
            recv = self.pick(att, ("W", "AM", "CM", "FB", "WM"), exclude=taker)
            self.attempt_pass(att, dfn, taker, recv, 104.5, side_y, rng.uniform(92, 100),
                              side_y + (8 if side_y < 34 else -8), "ground", "corner", False, restart="corner")
            return
        self.do_cross(att, dfn, taker, 104.5, side_y, False, restart="corner")

    def throw_in(self, ts):
        rng = self.rng
        p = self.carrier
        x, y = self.bx, self.by
        recv = None
        best = 1e9
        for q in ts.outfield():
            if q is p:
                continue
            qx, qy = self.shape_pos(ts, q, x, y)
            d = math.hypot(qx - x, qy - y) + rng.uniform(0, 8)
            if d < best:
                best, recv = d, q
        tx = clamp(x + rng.uniform(-6, 14), 2, 103)
        ty = clamp(y + (rng.uniform(6, 16) if y < 34 else -rng.uniform(6, 16)), 1, 67)
        self.attempt_pass(ts, self.other(ts), p, recv, x, y, tx, ty, "low", "throw_in", False, restart="throw_in")

    def goal_kick(self, ts):
        rng = self.rng
        gk = ts.gk()
        x, y = self.bx, self.by
        short = rng.random() < 0.20 + 0.65 * ts.style["possession"] - 0.30 * self.other(ts).style["press"] + 0.1
        if short:
            recv = self.pick(ts, ("CB",)) if rng.random() < 0.8 else self.pick(ts, ("DM", "FB"))
            tx, ty = self.shape_pos(ts, recv, 15, y)
            tx = min(tx, 22)
            self.attempt_pass(ts, self.other(ts), gk, recv, x, y, tx, ty, "ground", "goal_kick", False,
                              restart="goal_kick")
        else:
            recv = self.pick(ts, ("ST", "W", "AM", "WM"))
            tx, ty = rng.uniform(52, 70), clamp(34 + rng.gauss(0, 14), 4, 64)
            self.attempt_pass(ts, self.other(ts), gk, recv, x, y, tx, ty, "high", "goal_kick", False,
                              restart="goal_kick")

    def gk_distribution(self, ts):
        rng = self.rng
        gk = ts.gk()
        self.pattern = "regular_play"
        if rng.random() < 0.55 + 0.3 * ts.style["possession"]:
            recv = self.pick(ts, ("CB", "FB", "DM"))
            tx, ty = self.shape_pos(ts, recv, 20, self.by)
            self.attempt_pass(ts, self.other(ts), gk, recv, 6, self.by, min(tx, 30), ty, "ground", "gk_throw", False)
        else:
            recv = self.pick(ts, ("ST", "W", "AM"))
            self.attempt_pass(ts, self.other(ts), gk, recv, 12, self.by, rng.uniform(50, 72),
                              clamp(34 + rng.gauss(0, 15), 4, 64), "high", "long_ball", False)

    def foul(self, att, dfn, victim, offender, x, y):
        rng = self.rng
        in_box = x >= BOX_X and BOX_Y0 <= y <= BOX_Y1
        if in_box and rng.random() < 0.10:      # many box contacts are not given
            in_box = True
        elif in_box:
            x = BOX_X - rng.uniform(0.5, 4)
            in_box = False
        sev = rng.random()
        ev = self.emit("foul", dfn, offender, loc=(L - x, W - y), details={
            "fouled_player_id": victim.player_id, "fouled_player_name": victim.short_name,
            "penalty": in_box, "advantage": False,
            "tactical": self.counter > 0 or (x > 50 and self.pattern == "from_counter")})
        card = None
        strict = self.referee["strictness"]
        p_y = (0.07 + 0.15 * strict) * (1.8 if ev["details"]["tactical"] else 1.0) * (1.5 if in_box else 1.0)
        if sev < 0.0015 + 0.0025 * strict:
            card = "red"
        elif rng.random() < p_y * (0.4 if offender.player_id in dfn.yellow else 1.0):
            card = "second_yellow" if offender.player_id in dfn.yellow else "yellow"
        if card:
            self.period_counts["cards"] += 1
            self.emit("card", dfn, offender, details={"card": card, "foul_event_id": ev["event_id"],
                                                      "reason": "tactical_foul" if ev["details"]["tactical"] else "foul"})
            if card == "yellow":
                dfn.yellow.add(offender.player_id)
            else:
                self.send_off(dfn, offender)
        if rng.random() < 0.025:
            self.period_counts["injuries"] += 1
            self.emit("injury", att, victim, details={"severity": "minor" if rng.random() < 0.6 else "forced_off"})
            if att.subs_used < 5 and rng.random() < 0.4:
                att.forced_sub.append(victim)
            self.t += rng.uniform(40, 120)
        # restart
        if self.poss is not att:
            self.possession_id += 1
            self.poss = att
            self.poss_start_t = self.t
            self.poss_passes = 0
        self.carrier = victim if victim in att.on_pitch else self.rng.choice(att.outfield())
        self.bx, self.by = x, y
        self.counter = 0
        self.dead(rng.uniform(20, 38) + (20 if card else 0))
        if in_box:
            self.pattern = "from_penalty"
            taker = max(att.outfield(), key=lambda p: p.attrs["finishing"] + p.attrs["composure"])
            self.dead(rng.uniform(30, 60))
            self.do_shot(att, dfn, taker, BOX_X + 0.5 + 5.5, 34.0, False, penalty=True,
                         pattern_override="from_penalty")
            return
        self.pattern = "from_free_kick"
        if x > 76 and 18 < y < 50 and rng.random() < 0.40:
            taker = max(att.outfield(), key=lambda p: p.attrs["shot_power"] + p.attrs["finishing"] + rng.gauss(0, 5))
            self.do_shot(att, dfn, taker, x, y, False, direct_fk=True)
        elif x > 68 and rng.random() < 0.6:
            taker = max(att.outfield(), key=lambda p: p.attrs["passing"] + rng.gauss(0, 5))
            self.do_cross(att, dfn, taker, x, y, False, restart="free_kick")
        else:
            taker = self.carrier
            recv, tx, ty, h, ptype = self.choose_pass(att, dfn, taker, x, y, False)
            self.attempt_pass(att, dfn, taker, recv, x, y, tx, ty, h, "free_kick", False, restart="free_kick")

    def send_off(self, ts, p):
        ts.sent_off.add(p.player_id)
        if p in ts.on_pitch and len(ts.on_pitch) > 7:
            ts.on_pitch.remove(p)
            ts.minutes[p.player_id][1] = self.clock()[1]
        self.chaos = clamp(self.chaos + 0.25, 0, 1)
        self.mom = clamp(self.mom + (-0.25 if ts is self.home else 0.25), -1, 1)

    # ------------------------------------------------------------ outputs
    def _lineup(self, ts: TeamState):
        starters = [p for p in ts.club.squad if p.player_id in ts.minutes and ts.minutes[p.player_id][0] == 0]
        return starters

    def metadata(self) -> dict:
        def team_block(ts: TeamState):
            c = ts.club
            start_ids = {pid for pid, mm in ts.minutes.items() if mm[0] == 0}
            squad_by_id = {p.player_id: p for p in c.squad}
            starters = [squad_by_id[pid] for pid in start_ids]
            role_order = [r for r, _, _ in FORMATIONS[c.formation]]
            starters.sort(key=lambda p: role_order.index(ts.role_of[p.player_id]) if ts.role_of.get(p.player_id) in role_order else 99)
            bench = [p for p in c.squad if p.player_id not in start_ids and p.player_id in ts.role_of or
                     (p.player_id not in start_ids)]

            def pb(p, starter):
                return {"player_id": p.player_id, "name": p.name, "short_name": p.short_name,
                        "shirt": p.shirt, "position": ts.role_of.get(p.player_id, p.position) if starter else p.position,
                        "group": p.group, "nationality": p.nationality, "age": p.age, "foot": p.foot,
                        "height_cm": p.height_cm, "overall": p.overall(), "is_star": p.is_star,
                        "attributes": p.attrs}
            return {
                "team_id": c.club_id, "name": c.name, "short_name": c.short_name, "abbr": c.abbr,
                "nickname": c.nickname, "city": c.city, "market": c.country_market, "colors": c.colors,
                "formation": c.formation, "style_profile": c.style,
                "starting_xi": [pb(p, True) for p in starters],
                "bench": [pb(p, False) for p in bench if p.player_id not in start_ids],
            }
        return {
            "schema_version": SCHEMA_VERSION,
            "match_id": self.match_id,
            "seed": self.seed,
            "synthetic": True,
            "competition": self.competition,
            "kickoff_utc": self.kickoff_utc,
            "venue": {"stadium": self.home.club.stadium, "city": self.home.club.city,
                      "capacity": self.home.club.capacity},
            "attendance": int(self.home.club.capacity * self.rng.uniform(0.82, 0.995)),
            "referee": self.referee,
            "weather": {k: v for k, v in self.weather.items() if not k.startswith("_")},
            "pitch": {"length_m": L, "width_m": W},
            "coordinates": {
                "location": "acting team's attacking frame: x 0->105 toward opponent goal, y 0->68 left->right",
                "location_abs": "broadcast frame: x 0 = left goal line on screen, y 0 = far touchline",
                "home_attacks_right_in_period": {"1": True, "2": False}},
            "home": team_block(self.home),
            "away": team_block(self.away),
            "pre_match": self.pre_match,
            "final_score": {"home": self.home.goals, "away": self.away.goals},
        }

    def ground_truth(self) -> dict:
        """Hidden latent state for validating explainability models (not for live use)."""
        mins = {}
        for ts in (self.home, self.away):
            for pid, mm in ts.minutes.items():
                mins[pid] = {"on": mm[0], "off": mm[1]}
        return {
            "match_id": self.match_id,
            "description": "Latent variables that drove the simulation. momentum_home in [-1,1] (+ = home on top); "
                           "chaos in [0,1] (turnover-heavy, stretched play). Styles are live tactical intents.",
            "timeline": self.gt_timeline,
            "possession_seconds": {"home": round(self.home.possession_s, 1), "away": round(self.away.possession_s, 1)},
            "minutes_played": mins,
        }

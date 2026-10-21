"""Live calls: fans predict what happens next; the live models set fair odds.

Calls never touch official Fantasy points. They earn "call points" in a separate game:
a correct call pays round(10 / p), where p is the model probability when the call was made,
so every call is worth 10 call points on average whatever its odds: there is no safe farm,
only skill (or luck) at reading the match.

Kinds
    next_goal   home | away | none          settles at the next goal, or at full time for "none"
    scorer      player scores before full time (own goals do not count)
    booked      player gets a card before full time
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

from .scoring import position_of

MAX_OPEN = 3
SCORER_PRIOR = {"FWD": 0.24, "MID": 0.10, "DEF": 0.04, "GK": 0.0}
CARDS_PER_PLAYER_90 = 0.16            # simulated season average, all positions
CARD_POSITION = {"DEF": 1.2, "MID": 1.1, "FWD": 0.8, "GK": 0.25}


def payout(p: float) -> int:
    return max(11, min(500, round(10 / max(p, 1e-6))))


def team_rates(next_goal: dict | None, minutes_left: float) -> tuple[float, float]:
    """Expected remaining goals (home, away) recovered from the next-goal model's three probabilities."""
    if not next_goal:
        lam = 2.7 * minutes_left / 90
        return lam / 2, lam / 2
    p_none = min(0.999, max(1e-4, next_goal["none"]))
    total = -math.log(p_none)
    scored = max(1e-6, 1 - p_none)
    return total * next_goal["home"] / scored, total * next_goal["away"] / scored


@dataclass
class Call:
    call_id: str
    viewer: str
    kind: str
    target: str                # side for next_goal, player_id otherwise
    label: str
    p: float
    pays: int
    minute: str
    placed_at: float = field(default_factory=time.time)
    status: str = "open"       # open | won | lost
    settled_minute: str | None = None

    def view(self) -> dict:
        return {k: getattr(self, k) for k in ("call_id", "kind", "target", "label", "p", "pays", "minute",
                                              "status", "settled_minute")}


class CallBook:
    """Quotes and settles calls for one live match. `season_share` maps player_id -> share of the
    club's expected goals this season (used as the prior for scorer odds)."""

    def __init__(self, state, season_share: dict | None = None):
        self.st = state
        self.season_share = season_share or {}
        self.calls: dict[str, list[Call]] = {}
        self._n = 0

    # ------------------------------------------------------------------ odds
    def minutes_left(self) -> float:
        return max(1.0, 93.0 - self.st.minute)

    def scorer_share(self, pid: str) -> float:
        Q = self.st.players[pid]
        side = Q["side"]
        prior = self.season_share.get(pid, SCORER_PRIOR[position_of(Q["group"])])
        team_xg = self.st.teams[side]["xg"]
        w = team_xg / (team_xg + 1.0)
        live = Q["xg"] / team_xg if team_xg else prior
        return (1 - w) * prior + w * live

    def quotes(self) -> dict:
        """Current probabilities for every call on offer."""
        st = self.st
        if st.finished:
            return {"open": False}
        lam_h, lam_a = team_rates(st.next_goal, self.minutes_left())
        ng = st.next_goal or {"home": 0.4, "away": 0.4, "none": 0.2}
        lam = {"home": lam_h, "away": lam_a}
        scorer, booked = {}, {}
        for side in ("home", "away"):
            on = list(st.on_pitch[side])
            shares = {pid: self.scorer_share(pid) for pid in on}
            norm = max(1.0, sum(shares.values()) / 0.97)          # shares of one team can't exceed 100%
            for pid in on:
                Q = st.players[pid]
                scorer[pid] = round(1 - math.exp(-lam[side] * shares[pid] / norm), 4)
                if Q["yellow"] or Q["red"]:
                    continue
                rate = CARDS_PER_PLAYER_90 * CARD_POSITION[position_of(Q["group"])]
                rate *= (1 + 0.25 * Q["fouls"]) * (1 + st.chaos / 100)
                booked[pid] = round(1 - math.exp(-rate * self.minutes_left() / 90), 4)
        return {"open": True, "minutes_left": round(self.minutes_left()),
                "next_goal": {k: round(v, 4) for k, v in ng.items()}, "scorer": scorer, "booked": booked}

    # ------------------------------------------------------------------ placing
    def open_calls(self, viewer: str) -> list[Call]:
        return [c for c in self.calls.get(viewer, []) if c.status == "open"]

    def place(self, viewer: str, kind: str, target: str) -> Call:
        q = self.quotes()
        if not q["open"]:
            raise ValueError("The match is over: calls are closed.")
        if len(self.open_calls(viewer)) >= MAX_OPEN:
            raise ValueError(f"At most {MAX_OPEN} open calls at a time.")
        if any(c.kind == kind and c.target == target for c in self.open_calls(viewer)):
            raise ValueError("You already made that call.")
        if kind == "next_goal" and target in q["next_goal"]:
            p = q["next_goal"][target]
            label = {"home": self.st.meta["home"]["short_name"], "away": self.st.meta["away"]["short_name"],
                     "none": "No more goals"}[target]
            label = label + " score next" if target != "none" else label
        elif kind in ("scorer", "booked") and target in q[kind]:
            p = q[kind][target]
            label = f"{self.st.players[target]['name']} {'scores' if kind == 'scorer' else 'gets booked'}"
        else:
            raise ValueError("That call is not on offer right now.")
        if p < 0.01:
            raise ValueError("Odds too long to offer.")
        self._n += 1
        c = Call(f"C{self._n}", viewer, kind, target, label, round(p, 4), payout(p), self.st.display_minute)
        self.calls.setdefault(viewer, []).append(c)
        return c

    # ------------------------------------------------------------------ settling
    def settle(self, ev: dict) -> list[Call]:
        """Call after MatchState.update(ev); returns the calls settled by this event."""
        t = ev["type"]
        done = []
        for calls in self.calls.values():
            for c in calls:
                if c.status != "open":
                    continue
                result = None
                if t == "goal":
                    if c.kind == "next_goal":
                        result = c.target == ev["team_side"]
                    elif c.kind == "scorer" and c.target == ev["player_id"] and not ev["details"].get("own_goal"):
                        result = True
                elif t == "card" and c.kind == "booked" and c.target == ev["player_id"]:
                    result = True
                elif t == "match_end":
                    result = c.kind == "next_goal" and c.target == "none"
                if result is not None:
                    c.status = "won" if result else "lost"
                    c.settled_minute = ev.get("display_minute")
                    done.append(c)
        return done

    def scoreboard(self, viewer: str) -> dict:
        calls = self.calls.get(viewer, [])
        return {"points": sum(c.pays for c in calls if c.status == "won"),
                "won": sum(c.status == "won" for c in calls), "lost": sum(c.status == "lost" for c in calls),
                "calls": [c.view() for c in calls]}

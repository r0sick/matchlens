"""MatchLens Fantasy scoring: deterministic points with a reason for every point.

The same scorer is used for the season history (tools/build_fantasy.py) and live, next to the
MatchState of a running match, so a live total always equals the final total once the match ends.
Fan input never changes these points: predictions ("live calls") are scored separately.

Rules (MatchLens's own, kept close to what fantasy players expect)
    Appearance            1 pt for playing, 2 pts for 60 minutes or more
    Goal                  GK 6 / DEF 6 / MID 5 / FWD 4
    Assist                3
    Clean sheet           GK 4 / DEF 4 / MID 1   (60+ minutes, no goal conceded while on the pitch)
    Goals conceded        GK / DEF: -1 for every 2 conceded while on the pitch
    Saves                 GK: +1 for every 3 saves
    Defensive work        DEF: +2 for 5+ tackles won, interceptions, clearances and blocks
                          MID / FWD: +2 for 20+ of those plus ball recoveries
    Yellow card -1, red card -3, own goal -2
    MatchLens bonus       3 / 2 / 1 for the three best live ratings in the match
"""
from __future__ import annotations

from collections import defaultdict

# role group (from the generator) -> fantasy position
POSITION = {"GK": "GK", "CB": "DEF", "FB": "DEF", "DM": "MID", "CM": "MID", "WM": "MID", "AM": "MID",
            "W": "FWD", "ST": "FWD"}
GOAL_PTS = {"GK": 6, "DEF": 6, "MID": 5, "FWD": 4}
CLEAN_SHEET_PTS = {"GK": 4, "DEF": 4, "MID": 1, "FWD": 0}
ASSIST_PTS = 3
DEF_THRESHOLD = {"DEF": 5, "MID": 20, "FWD": 20}   # calibrated: roughly the top 15-20% of 60-minute games
DEF_PTS = 2
BONUS = (3, 2, 1)

# reason codes -> English labels (the UI translates the codes)
LABELS = {
    "appearance": "Played", "appearance_60": "Played 60+ minutes", "goal": "Goal", "assist": "Assist",
    "clean_sheet": "Clean sheet", "conceded": "Goals conceded", "saves": "Saves",
    "defensive": "Defensive work", "yellow": "Yellow card", "red": "Red card", "own_goal": "Own goal",
    "bonus": "MatchLens bonus",
}


def position_of(group: str) -> str:
    return POSITION.get(group, "MID")


class FantasyScorer:
    """Companion of a MatchState: call `update(ev)` after `MatchState.update(ev)` for each event."""

    def __init__(self, state):
        self.st = state
        self.conceded = defaultdict(int)       # goals conceded while the player was on the pitch
        self.blocks = defaultdict(int)
        self.own_goals = defaultdict(int)

    def update(self, ev: dict):
        t = ev["type"]
        if t == "goal":
            scoring_side = ev["team_side"]
            conceding = "away" if scoring_side == "home" else "home"
            for pid in self.st.on_pitch[conceding]:
                self.conceded[pid] += 1
            if ev["details"].get("own_goal"):
                self.own_goals[ev["player_id"]] += 1
        elif t == "block" and ev.get("player_id"):
            self.blocks[ev["player_id"]] += 1

    # ------------------------------------------------------------------ per player
    def minutes(self, pid) -> int:
        Q = self.st.players[pid]
        if "minutes_on" not in Q:
            return 0
        end = Q.get("minutes_off")
        if end is None:
            end = self.st.minute
        return min(90, max(0, int(end) - int(Q["minutes_on"])))   # added time is not counted twice

    def played(self, pid) -> bool:
        return "minutes_on" in self.st.players[pid]

    def defensive_actions(self, pid) -> int:
        Q = self.st.players[pid]
        n = Q["tackles_won"] + Q["interceptions"] + Q["clearances"] + self.blocks[pid]
        if position_of(Q["group"]) in ("MID", "FWD"):
            n += Q["ball_recoverys"]
        return int(n)

    def breakdown(self, pid, bonus: int = 0) -> list[dict]:
        """List of {code, label, count, pts}; empty if the player has not played."""
        if not self.played(pid):
            return []
        Q = self.st.players[pid]
        pos = position_of(Q["group"])
        mins = self.minutes(pid)
        out = []

        def add(code, pts, count=1):
            if pts:
                out.append({"code": code, "label": LABELS[code], "count": count, "pts": pts})

        if mins >= 60:
            add("appearance_60", 2, mins)
        else:
            add("appearance", 1, mins)
        g = int(Q["goals"]) - self.own_goals[pid]
        add("goal", g * GOAL_PTS[pos], g)
        add("assist", int(Q["assists"]) * ASSIST_PTS, int(Q["assists"]))
        conceded = self.conceded[pid]
        if mins >= 60 and conceded == 0:
            add("clean_sheet", CLEAN_SHEET_PTS[pos])
        if pos in ("GK", "DEF") and conceded >= 2:
            add("conceded", -(conceded // 2), conceded)
        if pos == "GK" and Q["saves"] >= 3:
            add("saves", int(Q["saves"]) // 3, int(Q["saves"]))
        if pos in DEF_THRESHOLD:
            n = self.defensive_actions(pid)
            if n >= DEF_THRESHOLD[pos]:
                add("defensive", DEF_PTS, n)
        add("yellow", -int(Q["yellow"]), int(Q["yellow"]))
        add("red", -3 * int(Q["red"]), int(Q["red"]))
        add("own_goal", -2 * self.own_goals[pid], self.own_goals[pid])
        add("bonus", bonus)
        return out

    def bonus_table(self) -> dict:
        """Provisional MatchLens bonus from the current live ratings (final once the match ends)."""
        rows = []
        for pid, Q in self.st.players.items():
            if self.played(pid):
                rows.append((self.st.player_rating(Q), Q["goals"], Q["assists"], pid))
        rows.sort(reverse=True)
        return {pid: BONUS[i] for i, (*_, pid) in enumerate(rows[:len(BONUS)])}

    def table(self) -> dict:
        """pid -> {points, minutes, position, reasons, rating, provisional} for every player who has played."""
        bonus = self.bonus_table()
        out = {}
        for pid, Q in self.st.players.items():
            if not self.played(pid):
                continue
            reasons = self.breakdown(pid, bonus.get(pid, 0))
            out[pid] = {"player_id": pid, "name": Q["name"], "side": Q["side"],
                        "position": position_of(Q["group"]), "minutes": self.minutes(pid),
                        "points": sum(r["pts"] for r in reasons), "reasons": reasons,
                        "rating": self.st.player_rating(Q), "provisional": not self.st.finished}
        return out

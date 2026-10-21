"""MatchLens MCP server: the live engine exposed as Model Context Protocol tools.

Mounted by the FastAPI app at /mcp (streamable HTTP). It serves two kinds of clients:
  * the newsroom agents, which call these tools to enrich a story with verified numbers;
  * any MCP client, e.g. GitHub Copilot agent mode in VS Code (see .vscode/mcp.json),
    so an analyst can ask questions about a live match in plain language.

Every tool is read-only and answers from the live session state, never from the future.
"""
from __future__ import annotations

import unicodedata
from typing import Callable

from mcp.server.fastmcp import FastMCP

from .facts import control_label, pct, r2


def _norm(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s or "") if not unicodedata.combining(c)).lower().strip()


def build_mcp(sessions: dict, catalogue: dict, narratives_of: Callable[[str], list]) -> FastMCP:
    mcp = FastMCP(
        "matchlens",
        instructions=("Live football match intelligence for synthetic Aurora League matches. "
                      "All numbers come from the live engine at the current match minute. "
                      "Call list_matches first if you do not know the match_id."),
        stateless_http=True, json_response=True, streamable_http_path="/",
    )

    def session(match_id: str):
        s = sessions.get(match_id)
        if s is None:
            raise ValueError(f"Match {match_id!r} is not being played right now. "
                             f"Use list_matches to see live matches.")
        return s

    def team_name(s, side):
        return s.meta[side]["short_name"]

    @mcp.tool()
    def list_matches(live_only: bool = True) -> list[dict]:
        """List matches. live_only=True returns only matches currently being played (they have live data)."""
        out = []
        for mid, info in catalogue.items():
            s = sessions.get(mid)
            if live_only and not s:
                continue
            row = {"match_id": mid, "home": info["home"]["name"], "away": info["away"]["name"],
                   "matchday": info["competition"].get("matchday"), "live": bool(s and not s.done)}
            if s:
                row.update({"minute": s.state.display_minute, "score": dict(s.state.score)})
            out.append(row)
        return out

    @mcp.tool()
    def get_match_state(match_id: str) -> dict:
        """Score, clock, win probability, xG, shots, possession, field tilt, pressing (PPDA),
        momentum (-100 away dominant .. +100 home dominant) and chaos (0 controlled .. 100 chaotic)."""
        s = session(match_id)
        st = s.state
        T = {k: st.team_view(k) for k in ("home", "away")}
        poss, tilt, ppda = st.possession(), st.field_tilt(), st.ppda()
        return {
            "match_id": match_id, "minute": st.display_minute, "finished": st.finished,
            "home": s.meta["home"]["name"], "away": s.meta["away"]["name"],
            "score": dict(st.score),
            "win_probability_pct": {k: pct(v) for k, v in st.win_prob.items()} if st.win_prob else None,
            "next_goal_pct": {k: pct(v) for k, v in st.next_goal.items()} if st.next_goal else None,
            "teams": {side: {"xg": r2(T[side].get("xg", 0)), "shots": int(T[side].get("shots", 0)),
                             "shots_on_target": int(T[side].get("shots_on_target", 0)),
                             "pass_accuracy_pct": round(T[side]["pass_accuracy_pct"]) if T[side].get("pass_accuracy_pct") else None,
                             "corners": int(T[side].get("corners", 0)), "fouls": int(T[side].get("fouls", 0)),
                             "yellow_cards": int(T[side].get("yellow", 0)), "red_cards": int(T[side].get("red", 0))}
                      for side in ("home", "away")},
            "possession_pct": {"total": [round(x) for x in poss["total"]], "last_5_min": [round(x) for x in poss["last5"]]},
            "field_tilt_pct_last_10_min": [round(x) for x in tilt["last10"]],
            "ppda": {"home": ppda["home"], "away": ppda["away"], "home_last_15": ppda["home_last15"], "away_last_15": ppda["away_last15"]},
            "momentum": round(st.momentum), "chaos": round(st.chaos), "control": control_label(st.chaos),
        }

    @mcp.tool()
    def get_player(match_id: str, player: str) -> dict:
        """Live stats for one player (name or player_id) plus season and career context before this match."""
        s = session(match_id)
        st = s.state
        q = _norm(player)
        cand = [pid for pid, P in st.players.items() if pid.lower() == q or _norm(P["name"]) == q]
        if not cand:
            cand = [pid for pid, P in st.players.items() if q and q in _norm(P["name"])]
        if not cand:
            raise ValueError(f"No player matching {player!r} in this match.")
        pid = cand[0]
        v = st.player_view(pid)
        pre = next((p for p in (s.meta.get("pre_match") or {}).get("players", []) if p["player_id"] == pid), {})
        return {
            "player_id": pid, "name": v["name"], "team": team_name(s, v["side"]), "shirt": v["shirt"],
            "position": v["position"], "on_pitch": v["on_pitch"], "rating": v["rating"],
            "match": {k: (r2(v.get(k)) if isinstance(v.get(k), float) else v.get(k)) for k in (
                "goals", "assists", "shots", "shots_on_target", "xg", "xa", "key_passes", "passes",
                "passes_complete", "pass_accuracy_pct", "avg_pass_difficulty", "tackles_won",
                "interceptions", "dribbles_complete", "distance_m", "sprints", "top_speed_kmh")},
            "season_before_match": pre.get("season"), "career_before_match": pre.get("career"),
            "scoring_streak_before_match": pre.get("scoring_streak_matches"),
        }

    @mcp.tool()
    def get_timeline(match_id: str, last_n: int = 20) -> dict:
        """Recent key events (goals, cards, shots with xG, substitutions) and win probability every 5 minutes."""
        s = session(match_id)
        evs = []
        for e in s.key_events[-max(1, min(last_n, 60)):]:
            d = e.get("details") or {}
            row = {"minute": e.get("display_minute"), "type": e["type"], "team": team_name(s, e["team_side"]),
                   "player": e.get("player_name")}
            if e["type"] == "shot":
                row.update({"outcome": e.get("outcome"), "xg": r2(d.get("xg"))})
            elif e["type"] == "card":
                row["card"] = d.get("card")
            elif e["type"] == "substitution":
                row.update({"on": d.get("player_on_name"), "off": d.get("player_off_name")})
            evs.append(row)
        wp = [{"minute": p["minute"] + 1, "home": pct(p["win_prob"]["home"]), "draw": pct(p["win_prob"]["draw"]),
               "away": pct(p["win_prob"]["away"]), "momentum": round(p["momentum"])}
              for p in s.state.series if p.get("win_prob") and p["minute"] % 5 == 0]
        return {"match_id": match_id, "events": evs, "win_probability_every_5_min": wp}

    @mcp.tool()
    def get_pre_match(match_id: str) -> dict:
        """League table positions and form before kick-off, head-to-head this season, scoring streaks and milestone watch."""
        s = session(match_id)
        pre = s.meta.get("pre_match") or {}
        return {k: pre.get(k) for k in ("matchday", "standings", "head_to_head_this_season", "scoring_streaks", "milestones_watch")}

    @mcp.tool()
    def get_moments(match_id: str, last_n: int = 10) -> list[dict]:
        """Narratives already published for this match by the MatchLens newsroom (captions and explanations)."""
        session(match_id)
        out = []
        for n in narratives_of(match_id)[-max(1, min(last_n, 40)):]:
            out.append({k: n.get(k) for k in ("moment_id", "kind", "display_minute", "caption", "fan", "analyst")})
        return out

    @mcp.tool()
    def get_fantasy_player(player: str, matchday: int, club: str = "") -> dict:
        """Fantasy view of a player before a matchday: price, points, form, goals vs expected goals,
        minutes trend, next fixtures, projected points and the Transfer Advisor's HOLD/WATCH/SELL rules.
        `player` is a name or player_id; `club` (abbreviation, e.g. THR) disambiguates shared surnames."""
        from .fantasy import season as S
        if not S.available():
            raise ValueError("Fantasy data is not available on this server.")
        players = S.load()["players"]
        if player in players:
            pid = player
        else:
            q = _norm(player)
            hits = [k for k, P in players.items() if q in (_norm(P["name"]), _norm(P["full_name"]))
                    and (not club or P["club"].lower() == club.lower())]
            if not hits:
                hits = [k for k, P in players.items() if q in _norm(P["full_name"])
                        and (not club or P["club"].lower() == club.lower())]
            if not hits:
                raise ValueError(f"No player matches {player!r}.")
            if len(hits) > 1:
                return {"ambiguous": [{"player_id": k, "name": players[k]["full_name"], "club": players[k]["club"]}
                                      for k in hits]}
            pid = hits[0]
        sig = S.signals(pid, matchday)
        return sig | {"advisor_rules": S.verdict(sig)}

    return mcp

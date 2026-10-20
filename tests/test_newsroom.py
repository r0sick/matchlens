"""Newsroom tests with a scripted model (no cloud access needed).  python -m pytest -q"""
import asyncio
import json

import pytest

from matchlens.facts import MomentDetector, allowed_numbers, unsupported_numbers
from matchlens.models import load_models
from matchlens.newsroom.llm import Provider
from matchlens.newsroom.workflow import Newsroom, check_moment
from matchlens.server import KEY_EVENT_TYPES, slim_event
from matchlens.state import MatchState
from matchsim.replay import load_match
from tests.fake_llm import ScriptedChatClient

MATCH = "data/season_2026-27/matches/AUR26-MD10-KMU-THR"


@pytest.fixture(scope="module")
def sheets():
    m = load_match(MATCH)
    st, det, keys, out = MatchState(m["metadata"], load_models()), MomentDetector(m["metadata"]), [], []
    for ev in m["events"]:
        sig = st.update(ev)
        if ev["type"] in KEY_EVENT_TYPES:
            se = slim_event(ev)
            se["display_minute"], se["match_time_s"] = ev["display_minute"], ev["match_time_s"]
            keys.append(se)
        out += det.observe(ev, sig, st, keys)
    return out


def newsroom(**kw):
    return Newsroom(Provider(ScriptedChatClient(**kw), "Scripted", "fake"), mcp_url="http://127.0.0.1:9/mcp/")


def test_moments_detected(sheets):
    kinds = [s["kind"] for s in sheets]
    assert kinds.count("goal") == 2 and "half_time" in kinds and "full_time" in kinds
    assert kinds.count("state_of_play") == 4
    goal = next(s for s in sheets if s["kind"] == "goal")
    assert goal["goal"]["situation"] == "opener" and goal["win_probability"]["after_pct"] > goal["win_probability"]["before_pct"]


def test_number_grounding():
    sheet = {"minute": "74'", "xg": 0.04, "win": {"before_pct": 37, "after_pct": 71}}
    allowed = allowed_numbers(sheet)
    assert unsupported_numbers("A 4% chance, 1 time in 25, win chance 37% to 71%, xG 0.04", allowed) == []
    assert unsupported_numbers("73% of fans agree", allowed) == ["73"]
    assert unsupported_numbers("487 passes", allowed) == ["487"]


def test_fact_checker_rejects_invented_numbers_and_jargon(sheets):
    goal = next(s for s in sheets if s["kind"] == "goal")
    name = goal["scorer"]["name"]
    ok = {"caption": f"{name} scores", "commentary": f"{name} opens the scoring.", "fan": "What a moment.",
          "analyst": f"xG {goal['goal']['xg']}"}
    assert check_moment(ok, goal, []) == []
    bad = dict(ok, fan="His xG was tiny.", analyst="Possession 99%.")
    issues = check_moment(bad, goal, [])
    assert any("jargon" in i for i in issues) and any("99" in i for i in issues)
    assert any("scorer" in i for i in check_moment(dict(ok, caption="Goal", commentary="Goal."), goal, []))


def test_workflow_retries_after_fact_check_and_localises(sheets):
    goal = next(s for s in sheets if s["kind"] == "goal")
    out = asyncio.run(newsroom().produce(goal, ["es", "fr"]))
    assert out["status"] == "final" and not out["fallback"]
    steps = [(t["step"], t["ok"]) for t in out["trace"]]
    assert ("fact_check", False) in steps and steps.index(("fact_check", True)) > steps.index(("fact_check", False))
    assert set(out["texts"]) == {"en", "es", "fr"}
    assert "487" not in json.dumps(out["texts"])


def test_writer_outage_falls_back_to_template(sheets):
    goal = next(s for s in sheets if s["kind"] == "goal")
    out = asyncio.run(newsroom(fail_roles=("writer",)).produce(goal, ["es"]))
    assert out["fallback"] and out["texts"]["en"]["caption"].startswith("Goal!")
    assert "es" in out["texts"]


def test_recap_workflow(sheets):
    ft = next(s for s in sheets if s["kind"] == "full_time")
    out = asyncio.run(newsroom().produce(ft, ["es"]))
    assert not out["fallback"]
    assert {"headline", "studio_script", "article", "social", "player_of_the_match"} <= set(out["texts"]["en"])


def test_mcp_tools_answer_from_live_session():
    from matchlens import server as srv

    async def run():
        s = srv.get_session("M000042", speed=5000, restart=True)
        await asyncio.sleep(1.0)
        async def call(name, args):
            res = await srv.MCP.call_tool(name, args)
            content = res[0] if isinstance(res, tuple) else res      # (content, structured) on newer SDKs
            return json.loads(content[0].text)
        state = await call("get_match_state", {"match_id": "M000042"})
        player = await call("get_player", {"match_id": "M000042", "player": "queiroz"})
        s.task.cancel()
        return state, player
    state, player = asyncio.run(run())
    assert state["home"] == "Thornbury Rovers" and "win_probability_pct" in state
    assert player["name"] == "Queiroz" and "match" in player

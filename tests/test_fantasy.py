"""Fantasy tests: scoring, season table, live calls, Transfer Advisor.  python -m pytest -q"""
import asyncio
import json

import pytest

from matchlens.fantasy import season as S
from matchlens.fantasy.advisor import advise, check_advice, scout
from matchlens.fantasy.calls import CallBook, payout
from matchlens.fantasy.scoring import FantasyScorer
from matchlens.models import load_models
from matchlens.newsroom.llm import Provider
from matchlens.newsroom.workflow import Newsroom
from matchlens.state import MatchState
from matchsim.replay import load_match
from tests.fake_llm import ScriptedChatClient

MATCH_ID = "AUR26-MD10-KMU-THR"
MATCH = f"data/season_2026-27/matches/{MATCH_ID}"
MD = 10


def pid_of(name, club):
    return next(k for k, P in S.load()["players"].items() if P["name"] == name and P["club"] == club)


@pytest.fixture(scope="module")
def replay():
    m = load_match(MATCH)
    st = MatchState(m["metadata"], load_models())
    fs = FantasyScorer(st)
    cb = CallBook(st, S.xg_shares([m["metadata"]["home"]["team_id"], m["metadata"]["away"]["team_id"]], MD))
    return m, st, fs, cb


def test_live_points_match_season_table(replay):
    m, st, fs, _ = replay
    for ev in m["events"]:
        st.update(ev)
        fs.update(ev)
    table = fs.table()
    peiro = table[pid_of("Peiró", "THR")]
    assert {"code": "goal", "label": "Goal", "count": 1, "pts": 5} in peiro["reasons"]      # midfielder goal = 5
    assert peiro["points"] == sum(r["pts"] for r in peiro["reasons"]) and not peiro["provisional"]
    season = S.load()["players"]
    for pid, row in table.items():                       # the season table was built by the same code
        assert season[pid]["history"][MD - 1]["points"] == row["points"]


def test_no_spoilers_and_valid_default_squad():
    pid = pid_of("Peiró", "THR")
    assert all(r["md"] < MD for r in S.history(pid, MD))
    assert S.summary(pid, MD)["points"] == sum(r["points"] for r in S.load()["players"][pid]["history"][:MD - 1])
    squad = S.default_squad(MD, ("C01", "C02"))
    assert len(squad) == 15 and S.validate(squad, MD) == []
    assert any(S.load()["players"][p]["club_id"] in ("C01", "C02") for p in squad)


def test_verdicts_and_replacements():
    squad = S.default_squad(MD, ("C01", "C02"))
    chukwu = pid_of("Chukwu", "KMU")                     # expensive, barely playing
    sig = S.signals(chukwu, MD)
    assert S.verdict(sig)["verdict"] == "SELL" and sig["minutes_last3"] < 120
    reps = S.replacements(chukwu, squad + [chukwu], MD, bank=0.5)
    assert reps and all(r["price"] <= sig["price"] + 0.5 and r["player_id"] not in squad for r in reps)
    assert all(S.load()["players"][r["player_id"]]["position"] == "FWD" for r in reps)


def test_calls_fair_odds_and_settlement():
    m = load_match(MATCH)
    st = MatchState(m["metadata"], load_models())
    cb = CallBook(st)
    for ev in m["events"][:10]:
        st.update(ev)
    assert payout(0.5) == 20 and payout(0.25) == 40
    q = cb.quotes()
    assert q["open"] and abs(sum(q["next_goal"].values()) - 1) < 1e-3
    peiro = pid_of("Peiró", "THR")
    c1 = cb.place("fan", "scorer", peiro)
    c2 = cb.place("fan", "next_goal", "home")
    cb.place("fan", "next_goal", "none")
    with pytest.raises(ValueError):                       # at most 3 open calls
        cb.place("fan", "next_goal", "away")
    for ev in m["events"][10:]:
        st.update(ev)
        cb.settle(ev)
    assert c1.status == "won" and c2.status == "lost"     # Peiró scored the opener for the away side
    board = cb.scoreboard("fan")
    assert board["won"] == 1 and board["lost"] == 2 and board["points"] == c1.pays


def test_advisor_checker_rejects_wrong_verdict_and_numbers():
    squad = S.default_squad(MD, ("C01", "C02"))
    chukwu = pid_of("Chukwu", "KMU")
    sheet = scout(chukwu, squad + [chukwu], MD)
    bad = {"headline": "Hold Chukwu", "explanation": "He scored 99 goals.", "replacement_note": "Keep him."}
    issues = check_advice(bad, sheet, [])
    assert any("verdict" in i for i in issues) and any("99" in i for i in issues)


def test_advisor_workflow_retries_and_localises():
    nr = Newsroom(Provider(ScriptedChatClient(), "Scripted", "fake"), mcp_url="http://127.0.0.1:9/mcp/")
    squad = S.default_squad(MD, ("C01", "C02"))
    chukwu = pid_of("Chukwu", "KMU")
    out = asyncio.run(advise(nr, chukwu, squad + [chukwu], MD, 0.5, "es"))
    assert out["verdict"] == "SELL" and not out["fallback"]
    assert out["texts"]["en"]["headline"].startswith("Sell Chukwu")
    assert out["texts"]["es"]["headline"].startswith("[es]")
    steps = [t["step"] for t in out["trace"]]
    assert steps[:4] == ["scout", "advisor", "fact_check", "advisor"] and "localiser_es" in steps


def test_advisor_without_ai_uses_templates():
    squad = S.default_squad(MD, ("C01", "C02"))
    out = asyncio.run(advise(None, squad[0], squad, MD, 0.0, "es"))
    assert out["source"] == "templates" and set(out["texts"]) == {"en", "es"}
    json.dumps(out)                                        # serialisable for the API

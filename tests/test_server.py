"""End-to-end tests for the live server.  Run with:  python -m pytest -q"""
import json

from fastapi.testclient import TestClient

from matchlens.server import app, LOOKAHEAD_FIELDS

client = TestClient(app)


def run_to_end(ws):
    msgs = []
    while True:
        m = ws.receive_json()
        msgs.append(m)
        if m["type"] == "session" and m["payload"]["done"]:
            return msgs


def test_catalogue_has_demo_and_season_matches():
    ms = client.get("/api/matches").json()
    assert {"M000042", "M000007"} <= {m["match_id"] for m in ms}
    assert len(ms) >= 90
    assert all("score" not in m for m in ms)          # no spoilers


def test_full_match_stream():
    with client.websocket_connect("/ws/M000042?speed=5000&restart=1") as ws:
        hello = ws.receive_json()
        assert hello["type"] == "hello" and hello["payload"]["home"]["abbr"] == "THR"
        msgs = run_to_end(ws)
    seqs = [m["seq"] for m in msgs]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)
    types = {m["type"] for m in msgs}
    assert {"event", "state", "alert", "minute", "players", "session"} <= types
    final = [m for m in msgs if m["type"] == "state"][-1]["payload"]
    meta = json.load(open("data/matches/M000042/metadata.json", encoding="utf-8"))
    assert final["score"] == meta["final_score"]
    assert final["win_prob"][max(("home", "away", "draw"),
                                 key=lambda k: final["win_prob"][k])] == 1.0
    goals = [m for m in msgs if m["type"] == "alert" and m["payload"]["alert"] == "goal"]
    assert len(goals) == sum(meta["final_score"].values())


def test_no_lookahead_fields_in_events():
    with client.websocket_connect("/ws/M000007?speed=5000&restart=1") as ws:
        ws.receive_json()
        msgs = run_to_end(ws)
    for m in msgs:
        if m["type"] == "event":
            assert not LOOKAHEAD_FIELDS & set(m["payload"]["details"])


def test_from_minute_and_controls():
    with client.websocket_connect("/ws/M000007?speed=60&from_minute=70&restart=1") as ws:
        hello = ws.receive_json()
        assert hello["payload"]["state"]["display_minute"] in ("70'", "71'")
        assert len(hello["payload"]["series"]) > 60
        ws.send_text(json.dumps({"action": "pause"}))
        while True:
            m = ws.receive_json()
            if m["type"] == "session":
                assert m["payload"]["paused"]
                break
        r = client.post("/api/sessions/M000007/control", json={"action": "speed", "speed": 5000})
        assert r.json()["speed"] == 5000
        client.post("/api/sessions/M000007/control", json={"action": "resume"})
        run_to_end(ws)
    assert client.post("/api/sessions/M000007/control", json={"action": "fly"}).status_code == 400
    assert client.get("/api/matches/NOPE").status_code == 404

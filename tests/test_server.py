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


def test_fantasy_live_points_and_calls():
    meta = client.get("/api/fantasy/meta").json()
    assert meta["budget"] == 100.0
    sq = client.get("/api/fantasy/squad", params={"matchday": 10, "match_id": "AUR26-MD10-KMU-THR"}).json()
    assert len(sq["squad"]) == 15 and sq["issues"] == [] and sq["cost"] <= 100
    with client.websocket_connect("/ws/AUR26-MD10-KMU-THR?speed=5000&restart=1&viewer=tester") as ws:
        hello = ws.receive_json()
        assert hello["payload"]["fantasy"]["matchday"] == 10 and hello["payload"]["fantasy"]["quotes"]["open"]
        ws.send_text(json.dumps({"action": "call", "kind": "next_goal", "target": "away"}))
        msgs = run_to_end(ws)
    calls = [m for m in msgs if m["type"] == "calls"]
    assert any("placed" in m["payload"] for m in calls)
    assert calls[-1]["payload"]["calls"][0]["status"] in ("won", "lost")
    fantasy = [m for m in msgs if m["type"] == "fantasy"][-1]["payload"]
    assert any(any(r["code"] == "goal" for r in p["reasons"]) for p in fantasy["points"].values())
    advice = client.post("/api/fantasy/advice", json={"player_id": sq["squad"][0], "squad": sq["squad"],
                                                      "matchday": 10, "lang": "es"}).json()
    assert advice["verdict"] in ("HOLD", "WATCH", "SELL") and "es" in advice["texts"]


def test_highlights_are_published_after_the_shot():
    with client.websocket_connect("/ws/AUR26-MD10-KMU-THR?speed=5000&restart=1") as ws:
        ws.receive_json()
        msgs = run_to_end(ws)
    hls = [m["payload"] for m in msgs if m["type"] == "highlight"]
    kinds = [h["kind"] for h in hls]
    assert kinds.count("goal") == 2 and "great_save" in kinds
    goal = hls[kinds.index("goal")]
    assert goal["player"] == "Peiró" and goal["score_after"] == {"home": 0, "away": 1}
    assert all(f["t"] <= goal["t_shot"] + 1.5 for f in goal["frames"]) and goal["frames"][-1]["type"] in ("shot", "goal")
    shot_seq = next(m["seq"] for m in msgs if m["type"] == "event" and m["payload"]["type"] == "shot"
                    and m["payload"]["player_name"] == "Peiró" and m["payload"]["outcome"] == "goal")
    assert next(m["seq"] for m in msgs if m["type"] == "highlight") > shot_seq       # never before the shot

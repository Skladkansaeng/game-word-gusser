from fastapi.testclient import TestClient

from partygame.server import app


def receive_until(ws, kind):
    while True:
        msg = ws.receive_json()
        if msg["type"] == kind:
            return msg


def test_three_players_can_start_a_match_and_only_clue_givers_get_the_word():
    with TestClient(app) as client:
        code = client.post("/api/lobbies").json()["code"]
        with client.websocket_connect(f"/ws/{code}") as a, \
             client.websocket_connect(f"/ws/{code}") as b, \
             client.websocket_connect(f"/ws/{code}") as c:
            ids = {}
            for ws, name in ((a, "A"), (b, "B"), (c, "C")):
                ws.send_json({"name": name})
                ids[name] = receive_until(ws, "welcome")["playerId"]
            for ws in (b, c):
                ws.send_json({"type": "set_ready", "ready": True})
            while not all(p["ready"] for p in receive_until(a, "state")["state"]["players"]):
                pass
            a.send_json({"type": "start_match"})
            views = {}
            for ws, name in ((a, "A"), (b, "B"), (c, "C")):
                while True:
                    state = receive_until(ws, "state")["state"]
                    if state["match"]:
                        views[name] = state["match"]["round"]
                        break
            guesser = next(v["guesserId"] for v in views.values())
            for name, rnd in views.items():
                if ids[name] == guesser:
                    assert rnd["word"] is None
                else:
                    assert rnd["word"]


def test_unknown_lobby_is_refused():
    with TestClient(app) as client:
        assert client.get("/api/lobbies/ZZZZ").status_code == 404
        with client.websocket_connect("/ws/ZZZZ") as ws:
            assert ws.receive_json() == {"type": "error", "code": "lobby_not_found"}


def test_settings_sent_by_the_frontend_are_applied():
    with TestClient(app) as client:
        code = client.post("/api/lobbies").json()["code"]
        with client.websocket_connect(f"/ws/{code}") as host:
            host.send_json({"name": "A"})
            receive_until(host, "welcome")
            receive_until(host, "state")
            changes = {"playMode": "in_person", "wordLanguage": "en", "wordSource": "mixed",
                       "cycles": 2, "roundSeconds": 60, "clueSeconds": 15}
            for key, value in changes.items():
                host.send_json({"type": "update_settings", "settings": {key: value}})
                msg = host.receive_json()
                assert msg["type"] == "state", msg
                assert msg["state"]["settings"][key] == value

"""FastAPI + WebSocket transport. All game rules live in game.py; this only routes messages."""

import asyncio
import contextlib
import os
import time
from collections import defaultdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from partygame.game import GameError, Lobby, new_lobby_code

TICK_SECONDS = 0.2
LOBBY_IDLE_SECONDS = 600

lobbies: dict[str, Lobby] = {}
# lobby code -> player id -> live sockets (a player may have more than one tab open)
sockets: dict[str, dict[str, set[WebSocket]]] = defaultdict(lambda: defaultdict(set))


async def broadcast(lobby: Lobby) -> None:
    now = time.time()
    for player_id, conns in list(sockets[lobby.code].items()):
        state = {"type": "state", "state": lobby.view(player_id, now)}
        for ws in list(conns):
            with contextlib.suppress(Exception):
                await ws.send_json(state)


async def close_kicked(lobby: Lobby, player_id: str) -> None:
    for ws in list(sockets[lobby.code].pop(player_id, ())):
        with contextlib.suppress(Exception):
            await ws.send_json({"type": "error", "code": "kicked"})
            await ws.close()


async def clock() -> None:
    while True:
        await asyncio.sleep(TICK_SECONDS)
        now = time.time()
        for code, lobby in list(lobbies.items()):
            if not lobby.any_connected() and now - lobby.last_active > LOBBY_IDLE_SECONDS:
                del lobbies[code]
                sockets.pop(code, None)
            elif lobby.tick(now):
                await broadcast(lobby)


@contextlib.asynccontextmanager
async def lifespan(_: FastAPI):
    task = asyncio.create_task(clock())
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan)


@app.get("/healthz")
def healthz() -> dict[str, int]:
    return {"lobbies": len(lobbies)}


@app.post("/api/lobbies")
def create_lobby() -> dict[str, str]:
    code = new_lobby_code(set(lobbies))
    lobbies[code] = Lobby(code, now=time.time())
    return {"code": code}


@app.get("/api/lobbies/{code}")
def get_lobby(code: str) -> dict[str, str]:
    if code.upper() not in lobbies:
        raise HTTPException(404, "lobby_not_found")
    return {"code": code.upper()}


def handle(lobby: Lobby, player_id: str, msg: dict, now: float) -> dict | None:
    """Apply one client message. Returns a private reply for the sender, if any."""
    kind = msg.get("type")
    match kind:
        case "update_settings":
            lobby.update_settings(player_id, msg.get("settings") or {})
        case "add_custom_word":
            lobby.add_custom_word(player_id, str(msg.get("text", "")))
        case "remove_custom_word":
            lobby.remove_custom_word(player_id, str(msg.get("text", "")))
        case "kick":
            lobby.kick(player_id, str(msg.get("playerId", "")))
        case "start_match":
            lobby.start_match(player_id, now)
        case "return_to_lobby":
            lobby.return_to_lobby(player_id)
        case "clue":
            lobby.submit_clue(player_id, str(msg.get("text", "")), now)
        case "preview_spoken_clue":
            syllable = lobby.preview_spoken_clue(player_id, str(msg.get("transcript", "")))
            return {"type": "spoken_clue", "syllable": syllable}
        case "buzz":
            lobby.buzz(player_id, now)
        case "guess":
            lobby.submit_guess(player_id, str(msg.get("text", "")), now)
        case "ping":
            return {"type": "pong", "serverNow": now}
        case _:
            raise GameError("unknown_message")
    return None


@app.websocket("/ws/{code}")
async def play(ws: WebSocket, code: str) -> None:
    await ws.accept()
    lobby = lobbies.get(code.upper())
    if lobby is None:
        await ws.send_json({"type": "error", "code": "lobby_not_found"})
        await ws.close()
        return

    # The first message must be a join; it either creates a player or reclaims one by token.
    try:
        hello = await ws.receive_json()
        player = lobby.join(str(hello.get("name", "")), hello.get("token"), time.time())
    except GameError as e:
        await ws.send_json({"type": "error", "code": e.code})
        await ws.close()
        return
    except (WebSocketDisconnect, ValueError, AttributeError):
        return

    sockets[lobby.code][player.id].add(ws)
    await ws.send_json({"type": "welcome", "playerId": player.id, "token": player.token})
    await broadcast(lobby)
    try:
        while True:
            msg = await ws.receive_json()
            if lobby.players[player.id].kicked:
                await ws.send_json({"type": "error", "code": "kicked"})
                break
            try:
                reply = handle(lobby, player.id, msg, time.time())
            except GameError as e:
                await ws.send_json({"type": "error", "code": e.code})
                continue
            if reply:
                await ws.send_json(reply)
            if msg.get("type") == "kick":
                await close_kicked(lobby, str(msg.get("playerId")))
            await broadcast(lobby)
    except (WebSocketDisconnect, ValueError):
        pass
    finally:
        conns = sockets[lobby.code][player.id]
        conns.discard(ws)
        if not conns:
            lobby.disconnect(player.id, time.time())
            await broadcast(lobby)


# Serve the built frontend when it exists (production); in development Vite serves it.
_dist = Path(os.environ.get("FRONTEND_DIST") or Path(__file__).resolve().parents[3] / "frontend" / "dist")
if _dist.is_dir():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="frontend")

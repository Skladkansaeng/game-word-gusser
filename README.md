# ใบ้ทีละพยางค์

เกมปาร์ตี้บนเว็บ: Clue Giver 2 คนผลัดกันต่อคำใบ้ทีละพยางค์ ให้ Guesser ทายคำลับ
กติกาและศัพท์ทั้งหมดอยู่ใน [CONTEXT.md](CONTEXT.md) เหตุผลของการเลือก stack อยู่ใน [docs/adr/](docs/adr/)

## Development

```bash
# backend (http://localhost:8000)
cd backend && uv run uvicorn partygame.server:app --reload

# frontend (http://localhost:5173, proxies /api and /ws to the backend)
cd frontend && npm install && npm run dev
```

Tests: `cd backend && uv run pytest`

## Deploy (Docker)

```bash
docker compose up -d --build      # http://localhost:8000
```

One image holds the built frontend and the backend. Settings via env:

| Variable | Default | |
|---|---|---|
| `PORT` | `8000` | port uvicorn listens on |
| `FRONTEND_DIST` | `/app/static` | folder of the built frontend |

Things to keep in mind:

- **Run exactly one replica.** Lobbies live in process memory (ADR 0001); a second replica would see different Lobbies, and a restart drops every open Lobby.
- **The reverse proxy must pass WebSockets** on `/ws/*` (`Upgrade`/`Connection` headers) and should allow idle connections for at least a few minutes.
- **Serve over HTTPS.** Browsers only allow the microphone (speech clues) on secure origins; the frontend switches to `wss://` automatically.
- Health check: `GET /healthz`.

## Production without Docker

```bash
cd frontend && npm run build
cd ../backend && uv run uvicorn partygame.server:app --host 0.0.0.0 --port 8000
```

The backend serves `frontend/dist` when it exists. All Lobby state is in memory in one process (see ADR 0001).

# syntax=docker/dockerfile:1

# --- Frontend build --------------------------------------------------------------
FROM node:22-alpine AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Python dependencies ---------------------------------------------------------
FROM python:3.11-slim AS backend
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY backend/src ./src
RUN uv sync --locked --no-dev --no-editable

# --- Runtime -----------------------------------------------------------------------
FROM python:3.11-slim
RUN useradd --create-home --uid 1000 app
WORKDIR /app
COPY --from=backend /app/.venv /app/.venv
COPY --from=frontend /frontend/dist /app/static
ENV PATH="/app/.venv/bin:$PATH" \
    FRONTEND_DIST=/app/static \
    PYTHONUNBUFFERED=1 \
    PORT=8000
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
  CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/healthz')"
# Exactly one worker: all Lobby state lives in this process's memory (docs/adr/0001).
CMD ["sh", "-c", "exec uvicorn partygame.server:app --host 0.0.0.0 --port ${PORT} --workers 1 --proxy-headers --forwarded-allow-ips='*'"]

#!/bin/sh
set -e

# ── 1. Run pending Alembic migrations ────────────────────────────────────────
echo "[entrypoint] Running database migrations..."
alembic upgrade head
echo "[entrypoint] Migrations complete."

# ── 2. Start the API server ───────────────────────────────────────────────────
# WORKERS defaults to 1 — override via env var when scaling horizontally.
# uvloop gives a meaningful throughput boost on async-heavy workloads.
# --no-access-log keeps stdout clean; structured app logs still appear.
echo "[entrypoint] Starting uvicorn (workers=${WORKERS:-1})..."
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers "${WORKERS:-1}" \
    --loop uvloop \
    --no-access-log

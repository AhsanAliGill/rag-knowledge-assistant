#!/bin/sh
set -e

echo "[entrypoint] Running database migrations..."
alembic upgrade head
echo "[entrypoint] Migrations complete."

if [ "${DEV_RELOAD:-false}" = "true" ]; then
    echo "[entrypoint] Dev mode — starting uvicorn with hot-reload..."
    exec uvicorn app.main:app \
        --host 0.0.0.0 \
        --port 8000 \
        --reload \
        --reload-dir /app/src
else
    echo "[entrypoint] Production mode — starting uvicorn (workers=${WORKERS:-1})..."
    exec uvicorn app.main:app \
        --host 0.0.0.0 \
        --port 8000 \
        --workers "${WORKERS:-1}" \
        --loop uvloop \
        --no-access-log
fi

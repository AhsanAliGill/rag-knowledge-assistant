# ═══════════════════════════════════════════════════════════════════════════════
# Stage 1 — builder: install Python deps with uv + lockfile
# ═══════════════════════════════════════════════════════════════════════════════
FROM python:3.11-slim AS builder

# Pull uv binary from the official image (faster than pip install uv)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Build-time system libs (not carried into the runtime image)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy manifests first — cached until uv.lock changes
COPY pyproject.toml uv.lock ./
RUN touch README.md

# Install all dependencies from the lockfile, skip the project package for now
# This layer is reused on every rebuild as long as uv.lock is unchanged
RUN uv sync --frozen --no-dev --no-install-project

# Copy source then install the project itself
COPY src/ src/
RUN uv sync --frozen --no-dev


# ═══════════════════════════════════════════════════════════════════════════════
# Stage 2 — runtime: minimal image, only what's needed to serve requests
# ═══════════════════════════════════════════════════════════════════════════════
FROM python:3.11-slim AS runtime

LABEL org.opencontainers.image.title="Knowledge Assistant API"
LABEL org.opencontainers.image.description="FastAPI + RAG backend — production"

# Runtime-only libs:
#   libpq5        — asyncpg / psycopg2 PostgreSQL driver
#   libmagic1     — python-magic used by unstructured for file-type detection
#   poppler-utils — PDF page rendering used by unstructured[pdf]
#   tesseract-ocr — OCR fallback used by unstructured[pdf]
#   curl          — healthcheck probe
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        libmagic1 \
        poppler-utils \
        tesseract-ocr \
        curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1001 -s /bin/sh appuser

WORKDIR /app

# Bring the pre-built venv from the builder stage
COPY --from=builder /app/.venv /app/.venv

COPY --chown=appuser:appuser src/        src/
COPY --chown=appuser:appuser alembic/    alembic/
COPY --chown=appuser:appuser alembic.ini .

RUN mkdir -p uploads bm25_indexes ground_truth \
    && chown -R appuser:appuser /app

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER appuser

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app/src

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -sf http://localhost:8000/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]

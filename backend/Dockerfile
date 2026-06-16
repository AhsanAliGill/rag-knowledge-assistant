# ═══════════════════════════════════════════════════════════════════════════════
# Stage 1 — builder: resolve + install all Python deps into an isolated venv
# ═══════════════════════════════════════════════════════════════════════════════
FROM python:3.11-slim AS builder

WORKDIR /build

# Build-time system libraries (not carried into runtime image)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        libffi-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# uv — significantly faster than pip for large dependency trees
RUN pip install --no-cache-dir uv

# Isolated venv keeps runtime stage clean
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy project manifest + source so hatchling can build the package
COPY pyproject.toml ./
# README is declared in pyproject.toml; touch it so hatchling doesn't error
RUN touch README.md
COPY src/ src/

# Install the package (pulls all [project].dependencies automatically)
RUN uv pip install --no-cache .


# ═══════════════════════════════════════════════════════════════════════════════
# Stage 2 — runtime: minimal image, only what's needed to serve requests
# ═══════════════════════════════════════════════════════════════════════════════
FROM python:3.11-slim AS runtime

LABEL org.opencontainers.image.title="Knowledge Assistant API"
LABEL org.opencontainers.image.description="FastAPI + RAG backend — production"
LABEL org.opencontainers.image.base.name="python:3.11-slim"

# Runtime libraries:
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

# Run as non-root for security
RUN useradd -m -u 1001 -s /bin/sh appuser

WORKDIR /app

# Bring in the pre-built venv from builder
COPY --from=builder /opt/venv /opt/venv

# Application source, Alembic migrations, and config
COPY --chown=appuser:appuser src/        src/
COPY --chown=appuser:appuser alembic/    alembic/
COPY --chown=appuser:appuser alembic.ini .

# Persistent data directories — mount these as Docker volumes in production
#   uploads/       — uploaded PDF files
#   bm25_indexes/  — BM25 keyword index files (per-user)
#   ground_truth/  — evaluation Q&A pairs
RUN mkdir -p uploads bm25_indexes ground_truth \
    && chown -R appuser:appuser /app

# Entrypoint: runs migrations then starts uvicorn
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER appuser

ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
# src/ on the path so `from app.xxx import` works without package install tricks
ENV PYTHONPATH=/app/src

EXPOSE 8000

# /health returns {"status":"ok"} — zero-dependency probe via curl
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -sf http://localhost:8000/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]

import asyncio
import os
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from unittest.mock import patch

import bcrypt as _bcrypt
import psycopg2
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

import app.main as main_module
from app.core.config import settings
from app.db.session import get_session
from app.main import app

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Import all models so SQLModel.metadata is fully populated before any fixture runs
from app.models.chunk import RAGChunk  # noqa: F401
from app.models.conversation import RAGConversation, RAGConversationMessage  # noqa: F401
from app.models.document import RAGDocument  # noqa: F401
from app.models.evaluation import RAGEvaluation, RAGEvaluationResult  # noqa: F401
from app.models.ingestion_job import RAGIngestionJob  # noqa: F401
from app.models.user import User  # noqa: F401

TEST_USER = {
    "username": "testuser",
    "email": "test@example.com",
    "password": "TestPass123!",
}

TEST_USER2 = {
    "username": "testuser2",
    "email": "test2@example.com",
    "password": "TestPass456!",
}


@pytest.fixture(scope="session", autouse=True)
def fast_bcrypt():
    """Use bcrypt rounds=4 in tests instead of the default 12.
    rounds=4 is ~64x faster and still exercises the full hash/verify path.
    Capture the real function first — calling _bcrypt.gensalt() inside the
    patch would hit the mock again and recurse infinitely.
    """
    real_gensalt = _bcrypt.gensalt
    with patch("bcrypt.gensalt", side_effect=lambda *a, **kw: real_gensalt(rounds=4)):
        yield


def _worker_schema() -> str:
    """Return a per-worker PostgreSQL schema name.

    pytest-xdist sets PYTEST_XDIST_WORKER ('gw0', 'gw1', …) in each worker
    process. Falls back to 'main' for single-process runs.
    This is more reliable than request.config.workerinput which can return {}
    in some xdist/pytest version combinations.
    """
    return f"test_{os.environ.get('PYTEST_XDIST_WORKER', 'main')}"


def _sync_dsn() -> str:
    """psycopg2-compatible DSN derived from the async TEST_DATABASE_URL.

    Strips all query parameters because asyncpg-specific params like ?ssl=...
    are not valid psycopg2 URI parameters and cause ProgrammingError.
    """
    from urllib.parse import urlparse, urlunparse

    url = settings.TEST_DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)
    parsed = urlparse(url)
    return urlunparse(parsed._replace(query="", fragment=""))


@pytest.fixture(scope="session")
def test_engine():
    """
    One async engine per xdist worker (session scope).
    Uses NullPool so connections are never shared across event loops.
    Each worker owns its own PostgreSQL schema (test_gw0, test_gw1, …).
    """
    schema = _worker_schema()
    engine = create_async_engine(
        settings.TEST_DATABASE_URL,
        poolclass=NullPool,
        connect_args={
            "server_settings": {"search_path": schema},
            "statement_cache_size": 0,  # prevent InvalidCachedStatementError on SET search_path
        },
    )

    async def _setup() -> None:
        async with engine.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
            await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
            # Explicit SET in case server_settings isn't applied by asyncpg
            # in the asyncio.run() event loop on Windows.
            await conn.execute(text(f'SET search_path TO "{schema}"'))
            await conn.run_sync(SQLModel.metadata.create_all)

    async def _teardown() -> None:
        async with engine.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await engine.dispose()

    asyncio.run(_setup())
    yield engine
    try:
        asyncio.run(_teardown())
    except Exception:
        pass  # non-fatal: next run's _setup() will drop this schema


@pytest.fixture(scope="session")
def session_factory(test_engine):
    return async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@pytest.fixture(autouse=True)
def clean_db(test_engine):  # noqa: ARG001 — ensures schema+tables exist before first TRUNCATE
    """Fresh psycopg2 connection per test — avoids cloud DB idle-timeout killing a shared connection."""
    schema = _worker_schema()
    table_names = ", ".join(f'"{schema}"."{t.name}"' for t in SQLModel.metadata.sorted_tables)
    conn = psycopg2.connect(_sync_dsn())
    try:
        with conn.cursor() as cur:
            cur.execute(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    yield


@pytest.fixture
async def client(test_engine, session_factory) -> AsyncGenerator[AsyncClient, None]:
    schema = _worker_schema()

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            await session.execute(text(f'SET search_path TO "{schema}"'))
            yield session

    app.dependency_overrides[get_session] = override_get_session

    @asynccontextmanager
    async def _noop_lifespan(_app):
        """Skip the real lifespan (create_all + dispose) — tables already exist
        from the session-scoped test_engine setup, and running create_all on
        every test wastes 8+ DB round-trips per test function."""
        yield

    with (
        patch.object(main_module, "engine", test_engine),
        patch.object(app.router, "lifespan_context", _noop_lifespan),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def registered_user(client: AsyncClient) -> dict:
    response = await client.post("/api/v1/auth/register", json=TEST_USER)
    assert response.status_code == 201
    return TEST_USER


@pytest.fixture
async def auth_token(client: AsyncClient, registered_user: dict) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": registered_user["email"],
            "password": registered_user["password"],
        },
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
async def registered_user2(client: AsyncClient) -> dict:
    response = await client.post("/api/v1/auth/register", json=TEST_USER2)
    assert response.status_code == 201
    return TEST_USER2


@pytest.fixture
async def auth_token2(client: AsyncClient, registered_user2: dict) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": registered_user2["email"],
            "password": registered_user2["password"],
        },
    )
    assert response.status_code == 200
    return response.json()["access_token"]

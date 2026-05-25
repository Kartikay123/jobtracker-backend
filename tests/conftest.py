"""Shared pytest fixtures.

Strategy:
- One dedicated Postgres database `jobtracker_test`, created once per session
  using SQLAlchemy's `Base.metadata.create_all` (no Alembic — faster, and
  exercises the model definitions directly).
- Tables truncated before each test for isolation.
- Real Redis, FLUSHDB before each test (cache + rate-limit cleanup).
- App's `get_db` and `get_arq` deps overridden so we don't need to spin up
  the real lifespan (no arq pool, no real Redis pool from the app).
- Async test client via httpx.AsyncClient + ASGITransport (no actual server).
"""

from typing import AsyncGenerator
from urllib.parse import urlparse

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.queue import get_arq
from app.core.redis import redis_client
from app.db.base import Base
from app.db.deps import get_db
from app.main import app
from app.models import User as _UserModel  # noqa: F401 — register on metadata

# ---------------------------------------------------------------------------
# Test database wiring
# ---------------------------------------------------------------------------
TEST_DB_NAME = "jobtracker_test"

# Build a URL pointing at the test DB while keeping the original credentials.
_parsed = urlparse(settings.DATABASE_URL)
_admin_url = settings.DATABASE_URL.rsplit("/", 1)[0] + "/postgres"  # admin DB
_test_url = settings.DATABASE_URL.rsplit("/", 1)[0] + f"/{TEST_DB_NAME}"

# NullPool: don't cache connections across the loop boundary. Tests run in
# a session-wide loop, but defensive — and the perf hit is negligible at
# this scale (every test is a fresh connection anyway).
test_engine = create_async_engine(_test_url, future=True, poolclass=NullPool)
TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    """Drop-in replacement for `app.db.deps.get_db` during tests."""
    async with TestSessionLocal() as session:
        yield session


class _StubArq:
    """No-op stand-in for `app.state.arq` so the admin endpoint tests don't
    need a live arq pool. Records calls so tests *can* assert on them later
    if we add admin-endpoint tests.
    """

    def __init__(self) -> None:
        self.enqueued: list[tuple] = []

    async def enqueue_job(self, name: str, *args, **kwargs):
        self.enqueued.append((name, args, kwargs))
        return type("Job", (), {"job_id": f"stub-{len(self.enqueued)}"})()


_stub_arq = _StubArq()


async def override_get_arq() -> _StubArq:
    return _stub_arq


# Apply overrides at module load — safe because tests are the only consumers.
app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_arq] = override_get_arq


# ---------------------------------------------------------------------------
# Session-scoped: create test DB and schema once
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture(scope="session", autouse=True)
async def _setup_test_database():
    """Create `jobtracker_test` and apply the schema once for the session."""
    # Drop+recreate the test DB via the admin connection (must be AUTOCOMMIT).
    admin_engine = create_async_engine(
        _admin_url, isolation_level="AUTOCOMMIT", future=True
    )
    async with admin_engine.connect() as conn:
        await conn.execute(text(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}"'))
        await conn.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
    await admin_engine.dispose()

    # Build the schema directly from ORM metadata.
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    await test_engine.dispose()


# ---------------------------------------------------------------------------
# Per-test: truncate tables and flush Redis
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture(autouse=True)
async def _isolate_state():
    """Wipe DB tables and Redis before every test."""
    async with test_engine.begin() as conn:
        # CASCADE handles FK chains; RESTART IDENTITY resets sequences so
        # each test sees user_id=1, job_id=1, etc. (helpful for assertions).
        tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
        await conn.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))

    await redis_client.flushdb()
    yield


# ---------------------------------------------------------------------------
# HTTP client + auth helpers
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Plain async test client — no auth header pre-set."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c


async def _signup_user(
    client: AsyncClient,
    name: str = "Alice",
    email: str = "alice@example.com",
    password: str = "hunter2hunter",
) -> dict:
    """Create a user and return the parsed signup response (token + user)."""
    resp = await client.post(
        "/api/auth/signup",
        json={"name": name, "email": email, "password": password},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest_asyncio.fixture
async def alice(client: AsyncClient) -> dict:
    """Default authenticated user. Returns {token, headers, user}."""
    body = await _signup_user(client, "Alice", "alice@example.com")
    return {
        "token": body["accessToken"],
        "headers": {"Authorization": f"Bearer {body['accessToken']}"},
        "user": body["user"],
    }


@pytest_asyncio.fixture
async def bob(client: AsyncClient) -> dict:
    """A second user for ownership-isolation tests."""
    body = await _signup_user(client, "Bob", "bob@example.com")
    return {
        "token": body["accessToken"],
        "headers": {"Authorization": f"Bearer {body['accessToken']}"},
        "user": body["user"],
    }

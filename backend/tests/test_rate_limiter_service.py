"""Unit tests for rate_limiter_service — InMemory, Postgres, and factory."""

import time

import pytest

from app.auth_usermanagement.services.rate_limiter_service import (
    InMemoryRateLimiter,
    PostgresRateLimiter,
    create_rate_limiter,
)
from app.database import Base
from tests.async_test_utils import make_test_db, make_async_app


# ── InMemoryRateLimiter ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_allows_requests_under_limit():
    limiter = InMemoryRateLimiter()
    assert await limiter.is_rate_limited("key1", limit=3, window_seconds=60) is False
    assert await limiter.is_rate_limited("key1", limit=3, window_seconds=60) is False
    assert await limiter.is_rate_limited("key1", limit=3, window_seconds=60) is False


@pytest.mark.asyncio
async def test_blocks_requests_over_limit():
    limiter = InMemoryRateLimiter()
    for _ in range(5):
        await limiter.is_rate_limited("flood", limit=5, window_seconds=60)

    assert await limiter.is_rate_limited("flood", limit=5, window_seconds=60) is True


@pytest.mark.asyncio
async def test_different_keys_are_independent():
    limiter = InMemoryRateLimiter()
    for _ in range(3):
        await limiter.is_rate_limited("a", limit=3, window_seconds=60)

    assert await limiter.is_rate_limited("a", limit=3, window_seconds=60) is True
    assert await limiter.is_rate_limited("b", limit=3, window_seconds=60) is False


@pytest.mark.asyncio
async def test_window_expiration_allows_new_requests():
    limiter = InMemoryRateLimiter()
    # Fill to limit with a 1-second window
    for _ in range(2):
        await limiter.is_rate_limited("expire", limit=2, window_seconds=1)

    assert await limiter.is_rate_limited("expire", limit=2, window_seconds=1) is True

    # Wait for window to pass
    import asyncio
    await asyncio.sleep(1.1)

    assert await limiter.is_rate_limited("expire", limit=2, window_seconds=1) is False


@pytest.mark.asyncio
async def test_limit_of_one():
    limiter = InMemoryRateLimiter()
    assert await limiter.is_rate_limited("single", limit=1, window_seconds=60) is False
    assert await limiter.is_rate_limited("single", limit=1, window_seconds=60) is True


@pytest.mark.asyncio
async def test_close_is_noop():
    limiter = InMemoryRateLimiter()
    await limiter.close()  # Should not raise


# ── Factory ──────────────────────────────────────────────────────


def test_create_rate_limiter_returns_in_memory_by_default():
    limiter = create_rate_limiter()
    assert isinstance(limiter, InMemoryRateLimiter)


def test_create_rate_limiter_returns_postgres_when_factory_provided():
    from app.auth_usermanagement.services.rate_limiter_service import PostgresRateLimiter

    limiter = create_rate_limiter(db_factory=lambda: None)
    assert isinstance(limiter, PostgresRateLimiter)


# ── PostgresRateLimiter (SQLite stand-in) ─────────────────────────────


def _make_db():
    return make_test_db()


@pytest.mark.asyncio
async def test_postgres_limiter_allows_under_limit():
    sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
    try:
        limiter = PostgresRateLimiter(db_factory=AsyncSessionLocal)
        assert await limiter.is_rate_limited("pg-key", limit=3, window_seconds=60) is False
        assert await limiter.is_rate_limited("pg-key", limit=3, window_seconds=60) is False
    finally:
        Base.metadata.drop_all(sync_engine)


@pytest.mark.asyncio
async def test_postgres_limiter_blocks_over_limit():
    sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
    try:
        limiter = PostgresRateLimiter(db_factory=AsyncSessionLocal)
        for _ in range(5):
            await limiter.is_rate_limited("pg-flood", limit=5, window_seconds=60)

        assert await limiter.is_rate_limited("pg-flood", limit=5, window_seconds=60) is True
    finally:
        Base.metadata.drop_all(sync_engine)


@pytest.mark.asyncio
async def test_postgres_limiter_independent_keys():
    sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
    try:
        limiter = PostgresRateLimiter(db_factory=AsyncSessionLocal)
        for _ in range(2):
            await limiter.is_rate_limited("pg-a", limit=2, window_seconds=60)

        assert await limiter.is_rate_limited("pg-a", limit=2, window_seconds=60) is True
        assert await limiter.is_rate_limited("pg-b", limit=2, window_seconds=60) is False
    finally:
        Base.metadata.drop_all(sync_engine)


@pytest.mark.asyncio
async def test_postgres_limiter_fails_open_on_db_error():
    """When the DB factory raises, the limiter should fail open (allow)."""

    def broken_factory():
        raise RuntimeError("DB down")

    limiter = PostgresRateLimiter(db_factory=broken_factory)
    # Should NOT raise — returns False (allow the request)
    assert await limiter.is_rate_limited("broken", limit=1, window_seconds=60) is False


@pytest.mark.asyncio
async def test_postgres_limiter_close_is_noop():
    sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
    try:
        limiter = PostgresRateLimiter(db_factory=AsyncSessionLocal)
        await limiter.close()  # Should not raise
    finally:
        Base.metadata.drop_all(sync_engine)

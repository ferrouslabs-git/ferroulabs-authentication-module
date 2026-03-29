"""Unit tests for rate_limiter_service — InMemory, Postgres, and factory."""

import time

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth_usermanagement.services.rate_limiter_service import (
    InMemoryRateLimiter,
    PostgresRateLimiter,
    create_rate_limiter,
)
from app.database import Base


# ── InMemoryRateLimiter ─────────────────────────────────────────


def test_allows_requests_under_limit():
    limiter = InMemoryRateLimiter()
    assert limiter.is_rate_limited("key1", limit=3, window_seconds=60) is False
    assert limiter.is_rate_limited("key1", limit=3, window_seconds=60) is False
    assert limiter.is_rate_limited("key1", limit=3, window_seconds=60) is False


def test_blocks_requests_over_limit():
    limiter = InMemoryRateLimiter()
    for _ in range(5):
        limiter.is_rate_limited("flood", limit=5, window_seconds=60)

    assert limiter.is_rate_limited("flood", limit=5, window_seconds=60) is True


def test_different_keys_are_independent():
    limiter = InMemoryRateLimiter()
    for _ in range(3):
        limiter.is_rate_limited("a", limit=3, window_seconds=60)

    assert limiter.is_rate_limited("a", limit=3, window_seconds=60) is True
    assert limiter.is_rate_limited("b", limit=3, window_seconds=60) is False


def test_window_expiration_allows_new_requests():
    limiter = InMemoryRateLimiter()
    # Fill to limit with a 1-second window
    for _ in range(2):
        limiter.is_rate_limited("expire", limit=2, window_seconds=1)

    assert limiter.is_rate_limited("expire", limit=2, window_seconds=1) is True

    # Wait for window to pass
    time.sleep(1.1)

    assert limiter.is_rate_limited("expire", limit=2, window_seconds=1) is False


def test_limit_of_one():
    limiter = InMemoryRateLimiter()
    assert limiter.is_rate_limited("single", limit=1, window_seconds=60) is False
    assert limiter.is_rate_limited("single", limit=1, window_seconds=60) is True


def test_close_is_noop():
    limiter = InMemoryRateLimiter()
    limiter.close()  # Should not raise


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
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return engine, SessionLocal


def test_postgres_limiter_allows_under_limit():
    engine, SessionLocal = _make_db()
    try:
        limiter = PostgresRateLimiter(db_factory=SessionLocal)
        assert limiter.is_rate_limited("pg-key", limit=3, window_seconds=60) is False
        assert limiter.is_rate_limited("pg-key", limit=3, window_seconds=60) is False
    finally:
        Base.metadata.drop_all(engine)


def test_postgres_limiter_blocks_over_limit():
    engine, SessionLocal = _make_db()
    try:
        limiter = PostgresRateLimiter(db_factory=SessionLocal)
        for _ in range(5):
            limiter.is_rate_limited("pg-flood", limit=5, window_seconds=60)

        assert limiter.is_rate_limited("pg-flood", limit=5, window_seconds=60) is True
    finally:
        Base.metadata.drop_all(engine)


def test_postgres_limiter_independent_keys():
    engine, SessionLocal = _make_db()
    try:
        limiter = PostgresRateLimiter(db_factory=SessionLocal)
        for _ in range(2):
            limiter.is_rate_limited("pg-a", limit=2, window_seconds=60)

        assert limiter.is_rate_limited("pg-a", limit=2, window_seconds=60) is True
        assert limiter.is_rate_limited("pg-b", limit=2, window_seconds=60) is False
    finally:
        Base.metadata.drop_all(engine)


def test_postgres_limiter_fails_open_on_db_error():
    """When the DB factory raises, the limiter should fail open (allow)."""

    def broken_factory():
        raise RuntimeError("DB down")

    limiter = PostgresRateLimiter(db_factory=broken_factory)
    # Should NOT raise — returns False (allow the request)
    assert limiter.is_rate_limited("broken", limit=1, window_seconds=60) is False


def test_postgres_limiter_close_is_noop():
    engine, SessionLocal = _make_db()
    try:
        limiter = PostgresRateLimiter(db_factory=SessionLocal)
        limiter.close()  # Should not raise
    finally:
        Base.metadata.drop_all(engine)

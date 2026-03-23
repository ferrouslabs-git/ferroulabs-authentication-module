"""Unit tests for rate_limiter_service — InMemory and factory."""

import time

from app.auth_usermanagement.services.rate_limiter_service import (
    InMemoryRateLimiter,
    create_rate_limiter,
)


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

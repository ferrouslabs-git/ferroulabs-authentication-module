"""Tests for P0 production hardening items.

Covers:
- P0-1: pool_pre_ping + pool_recycle on database engine
- P0-2: /debug-token gated behind AUTH_DEBUG env var
- P0-3: Refresh token security (opaque cookie_key boundary)
- P0-4: Rate limiter logs on fail-open
"""
import logging
import os
from unittest.mock import AsyncMock, patch

import pytest

from app.database import engine
from tests.async_test_utils import make_test_db
from app.database import Base


# ── P0-1: pool_pre_ping + pool_recycle ──────────────────────────


class TestDatabasePoolConfig:
    """Verify production pool settings are applied to the async engine."""

    def test_pool_pre_ping_enabled(self):
        assert engine.pool._pre_ping is True

    def test_pool_recycle_set(self):
        assert engine.pool._recycle == 3600


# ── P0-2: /debug-token gated behind AUTH_DEBUG ──────────────────


class TestDebugTokenGating:
    """Verify the debug-token endpoint is only functional with AUTH_DEBUG."""

    def test_debug_token_returns_404_without_auth_debug(self, monkeypatch):
        monkeypatch.delenv("AUTH_DEBUG", raising=False)
        from app.auth_usermanagement.api.auth_routes import router
        from tests.async_test_utils import make_async_app

        sync_engine, SyncSession, async_engine, AsyncSessionLocal = make_test_db()
        try:
            app = make_async_app(router, async_engine, AsyncSessionLocal, prefix="/auth")
            from fastapi.testclient import TestClient
            with TestClient(app) as client:
                r = client.get("/auth/debug-token", headers={"Authorization": "Bearer fake"})
                assert r.status_code == 404
        finally:
            Base.metadata.drop_all(sync_engine)

    def test_debug_token_returns_401_with_auth_debug(self, monkeypatch):
        monkeypatch.setenv("AUTH_DEBUG", "1")
        from app.auth_usermanagement.api.auth_routes import router
        from tests.async_test_utils import make_async_app

        sync_engine, SyncSession, async_engine, AsyncSessionLocal = make_test_db()
        try:
            app = make_async_app(router, async_engine, AsyncSessionLocal, prefix="/auth")
            from fastapi.testclient import TestClient
            with TestClient(app) as client:
                # No Authorization header → 401
                r = client.get("/auth/debug-token")
                assert r.status_code == 401
        finally:
            Base.metadata.drop_all(sync_engine)

    def test_debug_token_accepts_true_string(self, monkeypatch):
        monkeypatch.setenv("AUTH_DEBUG", "true")
        from app.auth_usermanagement.api.auth_routes import router
        from tests.async_test_utils import make_async_app

        sync_engine, SyncSession, async_engine, AsyncSessionLocal = make_test_db()
        try:
            app = make_async_app(router, async_engine, AsyncSessionLocal, prefix="/auth")
            from fastapi.testclient import TestClient
            with TestClient(app) as client:
                r = client.get("/auth/debug-token")
                assert r.status_code == 401  # Endpoint active, just no auth
        finally:
            Base.metadata.drop_all(sync_engine)

    def test_debug_token_rejects_random_value(self, monkeypatch):
        monkeypatch.setenv("AUTH_DEBUG", "yes")
        from app.auth_usermanagement.api.auth_routes import router
        from tests.async_test_utils import make_async_app

        sync_engine, SyncSession, async_engine, AsyncSessionLocal = make_test_db()
        try:
            app = make_async_app(router, async_engine, AsyncSessionLocal, prefix="/auth")
            from fastapi.testclient import TestClient
            with TestClient(app) as client:
                r = client.get("/auth/debug-token", headers={"Authorization": "Bearer fake"})
                assert r.status_code == 404
        finally:
            Base.metadata.drop_all(sync_engine)


# ── P0-3: Refresh token security (opaque cookie_key) ───────────


class TestRefreshTokenSecurity:
    """Verify cookie_key is the security boundary, token roundtrips for Cognito."""

    @pytest.mark.asyncio
    async def test_stored_token_is_retrievable_for_cognito(self):
        """The raw token must survive store → get so it can be sent to Cognito."""
        from app.auth_usermanagement.services.cookie_token_service import (
            store_refresh_token, get_refresh_token,
        )

        sync_engine, SyncSession, async_engine, AsyncSessionLocal = make_test_db()
        try:
            raw_token = "cognito-refresh-token-abc123"

            async with AsyncSessionLocal() as db:
                cookie_key = await store_refresh_token(db, raw_token)

            async with AsyncSessionLocal() as db:
                result = await get_refresh_token(db, cookie_key)

            assert result == raw_token
        finally:
            Base.metadata.drop_all(sync_engine)

    @pytest.mark.asyncio
    async def test_cookie_key_is_opaque_and_unguessable(self):
        """cookie_key must be a long random string, not derived from the token."""
        from app.auth_usermanagement.services.cookie_token_service import store_refresh_token

        sync_engine, SyncSession, async_engine, AsyncSessionLocal = make_test_db()
        try:
            async with AsyncSessionLocal() as db:
                key1 = await store_refresh_token(db, "same-token")
            async with AsyncSessionLocal() as db:
                key2 = await store_refresh_token(db, "same-token")

            # Two stores of the same token produce different cookie keys
            assert key1 != key2
            # Cookie key is long enough (secrets.token_urlsafe(32) = 43 chars)
            assert len(key1) >= 40
        finally:
            Base.metadata.drop_all(sync_engine)

    @pytest.mark.asyncio
    async def test_wrong_cookie_key_returns_none(self):
        """Without the correct cookie_key, the token is inaccessible."""
        from app.auth_usermanagement.services.cookie_token_service import (
            store_refresh_token, get_refresh_token,
        )

        sync_engine, SyncSession, async_engine, AsyncSessionLocal = make_test_db()
        try:
            async with AsyncSessionLocal() as db:
                await store_refresh_token(db, "secret-token")

            async with AsyncSessionLocal() as db:
                result = await get_refresh_token(db, "wrong-key")

            assert result is None
        finally:
            Base.metadata.drop_all(sync_engine)


# ── P0-4: Rate limiter fail-open logging ────────────────────────


class TestRateLimiterFailOpenLogging:
    """Verify the PostgresRateLimiter logs when failing open on DB error."""

    @pytest.mark.asyncio
    async def test_fail_open_logs_exception(self):
        """When DB errors occur, limiter should fail open AND log the error."""
        from app.auth_usermanagement.services import rate_limiter_service
        from app.auth_usermanagement.services.rate_limiter_service import PostgresRateLimiter

        def broken_factory():
            raise RuntimeError("Connection refused")

        limiter = PostgresRateLimiter(db_factory=broken_factory)

        with patch.object(rate_limiter_service.logger, "exception") as mock_log:
            result = await limiter.is_rate_limited("test-key", limit=5, window_seconds=60)

        # Must still fail open
        assert result is False
        # Must log the error via logger.exception()
        mock_log.assert_called_once()
        log_msg = mock_log.call_args[0][0]
        assert "Rate limiter DB error" in log_msg

    @pytest.mark.asyncio
    async def test_no_log_on_normal_operation(self, caplog):
        """Normal operation should not produce error logs."""
        from app.auth_usermanagement.services.rate_limiter_service import InMemoryRateLimiter

        limiter = InMemoryRateLimiter()

        with caplog.at_level(logging.ERROR, logger="app.auth_usermanagement.services.rate_limiter_service"):
            result = await limiter.is_rate_limited("clean-key", limit=10, window_seconds=60)

        assert result is False
        assert len(caplog.records) == 0

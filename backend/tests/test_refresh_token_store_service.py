"""Unit tests for DB-backed refresh token store helpers."""
from datetime import UTC, datetime, timedelta

import pytest

from app.auth_usermanagement.services import cookie_token_service as svc


@pytest.mark.asyncio
async def test_store_and_get_refresh_token_roundtrip(dual_session):
    sync_db, async_db = dual_session
    key = await svc.store_refresh_token(async_db, "refresh-1")
    assert key
    assert await svc.get_refresh_token(async_db, key) == "refresh-1"


@pytest.mark.asyncio
async def test_rotate_refresh_token_replaces_old_key(dual_session):
    sync_db, async_db = dual_session
    old_key = await svc.store_refresh_token(async_db, "refresh-old")
    new_key = await svc.rotate_refresh_token(async_db, old_key, "refresh-new")

    assert new_key != old_key
    assert await svc.get_refresh_token(async_db, old_key) is None
    assert await svc.get_refresh_token(async_db, new_key) == "refresh-new"


@pytest.mark.asyncio
async def test_revoke_refresh_token_removes_key(dual_session):
    sync_db, async_db = dual_session
    key = await svc.store_refresh_token(async_db, "refresh-1")
    await svc.revoke_refresh_token(async_db, key)
    assert await svc.get_refresh_token(async_db, key) is None


@pytest.mark.asyncio
async def test_get_refresh_token_purges_expired_records(dual_session, monkeypatch):
    sync_db, async_db = dual_session
    key = await svc.store_refresh_token(async_db, "refresh-expiring")
    future_now = datetime.now(UTC) + timedelta(days=31)
    monkeypatch.setattr(svc, "_utc_now", lambda: future_now)

    assert await svc.get_refresh_token(async_db, key) is None

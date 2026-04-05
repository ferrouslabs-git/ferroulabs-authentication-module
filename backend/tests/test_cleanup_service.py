"""Tests for cleanup_service — verify expired/stale row removal."""
import pytest
from datetime import timedelta
from uuid import uuid4

from app.auth_usermanagement.models.audit_event import AuditEvent, utc_now as audit_utc
from app.auth_usermanagement.models.invitation import Invitation
from app.auth_usermanagement.models.rate_limit_hit import RateLimitHit
from app.auth_usermanagement.models.refresh_token import RefreshTokenStore
from app.auth_usermanagement.services.cleanup_service import (
    CleanupResult,
    purge_expired_refresh_tokens,
    purge_old_audit_events,
    purge_old_rate_limit_hits,
    purge_stale_invitations,
    run_cleanup,
)


def _now():
    return audit_utc()


# ── Refresh tokens ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_purge_expired_refresh_tokens_removes_expired(dual_session):
    sync_db, async_db = dual_session
    now = _now()
    sync_db.add(RefreshTokenStore(cookie_key="expired-1", refresh_token="t", expires_at=now - timedelta(hours=1)))
    sync_db.add(RefreshTokenStore(cookie_key="valid-1", refresh_token="t", expires_at=now + timedelta(hours=1)))
    sync_db.commit()

    removed = await purge_expired_refresh_tokens(async_db)
    await async_db.commit()

    assert removed == 1
    sync_db.expire_all()
    remaining = sync_db.query(RefreshTokenStore).all()
    assert len(remaining) == 1
    assert remaining[0].cookie_key == "valid-1"


# ── Invitations ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_purge_stale_invitations_removes_old_expired(dual_session):
    sync_db, async_db = dual_session
    now = _now()
    tenant_id = uuid4()
    sync_db.add(Invitation(
        id=uuid4(), tenant_id=tenant_id, email="old@x.com",
        token="h1", token_hash="h1",
        expires_at=now - timedelta(days=60),
        created_at=now - timedelta(days=61),
        target_scope_type="account", target_scope_id=tenant_id, target_role_name="account_member",
    ))
    sync_db.add(Invitation(
        id=uuid4(), tenant_id=tenant_id, email="recent@x.com",
        token="h2", token_hash="h2",
        expires_at=now - timedelta(days=1),
        created_at=now - timedelta(days=3),
        target_scope_type="account", target_scope_id=tenant_id, target_role_name="account_member",
    ))
    sync_db.add(Invitation(
        id=uuid4(), tenant_id=tenant_id, email="active@x.com",
        token="h3", token_hash="h3",
        expires_at=now + timedelta(days=5),
        created_at=now - timedelta(days=1),
        target_scope_type="account", target_scope_id=tenant_id, target_role_name="account_member",
    ))
    sync_db.commit()

    removed = await purge_stale_invitations(async_db)
    await async_db.commit()

    assert removed == 1
    sync_db.expire_all()
    assert sync_db.query(Invitation).count() == 2


@pytest.mark.asyncio
async def test_purge_stale_invitations_removes_old_revoked(dual_session):
    sync_db, async_db = dual_session
    now = _now()
    tenant_id = uuid4()
    sync_db.add(Invitation(
        id=uuid4(), tenant_id=tenant_id, email="revoked@x.com",
        token="h4", token_hash="h4",
        expires_at=now + timedelta(days=5),
        revoked_at=now - timedelta(days=40),
        created_at=now - timedelta(days=45),
        target_scope_type="account", target_scope_id=tenant_id, target_role_name="account_member",
    ))
    sync_db.commit()

    removed = await purge_stale_invitations(async_db)
    await async_db.commit()

    assert removed == 1


# ── Rate limit hits ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_purge_old_rate_limit_hits_removes_stale(dual_session):
    sync_db, async_db = dual_session
    now = _now()
    sync_db.add(RateLimitHit(id=uuid4(), key="ip:1.2.3.4", hit_at=now - timedelta(hours=25)))
    sync_db.add(RateLimitHit(id=uuid4(), key="ip:1.2.3.4", hit_at=now - timedelta(minutes=30)))
    sync_db.commit()

    removed = await purge_old_rate_limit_hits(async_db)
    await async_db.commit()

    assert removed == 1
    sync_db.expire_all()
    assert sync_db.query(RateLimitHit).count() == 1


# ── Audit events ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_purge_old_audit_events_removes_old(dual_session):
    sync_db, async_db = dual_session
    now = _now()
    sync_db.add(AuditEvent(id=uuid4(), timestamp=now - timedelta(days=400), action="login"))
    sync_db.add(AuditEvent(id=uuid4(), timestamp=now - timedelta(days=100), action="login"))
    sync_db.commit()

    removed = await purge_old_audit_events(async_db)
    await async_db.commit()

    assert removed == 1
    sync_db.expire_all()
    assert sync_db.query(AuditEvent).count() == 1


@pytest.mark.asyncio
async def test_purge_old_audit_events_skips_when_zero(dual_session):
    sync_db, async_db = dual_session
    now = _now()
    sync_db.add(AuditEvent(id=uuid4(), timestamp=now - timedelta(days=400), action="login"))
    sync_db.commit()

    removed = await purge_old_audit_events(async_db, older_than_days=0)
    await async_db.commit()

    assert removed == 0
    sync_db.expire_all()
    assert sync_db.query(AuditEvent).count() == 1


# ── run_cleanup (integrated) ────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_cleanup_returns_result(dual_session):
    sync_db, async_db = dual_session
    now = _now()
    tenant_id = uuid4()
    sync_db.add(RefreshTokenStore(cookie_key="e", refresh_token="t", expires_at=now - timedelta(hours=1)))
    sync_db.add(Invitation(
        id=uuid4(), tenant_id=tenant_id, email="x@x.com",
        token="hx", token_hash="hx",
        expires_at=now - timedelta(days=60),
        created_at=now - timedelta(days=61),
        target_scope_type="account", target_scope_id=tenant_id, target_role_name="account_member",
    ))
    sync_db.add(RateLimitHit(id=uuid4(), key="k", hit_at=now - timedelta(hours=25)))
    sync_db.add(AuditEvent(id=uuid4(), timestamp=now - timedelta(days=400), action="x"))
    sync_db.commit()

    result = await run_cleanup(async_db)
    await async_db.commit()

    assert isinstance(result, CleanupResult)
    assert result.refresh_tokens == 1
    assert result.invitations == 1
    assert result.rate_limit_hits == 1
    assert result.audit_events == 1


@pytest.mark.asyncio
async def test_run_cleanup_is_idempotent(dual_session):
    sync_db, async_db = dual_session
    now = _now()
    sync_db.add(RefreshTokenStore(cookie_key="e2", refresh_token="t", expires_at=now - timedelta(hours=1)))
    sync_db.commit()

    first = await run_cleanup(async_db)
    await async_db.commit()
    second = await run_cleanup(async_db)
    await async_db.commit()

    assert first.refresh_tokens == 1
    assert second.refresh_tokens == 0


@pytest.mark.asyncio
async def test_run_cleanup_preserves_valid_records(dual_session):
    sync_db, async_db = dual_session
    now = _now()
    tenant_id = uuid4()
    sync_db.add(RefreshTokenStore(cookie_key="ok", refresh_token="t", expires_at=now + timedelta(hours=1)))
    sync_db.add(Invitation(
        id=uuid4(), tenant_id=tenant_id, email="ok@x.com",
        token="ok", token_hash="ok",
        expires_at=now + timedelta(days=5),
        created_at=now,
        target_scope_type="account", target_scope_id=tenant_id, target_role_name="account_member",
    ))
    sync_db.add(RateLimitHit(id=uuid4(), key="k", hit_at=now))
    sync_db.add(AuditEvent(id=uuid4(), timestamp=now, action="login"))
    sync_db.commit()

    result = await run_cleanup(async_db)
    await async_db.commit()

    assert result.refresh_tokens == 0
    assert result.invitations == 0
    assert result.rate_limit_hits == 0
    assert result.audit_events == 0

"""Tests for cleanup_service — verify expired/stale row removal."""
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


def test_purge_expired_refresh_tokens_removes_expired(db_session):
    now = _now()
    db_session.add(RefreshTokenStore(cookie_key="expired-1", refresh_token="t", expires_at=now - timedelta(hours=1)))
    db_session.add(RefreshTokenStore(cookie_key="valid-1", refresh_token="t", expires_at=now + timedelta(hours=1)))
    db_session.commit()

    removed = purge_expired_refresh_tokens(db_session)
    db_session.commit()

    assert removed == 1
    remaining = db_session.query(RefreshTokenStore).all()
    assert len(remaining) == 1
    assert remaining[0].cookie_key == "valid-1"


# ── Invitations ─────────────────────────────────────────────────────


def test_purge_stale_invitations_removes_old_expired(db_session):
    now = _now()
    tenant_id = uuid4()
    # Old expired invitation (>30 days)
    db_session.add(Invitation(
        id=uuid4(), tenant_id=tenant_id, email="old@x.com",
        token="h1", token_hash="h1",
        expires_at=now - timedelta(days=60),
        created_at=now - timedelta(days=61),
        target_scope_type="account", target_scope_id=tenant_id, target_role_name="account_member",
    ))
    # Recent expired invitation (<30 days old) — should survive
    db_session.add(Invitation(
        id=uuid4(), tenant_id=tenant_id, email="recent@x.com",
        token="h2", token_hash="h2",
        expires_at=now - timedelta(days=1),
        created_at=now - timedelta(days=3),
        target_scope_type="account", target_scope_id=tenant_id, target_role_name="account_member",
    ))
    # Active pending invitation — should survive
    db_session.add(Invitation(
        id=uuid4(), tenant_id=tenant_id, email="active@x.com",
        token="h3", token_hash="h3",
        expires_at=now + timedelta(days=5),
        created_at=now - timedelta(days=1),
        target_scope_type="account", target_scope_id=tenant_id, target_role_name="account_member",
    ))
    db_session.commit()

    removed = purge_stale_invitations(db_session)
    db_session.commit()

    assert removed == 1
    assert db_session.query(Invitation).count() == 2


def test_purge_stale_invitations_removes_old_revoked(db_session):
    now = _now()
    tenant_id = uuid4()
    db_session.add(Invitation(
        id=uuid4(), tenant_id=tenant_id, email="revoked@x.com",
        token="h4", token_hash="h4",
        expires_at=now + timedelta(days=5),
        revoked_at=now - timedelta(days=40),
        created_at=now - timedelta(days=45),
        target_scope_type="account", target_scope_id=tenant_id, target_role_name="account_member",
    ))
    db_session.commit()

    removed = purge_stale_invitations(db_session)
    db_session.commit()

    assert removed == 1


# ── Rate limit hits ─────────────────────────────────────────────────


def test_purge_old_rate_limit_hits_removes_stale(db_session):
    now = _now()
    db_session.add(RateLimitHit(id=uuid4(), key="ip:1.2.3.4", hit_at=now - timedelta(hours=25)))
    db_session.add(RateLimitHit(id=uuid4(), key="ip:1.2.3.4", hit_at=now - timedelta(minutes=30)))
    db_session.commit()

    removed = purge_old_rate_limit_hits(db_session)
    db_session.commit()

    assert removed == 1
    assert db_session.query(RateLimitHit).count() == 1


# ── Audit events ────────────────────────────────────────────────────


def test_purge_old_audit_events_removes_old(db_session):
    now = _now()
    db_session.add(AuditEvent(id=uuid4(), timestamp=now - timedelta(days=400), action="login"))
    db_session.add(AuditEvent(id=uuid4(), timestamp=now - timedelta(days=100), action="login"))
    db_session.commit()

    removed = purge_old_audit_events(db_session)
    db_session.commit()

    assert removed == 1
    assert db_session.query(AuditEvent).count() == 1


def test_purge_old_audit_events_skips_when_zero(db_session):
    now = _now()
    db_session.add(AuditEvent(id=uuid4(), timestamp=now - timedelta(days=400), action="login"))
    db_session.commit()

    removed = purge_old_audit_events(db_session, older_than_days=0)
    db_session.commit()

    assert removed == 0
    assert db_session.query(AuditEvent).count() == 1


# ── run_cleanup (integrated) ────────────────────────────────────────


def test_run_cleanup_returns_result(db_session):
    now = _now()
    tenant_id = uuid4()
    # Seed one expired row per category
    db_session.add(RefreshTokenStore(cookie_key="e", refresh_token="t", expires_at=now - timedelta(hours=1)))
    db_session.add(Invitation(
        id=uuid4(), tenant_id=tenant_id, email="x@x.com",
        token="hx", token_hash="hx",
        expires_at=now - timedelta(days=60),
        created_at=now - timedelta(days=61),
        target_scope_type="account", target_scope_id=tenant_id, target_role_name="account_member",
    ))
    db_session.add(RateLimitHit(id=uuid4(), key="k", hit_at=now - timedelta(hours=25)))
    db_session.add(AuditEvent(id=uuid4(), timestamp=now - timedelta(days=400), action="x"))
    db_session.commit()

    result = run_cleanup(db_session)
    db_session.commit()

    assert isinstance(result, CleanupResult)
    assert result.refresh_tokens == 1
    assert result.invitations == 1
    assert result.rate_limit_hits == 1
    assert result.audit_events == 1


def test_run_cleanup_is_idempotent(db_session):
    now = _now()
    db_session.add(RefreshTokenStore(cookie_key="e2", refresh_token="t", expires_at=now - timedelta(hours=1)))
    db_session.commit()

    first = run_cleanup(db_session)
    db_session.commit()
    second = run_cleanup(db_session)
    db_session.commit()

    assert first.refresh_tokens == 1
    assert second.refresh_tokens == 0


def test_run_cleanup_preserves_valid_records(db_session):
    now = _now()
    tenant_id = uuid4()
    db_session.add(RefreshTokenStore(cookie_key="ok", refresh_token="t", expires_at=now + timedelta(hours=1)))
    db_session.add(Invitation(
        id=uuid4(), tenant_id=tenant_id, email="ok@x.com",
        token="ok", token_hash="ok",
        expires_at=now + timedelta(days=5),
        created_at=now,
        target_scope_type="account", target_scope_id=tenant_id, target_role_name="account_member",
    ))
    db_session.add(RateLimitHit(id=uuid4(), key="k", hit_at=now))
    db_session.add(AuditEvent(id=uuid4(), timestamp=now, action="login"))
    db_session.commit()

    result = run_cleanup(db_session)
    db_session.commit()

    assert result.refresh_tokens == 0
    assert result.invitations == 0
    assert result.rate_limit_hits == 0
    assert result.audit_events == 0

"""Background cleanup service for expired data.

Removes stale rows that accumulate over time:
- Expired refresh tokens
- Expired/revoked invitations older than 30 days
- Rate-limit hits older than 24 hours
- Audit events older than configurable retention period

Host Integration Contract
-------------------------
- Host owns: DB engine, session factory, scheduling (cron / Celery / CloudWatch)
- Module owns: cleanup query logic
- Caller provides a SQLAlchemy ``Session`` — this module never creates one.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from ..models.audit_event import AuditEvent
from ..models.invitation import Invitation
from ..models.rate_limit_hit import RateLimitHit
from ..models.refresh_token import RefreshTokenStore

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass
class CleanupResult:
    """Summary of rows removed by a single cleanup run."""

    refresh_tokens: int = 0
    invitations: int = 0
    rate_limit_hits: int = 0
    audit_events: int = 0


def purge_expired_refresh_tokens(db: Session) -> int:
    """Delete refresh tokens whose ``expires_at`` is in the past."""
    now = _utc_now()
    count = (
        db.query(RefreshTokenStore)
        .filter(RefreshTokenStore.expires_at < now)
        .delete(synchronize_session=False)
    )
    db.flush()
    return count


def purge_stale_invitations(db: Session, *, older_than_days: int = 30) -> int:
    """Delete expired or revoked invitations older than *older_than_days*."""
    cutoff = _utc_now() - timedelta(days=older_than_days)
    count = (
        db.query(Invitation)
        .filter(
            Invitation.created_at < cutoff,
            (Invitation.expires_at < _utc_now())
            | (Invitation.revoked_at.isnot(None)),
        )
        .delete(synchronize_session=False)
    )
    db.flush()
    return count


def purge_old_rate_limit_hits(db: Session, *, older_than_hours: int = 24) -> int:
    """Delete rate-limit hit records older than *older_than_hours*."""
    cutoff = _utc_now() - timedelta(hours=older_than_hours)
    count = (
        db.query(RateLimitHit)
        .filter(RateLimitHit.hit_at < cutoff)
        .delete(synchronize_session=False)
    )
    db.flush()
    return count


def purge_old_audit_events(db: Session, *, older_than_days: int = 365) -> int:
    """Delete audit events older than *older_than_days*.

    Defaults to 365 days. Pass ``0`` to skip audit cleanup entirely.
    """
    if older_than_days <= 0:
        return 0
    cutoff = _utc_now() - timedelta(days=older_than_days)
    count = (
        db.query(AuditEvent)
        .filter(AuditEvent.timestamp < cutoff)
        .delete(synchronize_session=False)
    )
    db.flush()
    return count


def run_cleanup(
    db: Session,
    *,
    invitation_days: int = 30,
    rate_limit_hours: int = 24,
    audit_retention_days: int = 365,
) -> CleanupResult:
    """Execute all cleanup tasks in a single transaction.

    The caller is responsible for committing or rolling back the session
    afterwards. Typical usage::

        db = SessionLocal()
        try:
            result = run_cleanup(db)
            db.commit()
            print(result)
        finally:
            db.close()
    """
    result = CleanupResult(
        refresh_tokens=purge_expired_refresh_tokens(db),
        invitations=purge_stale_invitations(db, older_than_days=invitation_days),
        rate_limit_hits=purge_old_rate_limit_hits(db, older_than_hours=rate_limit_hours),
        audit_events=purge_old_audit_events(db, older_than_days=audit_retention_days),
    )

    logger.info(
        "Cleanup complete: refresh_tokens=%d, invitations=%d, rate_limit_hits=%d, audit_events=%d",
        result.refresh_tokens,
        result.invitations,
        result.rate_limit_hits,
        result.audit_events,
    )
    return result

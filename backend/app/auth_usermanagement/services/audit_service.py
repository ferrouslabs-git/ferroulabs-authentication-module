"""
Security/audit event logging utilities.
"""
import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from ..models.audit_event import AuditEvent

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    """Return naive UTC datetime compatible with current log payload expectations."""
    return datetime.now(UTC).replace(tzinfo=None)


def _parse_uuid(value: str | UUID | None) -> UUID | None:
    """Safely parse UUID-like values used in audit event payloads."""
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (ValueError, TypeError):
        return None


def log_audit_event(
    event: str,
    actor_user_id: str | UUID | None = None,
    db: Session | None = None,
    **details: Any,
) -> None:
    """
    Emit a structured audit log entry and optionally persist it to database.

    Persistence is best-effort so auth flows never fail due to audit storage issues.
    """
    timestamp = utc_now()
    payload = {
        "timestamp": timestamp.isoformat(),
        "event": event,
        "actor_user_id": str(actor_user_id) if actor_user_id else None,
        "details": details,
    }
    logger.info("AUDIT %s", json.dumps(payload, default=str))

    if db is None:
        return

    tenant_id = _parse_uuid(details.get("tenant_id"))
    parsed_actor_user_id = _parse_uuid(actor_user_id)
    target_type = details.get("target_type")
    target_id = details.get("target_id")
    ip_address = details.get("ip_address")

    try:
        db.add(
            AuditEvent(
                timestamp=timestamp,
                actor_user_id=parsed_actor_user_id,
                tenant_id=tenant_id,
                action=event,
                target_type=str(target_type) if target_type else None,
                target_id=str(target_id) if target_id else None,
                ip_address=str(ip_address) if ip_address else None,
                metadata_json=details,
            )
        )
        db.flush()
    except Exception:
        logger.exception("Failed to persist audit event", extra={"event": event})

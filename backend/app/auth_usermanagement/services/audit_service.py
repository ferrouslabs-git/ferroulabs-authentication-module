"""
Security/audit event logging utilities.
"""
import json
import logging
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger("trustos.audit")


def utc_now() -> datetime:
    """Return naive UTC datetime compatible with current log payload expectations."""
    return datetime.now(UTC).replace(tzinfo=None)


def log_audit_event(event: str, actor_user_id: str | None = None, **details: Any) -> None:
    """
    Emit a structured audit log entry.

    Stored in application logs; can later be forwarded to a dedicated sink.
    """
    payload = {
        "timestamp": utc_now().isoformat(),
        "event": event,
        "actor_user_id": actor_user_id,
        "details": details,
    }
    logger.info("AUDIT %s", json.dumps(payload, default=str))

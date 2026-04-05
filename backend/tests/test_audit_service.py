from uuid import uuid4

import pytest
from sqlalchemy import select

from app.auth_usermanagement.models.audit_event import AuditEvent
from app.auth_usermanagement.services.audit_service import log_audit_event


@pytest.mark.asyncio
async def test_log_audit_event_persists_to_db_when_session_provided(async_db_session):
    actor_id = str(uuid4())
    tenant_id = str(uuid4())

    await log_audit_event(
        "tenant_created",
        actor_user_id=actor_id,
        db=async_db_session,
        tenant_id=tenant_id,
        target_type="tenant",
        target_id="tenant-123",
        tenant_name="Acme",
    )

    result = await async_db_session.execute(select(AuditEvent))
    event = result.scalar_one()
    assert event.action == "tenant_created"
    assert str(event.actor_user_id) == actor_id
    assert str(event.tenant_id) == tenant_id
    assert event.target_type == "tenant"
    assert event.target_id == "tenant-123"
    assert event.metadata_json["tenant_name"] == "Acme"


@pytest.mark.asyncio
async def test_log_audit_event_without_db_keeps_log_only_path():
    # Should not raise when DB persistence is unavailable.
    await log_audit_event("health_check", actor_user_id=None, note="log-only")

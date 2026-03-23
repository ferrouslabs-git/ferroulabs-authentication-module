"""Tests for membership and invitation scope columns (post-cleanup).

Verifies that models use scope_type/scope_id/role_name and that deprecated
columns (tenant_id, role on membership; role on invitation) have been removed.
"""
import pytest
from uuid import uuid4
from datetime import datetime, timedelta

from app.auth_usermanagement.models.membership import Membership
from app.auth_usermanagement.models.invitation import Invitation
from app.auth_usermanagement.models.tenant import Tenant
from app.auth_usermanagement.models.user import User


def _create_tenant_and_user(db):
    tenant = Tenant(id=uuid4(), name="Acme")
    user = User(
        id=uuid4(),
        cognito_sub=f"sub-{uuid4().hex[:8]}",
        email=f"{uuid4().hex[:8]}@test.com",
        name="Test User",
    )
    db.add_all([tenant, user])
    db.flush()
    return tenant, user


# ── Membership model tests ───────────────────────────────────────

def test_membership_has_scope_columns():
    assert hasattr(Membership, "scope_type")
    assert hasattr(Membership, "role_name")
    assert hasattr(Membership, "scope_id")
    assert hasattr(Membership, "granted_by")


def test_membership_deprecated_columns_removed():
    """Legacy tenant_id and role columns should no longer exist."""
    assert not hasattr(Membership, "tenant_id") or "tenant_id" not in Membership.__table__.columns
    assert not hasattr(Membership, "role") or "role" not in Membership.__table__.columns


def test_create_membership_with_scope(db_session):
    """New-style membership uses scope_type + scope_id + role_name."""
    tenant, user = _create_tenant_and_user(db_session)
    m = Membership(
        user_id=user.id,
        role_name="account_owner",
        scope_type="account",
        scope_id=tenant.id,
        status="active",
    )
    db_session.add(m)
    db_session.flush()
    assert m.scope_type == "account"
    assert m.role_name == "account_owner"
    assert m.scope_id == tenant.id


# ── Invitation model tests ───────────────────────────────────────

def test_invitation_has_scope_columns():
    assert hasattr(Invitation, "target_scope_type")
    assert hasattr(Invitation, "target_scope_id")
    assert hasattr(Invitation, "target_role_name")


def test_invitation_deprecated_role_removed():
    """Legacy role column should no longer exist on Invitation."""
    assert "role" not in Invitation.__table__.columns


def test_create_invitation_with_scope_columns(db_session):
    tenant, user = _create_tenant_and_user(db_session)
    inv = Invitation(
        tenant_id=tenant.id,
        email="new@test.com",
        token=f"tok-{uuid4().hex}",
        token_hash="abc123",
        expires_at=datetime.utcnow() + timedelta(days=7),
        created_by=user.id,
        target_scope_type="account",
        target_scope_id=tenant.id,
        target_role_name="account_admin",
    )
    db_session.add(inv)
    db_session.flush()
    assert inv.target_scope_type == "account"
    assert inv.target_role_name == "account_admin"

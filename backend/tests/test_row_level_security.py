"""
Tests for Row-Level Security (RLS) enforcement.

These tests verify that PostgreSQL RLS policies properly isolate tenant data.
"""
import pytest
from uuid import uuid4
from datetime import datetime, UTC
from sqlalchemy import text
from app.auth_usermanagement.models.tenant import Tenant
from app.auth_usermanagement.models.user import User
from app.auth_usermanagement.models.membership import Membership
from app.auth_usermanagement.models.invitation import Invitation


def utc_now():
    """Return current UTC datetime without timezone info."""
    return datetime.now(UTC).replace(tzinfo=None)


# Skip all RLS tests - they require PostgreSQL (RLS not supported in SQLite)
pytestmark = pytest.mark.skip(reason="RLS tests require PostgreSQL. Run against production database to verify RLS policies.")


def test_rls_memberships_tenant_isolation(db_session):
    """Test that RLS prevents cross-tenant membership queries."""
    # Create two tenants
    tenant_a = Tenant(name="Tenant A", status="active")
    tenant_b = Tenant(name="Tenant B", status="active")
    db_session.add(tenant_a)
    db_session.add(tenant_b)
    db_session.commit()
    
    # Create users
    user_a = User(cognito_sub="user-a-sub", email="user-a@example.com", is_active=True)
    user_b = User(cognito_sub="user-b-sub", email="user-b@example.com", is_active=True)
    db_session.add(user_a)
    db_session.add(user_b)
    db_session.commit()
    
    # Create memberships
    membership_a = Membership(user_id=user_a.id, tenant_id=tenant_a.id, role="owner", status="active")
    membership_b = Membership(user_id=user_b.id, tenant_id=tenant_b.id, role="owner", status="active")
    db_session.add(membership_a)
    db_session.add(membership_b)
    db_session.commit()
    
    # Set RLS context for tenant A
    db_session.execute(
        text("SET LOCAL app.current_tenant_id = :tenant_id"),
        {"tenant_id": str(tenant_a.id)}
    )
    db_session.execute(text("SET LOCAL app.is_platform_admin = 'false'"))
    db_session.commit()
    
    # Query should only return tenant A memberships
    memberships = db_session.query(Membership).all()
    assert len(memberships) == 1
    assert memberships[0].tenant_id == tenant_a.id
    
    # Reset session
    db_session.execute(text("RESET app.current_tenant_id"))
    db_session.execute(text("RESET app.is_platform_admin"))
    db_session.commit()
    
    # Set RLS context for tenant B
    db_session.execute(
        text("SET LOCAL app.current_tenant_id = :tenant_id"),
        {"tenant_id": str(tenant_b.id)}
    )
    db_session.execute(text("SET LOCAL app.is_platform_admin = 'false'"))
    db_session.commit()
    
    # Query should only return tenant B memberships
    memberships = db_session.query(Membership).all()
    assert len(memberships) == 1
    assert memberships[0].tenant_id == tenant_b.id


def test_rls_invitations_tenant_isolation(db_session):
    """Test that RLS prevents cross-tenant invitation queries."""
    # Create two tenants
    tenant_a = Tenant(name="Tenant A", status="active")
    tenant_b = Tenant(name="Tenant B", status="active")
    db_session.add(tenant_a)
    db_session.add(tenant_b)
    db_session.commit()
    
    # Create a creator user
    creator = User(cognito_sub="creator-sub", email="creator@example.com", is_active=True)
    db_session.add(creator)
    db_session.commit()
    
    # Create invitations for both tenants
    invite_a = Invitation(
        tenant_id=tenant_a.id,
        email="invite-a@example.com",
        role="member",
        token="token-a",
        expires_at=utc_now(),
        created_by=creator.id,
    )
    invite_b = Invitation(
        tenant_id=tenant_b.id,
        email="invite-b@example.com",
        role="member",
        token="token-b",
        expires_at=utc_now(),
        created_by=creator.id,
    )
    db_session.add(invite_a)
    db_session.add(invite_b)
    db_session.commit()
    
    # Set RLS context for tenant A
    db_session.execute(
        text("SET LOCAL app.current_tenant_id = :tenant_id"),
        {"tenant_id": str(tenant_a.id)}
    )
    db_session.execute(text("SET LOCAL app.is_platform_admin = 'false'"))
    db_session.commit()
    
    # Query should only return tenant A invitations
    invitations = db_session.query(Invitation).all()
    assert len(invitations) == 1
    assert invitations[0].tenant_id == tenant_a.id
    
    # Reset and set context for tenant B
    db_session.execute(text("RESET app.current_tenant_id"))
    db_session.execute(text("RESET app.is_platform_admin"))
    db_session.execute(
        text("SET LOCAL app.current_tenant_id = :tenant_id"),
        {"tenant_id": str(tenant_b.id)}
    )
    db_session.execute(text("SET LOCAL app.is_platform_admin = 'false'"))
    db_session.commit()
    
    # Query should only return tenant B invitations
    invitations = db_session.query(Invitation).all()
    assert len(invitations) == 1
    assert invitations[0].tenant_id == tenant_b.id


def test_rls_platform_admin_bypass(db_session):
    """Test that platform admins can see all tenant data."""
    # Create two tenants
    tenant_a = Tenant(name="Tenant A", status="active")
    tenant_b = Tenant(name="Tenant B", status="active")
    db_session.add(tenant_a)
    db_session.add(tenant_b)
    db_session.commit()
    
    # Create users
    user_a = User(cognito_sub="user-a-sub", email="user-a@example.com", is_active=True)
    user_b = User(cognito_sub="user-b-sub", email="user-b@example.com", is_active=True)
    db_session.add(user_a)
    db_session.add(user_b)
    db_session.commit()
    
    # Create memberships
    membership_a = Membership(user_id=user_a.id, tenant_id=tenant_a.id, role="owner", status="active")
    membership_b = Membership(user_id=user_b.id, tenant_id=tenant_b.id, role="owner", status="active")
    db_session.add(membership_a)
    db_session.add(membership_b)
    db_session.commit()
    
    # Set RLS context as platform admin (no specific tenant)
    db_session.execute(text("SET LOCAL app.current_tenant_id = ''"))
    db_session.execute(text("SET LOCAL app.is_platform_admin = 'true'"))
    db_session.commit()
    
    # Platform admin should see all memberships
    memberships = db_session.query(Membership).all()
    assert len(memberships) == 2


def test_rls_no_context_blocks_access(db_session):
    """Test that queries without RLS context are blocked."""
    # Create tenant and membership
    tenant = Tenant(name="Test Tenant", status="active")
    db_session.add(tenant)
    db_session.commit()
    
    user = User(cognito_sub="test-sub", email="test@example.com", is_active=True)
    db_session.add(user)
    db_session.commit()
    
    membership = Membership(user_id=user.id, tenant_id=tenant.id, role="owner", status="active")
    db_session.add(membership)
    db_session.commit()
    
    # Query without setting RLS context (no app.current_tenant_id set)
    # Should return 0 results since RLS will block access
    memberships = db_session.query(Membership).all()
    assert len(memberships) == 0

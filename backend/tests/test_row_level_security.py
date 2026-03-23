"""
Tests for Row-Level Security (RLS) enforcement.

These tests verify that PostgreSQL RLS policies properly isolate
scope-based data (memberships, invitations, spaces).
"""
import os
import pytest
from uuid import uuid4
from datetime import datetime, UTC
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.database import DATABASE_URL
from app.auth_usermanagement.models.tenant import Tenant
from app.auth_usermanagement.models.user import User
from app.auth_usermanagement.models.membership import Membership
from app.auth_usermanagement.models.invitation import Invitation
from app.auth_usermanagement.models.space import Space


def utc_now():
    """Return current UTC datetime without timezone info."""
    return datetime.now(UTC).replace(tzinfo=None)


RUN_POSTGRES_RLS_TESTS = os.getenv("RUN_POSTGRES_RLS_TESTS") == "1"

pytestmark = pytest.mark.skipif(
    not (RUN_POSTGRES_RLS_TESTS and DATABASE_URL.startswith("postgresql")),
    reason="Set RUN_POSTGRES_RLS_TESTS=1 and use PostgreSQL DATABASE_URL to run RLS tests.",
)


def _check_not_superuser():
    """Skip the entire module if the current DB role bypasses RLS."""
    if not (RUN_POSTGRES_RLS_TESTS and DATABASE_URL.startswith("postgresql")):
        return
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user")
        ).fetchone()
    engine.dispose()
    if row and row[0]:
        pytest.skip(
            "RLS tests skipped: current DB role has rolbypassrls=true (superuser). "
            "Re-run with a non-superuser role, e.g.: "
            "DATABASE_URL=postgresql://rls_tester:rls_tester_pw@localhost:5432/trustos_dev"
        )


_check_not_superuser()


def _admin_context(session):
    """Set session variables to bypass RLS for test data setup."""
    session.execute(text("SET app.is_platform_admin = 'true'"))
    session.execute(text("SET app.is_super_admin = 'true'"))
    session.execute(text("SET app.current_tenant_id = ''"))
    session.execute(text("SET app.current_scope_type = ''"))
    session.execute(text("SET app.current_scope_id = ''"))


def _clear_context(session):
    """Reset all RLS session variables."""
    session.execute(text("SET app.is_platform_admin = 'false'"))
    session.execute(text("SET app.is_super_admin = 'false'"))
    session.execute(text("RESET app.current_tenant_id"))
    session.execute(text("RESET app.current_scope_type"))
    session.execute(text("RESET app.current_scope_id"))


def _set_scope(session, scope_type, scope_id):
    """Set v3 scope context for RLS."""
    session.execute(text("SET app.current_scope_type = :st"), {"st": scope_type})
    session.execute(text("SET app.current_scope_id = :sid"), {"sid": str(scope_id)})
    session.execute(text("SET app.current_tenant_id = :tid"), {"tid": str(scope_id)})
    session.execute(text("SET app.is_platform_admin = 'false'"))
    session.execute(text("SET app.is_super_admin = 'false'"))


@pytest.fixture
def db_session() -> Session:
    """Use PostgreSQL session against migrated schema for RLS behavior tests."""
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()

    try:
        _admin_context(session)
        session.execute(text("DELETE FROM invitations"))
        session.execute(text("DELETE FROM memberships"))
        session.execute(text("DELETE FROM spaces"))
        session.execute(text("DELETE FROM sessions"))
        session.execute(text("DELETE FROM tenants"))
        session.execute(text("DELETE FROM users"))
        session.commit()

        _clear_context(session)
        session.commit()

        yield session
    finally:
        try:
            _admin_context(session)
            session.execute(text("DELETE FROM invitations"))
            session.execute(text("DELETE FROM memberships"))
            session.execute(text("DELETE FROM spaces"))
            session.execute(text("DELETE FROM sessions"))
            session.execute(text("DELETE FROM tenants"))
            session.execute(text("DELETE FROM users"))
            session.commit()
        finally:
            session.close()


# ── Membership scope isolation ───────────────────────────────────


def test_rls_memberships_account_scope_isolation(db_session):
    """Memberships in account_a are not visible with account_b scope context."""
    tenant_a = Tenant(name="Tenant A", status="active")
    tenant_b = Tenant(name="Tenant B", status="active")
    db_session.add_all([tenant_a, tenant_b])
    db_session.commit()

    user_a = User(cognito_sub="user-a-sub", email="user-a@example.com", is_active=True)
    user_b = User(cognito_sub="user-b-sub", email="user-b@example.com", is_active=True)
    db_session.add_all([user_a, user_b])
    db_session.commit()

    _admin_context(db_session)
    db_session.add(Membership(
        user_id=user_a.id,
        scope_type="account", scope_id=tenant_a.id, role_name="account_owner", status="active",
    ))
    db_session.add(Membership(
        user_id=user_b.id,
        scope_type="account", scope_id=tenant_b.id, role_name="account_owner", status="active",
    ))
    db_session.commit()

    # Scope to account A
    _set_scope(db_session, "account", tenant_a.id)
    db_session.commit()
    memberships = db_session.query(Membership).all()
    assert len(memberships) == 1
    assert memberships[0].scope_id == tenant_a.id

    # Scope to account B
    _set_scope(db_session, "account", tenant_b.id)
    db_session.commit()
    memberships = db_session.query(Membership).all()
    assert len(memberships) == 1
    assert memberships[0].scope_id == tenant_b.id


def test_rls_memberships_space_scope_isolation(db_session):
    """Memberships in space_a are not visible with space_b scope context."""
    tenant = Tenant(name="Acme", status="active")
    db_session.add(tenant)
    db_session.commit()

    user = User(cognito_sub="u-sub", email="u@example.com", is_active=True)
    db_session.add(user)
    db_session.commit()

    space_a_id = uuid4()
    space_b_id = uuid4()

    _admin_context(db_session)
    db_session.add(Membership(
        user_id=user.id,
        scope_type="space", scope_id=space_a_id, role_name="space_admin", status="active",
    ))
    db_session.add(Membership(
        user_id=user.id,
        scope_type="space", scope_id=space_b_id, role_name="space_member", status="active",
    ))
    db_session.commit()

    _set_scope(db_session, "space", space_a_id)
    db_session.commit()
    memberships = db_session.query(Membership).all()
    assert len(memberships) == 1
    assert memberships[0].scope_id == space_a_id

    _set_scope(db_session, "space", space_b_id)
    db_session.commit()
    memberships = db_session.query(Membership).all()
    assert len(memberships) == 1
    assert memberships[0].scope_id == space_b_id


# ── Invitation scope isolation ───────────────────────────────────


def test_rls_invitations_scope_isolation(db_session):
    """Invitations scoped to account_a are not visible with account_b context."""
    tenant_a = Tenant(name="Tenant A", status="active")
    tenant_b = Tenant(name="Tenant B", status="active")
    db_session.add_all([tenant_a, tenant_b])
    db_session.commit()

    creator = User(cognito_sub="creator-sub", email="creator@example.com", is_active=True)
    db_session.add(creator)
    db_session.commit()

    _admin_context(db_session)
    db_session.add(Invitation(
        tenant_id=tenant_a.id, email="a@example.com",
        token="tok-a", expires_at=utc_now(), created_by=creator.id,
        target_scope_type="account", target_scope_id=tenant_a.id, target_role_name="account_member",
    ))
    db_session.add(Invitation(
        tenant_id=tenant_b.id, email="b@example.com",
        token="tok-b", expires_at=utc_now(), created_by=creator.id,
        target_scope_type="account", target_scope_id=tenant_b.id, target_role_name="account_member",
    ))
    db_session.commit()

    _set_scope(db_session, "account", tenant_a.id)
    db_session.commit()
    invitations = db_session.query(Invitation).all()
    assert len(invitations) == 1
    assert invitations[0].tenant_id == tenant_a.id

    _set_scope(db_session, "account", tenant_b.id)
    db_session.commit()
    invitations = db_session.query(Invitation).all()
    assert len(invitations) == 1
    assert invitations[0].tenant_id == tenant_b.id


# ── Spaces account isolation ────────────────────────────────────


def test_rls_spaces_account_isolation(db_session):
    """Spaces belonging to account_a are not visible with account_b context."""
    tenant_a = Tenant(name="Tenant A", status="active")
    tenant_b = Tenant(name="Tenant B", status="active")
    db_session.add_all([tenant_a, tenant_b])
    db_session.commit()

    _admin_context(db_session)
    db_session.add(Space(name="Space A", account_id=tenant_a.id))
    db_session.add(Space(name="Space B", account_id=tenant_b.id))
    db_session.commit()

    _set_scope(db_session, "account", tenant_a.id)
    db_session.commit()
    spaces = db_session.query(Space).all()
    assert len(spaces) == 1
    assert spaces[0].account_id == tenant_a.id

    _set_scope(db_session, "account", tenant_b.id)
    db_session.commit()
    spaces = db_session.query(Space).all()
    assert len(spaces) == 1
    assert spaces[0].account_id == tenant_b.id


# ── Super admin bypass ──────────────────────────────────────────


def test_rls_super_admin_bypass(db_session):
    """is_super_admin = 'true' bypasses all scope restrictions."""
    tenant_a = Tenant(name="Tenant A", status="active")
    tenant_b = Tenant(name="Tenant B", status="active")
    db_session.add_all([tenant_a, tenant_b])
    db_session.commit()

    user_a = User(cognito_sub="user-a-sub", email="user-a@example.com", is_active=True)
    user_b = User(cognito_sub="user-b-sub", email="user-b@example.com", is_active=True)
    db_session.add_all([user_a, user_b])
    db_session.commit()

    _admin_context(db_session)
    db_session.add(Membership(
        user_id=user_a.id,
        scope_type="account", scope_id=tenant_a.id, role_name="account_owner", status="active",
    ))
    db_session.add(Membership(
        user_id=user_b.id,
        scope_type="account", scope_id=tenant_b.id, role_name="account_owner", status="active",
    ))
    db_session.commit()

    # Super admin sees all
    db_session.execute(text("SET app.current_scope_type = ''"))
    db_session.execute(text("SET app.current_scope_id = ''"))
    db_session.execute(text("SET app.current_tenant_id = ''"))
    db_session.execute(text("SET app.is_super_admin = 'true'"))
    db_session.execute(text("SET app.is_platform_admin = 'false'"))
    db_session.commit()

    memberships = db_session.query(Membership).all()
    assert len(memberships) == 2


# ── Default deny ────────────────────────────────────────────────


def test_rls_no_context_blocks_access(db_session):
    """No scope variables set → 0 rows returned."""
    tenant = Tenant(name="Test Tenant", status="active")
    db_session.add(tenant)
    db_session.commit()

    user = User(cognito_sub="test-sub", email="test@example.com", is_active=True)
    db_session.add(user)
    db_session.commit()

    _admin_context(db_session)
    db_session.add(Membership(
        user_id=user.id,
        scope_type="account", scope_id=tenant.id, role_name="account_owner", status="active",
    ))
    db_session.commit()

    _clear_context(db_session)
    db_session.commit()

    memberships = db_session.query(Membership).all()
    assert len(memberships) == 0

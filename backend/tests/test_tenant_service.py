"""Unit tests for tenant service — create, lookup, access, list."""

from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth_usermanagement.models.membership import Membership
from app.auth_usermanagement.models.tenant import Tenant
from app.auth_usermanagement.models.user import User
from app.auth_usermanagement.services.tenant_service import (
    create_tenant,
    get_tenant_by_id,
    get_user_tenants,
    get_user_tenant_role,
    list_platform_tenants,
    suspend_tenant,
    unsuspend_tenant,
    verify_user_tenant_access,
)
from app.database import Base


def _make_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return engine, SessionLocal


# ── create_tenant ────────────────────────────────────────────────


def test_create_tenant_assigns_owner_membership():
    engine, SessionLocal = _make_db()
    db = SessionLocal()

    try:
        user = User(cognito_sub="sub-1", email="creator@example.com", name="Creator")
        db.add(user)
        db.commit()
        db.refresh(user)

        tenant = create_tenant("Acme", user, db)

        assert tenant.name == "Acme"
        assert tenant.status == "active"
        assert tenant.plan == "free"

        membership = db.query(Membership).filter(
            Membership.scope_id == tenant.id,
            Membership.user_id == user.id,
        ).first()
        assert membership is not None
        assert membership.scope_type == "account"
        assert membership.role_name == "account_owner"
        assert membership.status == "active"
    finally:
        db.close()
        Base.metadata.drop_all(engine)


def test_create_tenant_with_custom_plan():
    engine, SessionLocal = _make_db()
    db = SessionLocal()

    try:
        user = User(cognito_sub="sub-2", email="u@example.com", name="U")
        db.add(user)
        db.commit()
        db.refresh(user)

        tenant = create_tenant("Beta", user, db, plan="pro")
        assert tenant.plan == "pro"
    finally:
        db.close()
        Base.metadata.drop_all(engine)


# ── get_tenant_by_id ────────────────────────────────────────────


def test_get_tenant_by_id_found():
    engine, SessionLocal = _make_db()
    db = SessionLocal()

    try:
        tenant = Tenant(name="Found")
        db.add(tenant)
        db.commit()
        db.refresh(tenant)

        result = get_tenant_by_id(tenant.id, db)
        assert result is not None
        assert result.name == "Found"
    finally:
        db.close()
        Base.metadata.drop_all(engine)


def test_get_tenant_by_id_not_found():
    engine, SessionLocal = _make_db()
    db = SessionLocal()

    try:
        result = get_tenant_by_id(uuid4(), db)
        assert result is None
    finally:
        db.close()
        Base.metadata.drop_all(engine)


# ── get_user_tenants ─────────────────────────────────────────────


def test_get_user_tenants_returns_active_account_memberships():
    engine, SessionLocal = _make_db()
    db = SessionLocal()

    try:
        user = User(cognito_sub="sub-3", email="multi@example.com", name="Multi")
        t1 = Tenant(name="T1")
        t2 = Tenant(name="T2")
        db.add_all([user, t1, t2])
        db.commit()

        db.add_all([
            Membership(user_id=user.id, scope_type="account", scope_id=t1.id,
                       role_name="account_owner", status="active"),
            Membership(user_id=user.id, scope_type="account", scope_id=t2.id,
                       role_name="account_member", status="active"),
        ])
        db.commit()

        tenants = get_user_tenants(user.id, db)
        assert len(tenants) == 2
        names = {t["name"] for t in tenants}
        assert names == {"T1", "T2"}
    finally:
        db.close()
        Base.metadata.drop_all(engine)


def test_get_user_tenants_excludes_removed_memberships():
    engine, SessionLocal = _make_db()
    db = SessionLocal()

    try:
        user = User(cognito_sub="sub-4", email="removed@example.com", name="Rem")
        t = Tenant(name="T")
        db.add_all([user, t])
        db.commit()

        db.add(Membership(user_id=user.id, scope_type="account", scope_id=t.id,
                          role_name="account_member", status="removed"))
        db.commit()

        tenants = get_user_tenants(user.id, db)
        assert tenants == []
    finally:
        db.close()
        Base.metadata.drop_all(engine)


def test_get_user_tenants_excludes_space_memberships():
    engine, SessionLocal = _make_db()
    db = SessionLocal()

    try:
        user = User(cognito_sub="sub-5", email="space@example.com", name="S")
        t = Tenant(name="T")
        db.add_all([user, t])
        db.commit()

        db.add(Membership(user_id=user.id, scope_type="space", scope_id=uuid4(),
                          role_name="space_member", status="active"))
        db.commit()

        tenants = get_user_tenants(user.id, db)
        assert tenants == []
    finally:
        db.close()
        Base.metadata.drop_all(engine)


# ── get_user_tenant_role ─────────────────────────────────────────


def test_get_user_tenant_role_returns_role_name():
    engine, SessionLocal = _make_db()
    db = SessionLocal()

    try:
        user = User(cognito_sub="sub-6", email="role@example.com", name="R")
        t = Tenant(name="T")
        db.add_all([user, t])
        db.commit()

        db.add(Membership(user_id=user.id, scope_type="account", scope_id=t.id,
                          role_name="account_admin", status="active"))
        db.commit()

        role = get_user_tenant_role(user.id, t.id, db)
        assert role == "account_admin"
    finally:
        db.close()
        Base.metadata.drop_all(engine)


def test_get_user_tenant_role_returns_none_when_no_membership():
    engine, SessionLocal = _make_db()
    db = SessionLocal()

    try:
        role = get_user_tenant_role(uuid4(), uuid4(), db)
        assert role is None
    finally:
        db.close()
        Base.metadata.drop_all(engine)


# ── verify_user_tenant_access ────────────────────────────────────


def test_verify_access_true_for_active_member():
    engine, SessionLocal = _make_db()
    db = SessionLocal()

    try:
        user = User(cognito_sub="sub-7", email="access@example.com", name="A")
        t = Tenant(name="T")
        db.add_all([user, t])
        db.commit()

        db.add(Membership(user_id=user.id, scope_type="account", scope_id=t.id,
                          role_name="account_member", status="active"))
        db.commit()

        assert verify_user_tenant_access(user.id, t.id, db) is True
    finally:
        db.close()
        Base.metadata.drop_all(engine)


def test_verify_access_false_for_removed_member():
    engine, SessionLocal = _make_db()
    db = SessionLocal()

    try:
        user = User(cognito_sub="sub-8", email="no@example.com", name="N")
        t = Tenant(name="T")
        db.add_all([user, t])
        db.commit()

        db.add(Membership(user_id=user.id, scope_type="account", scope_id=t.id,
                          role_name="account_member", status="removed"))
        db.commit()

        assert verify_user_tenant_access(user.id, t.id, db) is False
    finally:
        db.close()
        Base.metadata.drop_all(engine)


def test_verify_access_false_for_no_membership():
    engine, SessionLocal = _make_db()
    db = SessionLocal()

    try:
        assert verify_user_tenant_access(uuid4(), uuid4(), db) is False
    finally:
        db.close()
        Base.metadata.drop_all(engine)


# ── list_platform_tenants ────────────────────────────────────────


def test_list_platform_tenants_includes_counts():
    engine, SessionLocal = _make_db()
    db = SessionLocal()

    try:
        t = Tenant(name="Acme", status="active")
        u1 = User(cognito_sub="s1", email="a@x.com", name="A")
        u2 = User(cognito_sub="s2", email="b@x.com", name="B")
        db.add_all([t, u1, u2])
        db.commit()

        db.add_all([
            Membership(user_id=u1.id, scope_type="account", scope_id=t.id,
                       role_name="account_owner", status="active"),
            Membership(user_id=u2.id, scope_type="account", scope_id=t.id,
                       role_name="account_member", status="active"),
        ])
        db.commit()

        tenants = list_platform_tenants(db)
        assert len(tenants) == 1
        assert tenants[0]["name"] == "Acme"
        assert tenants[0]["member_count"] == 2
        assert tenants[0]["owner_count"] == 1
    finally:
        db.close()
        Base.metadata.drop_all(engine)


def test_list_platform_tenants_excludes_removed_from_counts():
    engine, SessionLocal = _make_db()
    db = SessionLocal()

    try:
        t = Tenant(name="T", status="active")
        u = User(cognito_sub="s", email="e@x.com", name="N")
        db.add_all([t, u])
        db.commit()

        db.add(Membership(user_id=u.id, scope_type="account", scope_id=t.id,
                          role_name="account_member", status="removed"))
        db.commit()

        tenants = list_platform_tenants(db)
        assert tenants[0]["member_count"] == 0
    finally:
        db.close()
        Base.metadata.drop_all(engine)


# ── suspend / unsuspend ──────────────────────────────────────────


def test_suspend_nonexistent_tenant_raises():
    engine, SessionLocal = _make_db()
    db = SessionLocal()

    try:
        with pytest.raises(ValueError, match="Tenant not found"):
            suspend_tenant(uuid4(), db)
    finally:
        db.close()
        Base.metadata.drop_all(engine)


def test_unsuspend_nonexistent_tenant_raises():
    engine, SessionLocal = _make_db()
    db = SessionLocal()

    try:
        with pytest.raises(ValueError, match="Tenant not found"):
            unsuspend_tenant(uuid4(), db)
    finally:
        db.close()
        Base.metadata.drop_all(engine)

"""Unit tests for tenant user-management service."""

from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth_usermanagement.models.membership import Membership
from app.auth_usermanagement.models.tenant import Tenant
from app.auth_usermanagement.models.user import User
from app.auth_usermanagement.services.user_management_service import (
    list_tenant_users,
    list_platform_users,
    update_user_role,
    remove_user_from_tenant,
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


def _seed_tenant_with_users(SessionLocal):
    session = SessionLocal()

    tenant = Tenant(name="Acme")
    owner_user = User(cognito_sub="owner-sub", email="owner@example.com", name="Owner")
    admin_user = User(cognito_sub="admin-sub", email="admin@example.com", name="Admin")
    member_user = User(cognito_sub="member-sub", email="member@example.com", name="Member")

    session.add_all([tenant, owner_user, admin_user, member_user])
    session.flush()

    owner_membership = Membership(
        user_id=owner_user.id,
        scope_type="account",
        scope_id=tenant.id,
        role_name="owner",
        status="active",
    )
    admin_membership = Membership(
        user_id=admin_user.id,
        scope_type="account",
        scope_id=tenant.id,
        role_name="admin",
        status="active",
    )
    member_membership = Membership(
        user_id=member_user.id,
        scope_type="account",
        scope_id=tenant.id,
        role_name="member",
        status="active",
    )

    session.add_all([owner_membership, admin_membership, member_membership])
    session.commit()

    ids = {
        "tenant_id": tenant.id,
        "owner_user_id": owner_user.id,
        "admin_user_id": admin_user.id,
        "member_user_id": member_user.id,
    }

    session.close()
    return ids


def test_admin_can_only_assign_member_or_viewer():
    engine, SessionLocal = _make_db()
    ids = _seed_tenant_with_users(SessionLocal)
    db = SessionLocal()

    try:
        with pytest.raises(ValueError, match="Admins can only assign member or viewer roles"):
            update_user_role(
                db,
                ids["tenant_id"],
                ids["member_user_id"],
                "admin",
                actor_role="admin",
                actor_is_platform_admin=False,
            )
    finally:
        db.close()
        Base.metadata.drop_all(engine)


def test_admin_cannot_modify_owner_roles():
    engine, SessionLocal = _make_db()
    ids = _seed_tenant_with_users(SessionLocal)
    db = SessionLocal()

    try:
        with pytest.raises(ValueError, match="Admins cannot modify owner roles"):
            update_user_role(
                db,
                ids["tenant_id"],
                ids["owner_user_id"],
                "member",
                actor_role="admin",
                actor_is_platform_admin=False,
            )
    finally:
        db.close()
        Base.metadata.drop_all(engine)


def test_owner_can_promote_member_to_admin():
    engine, SessionLocal = _make_db()
    ids = _seed_tenant_with_users(SessionLocal)
    db = SessionLocal()

    try:
        membership = update_user_role(
            db,
            ids["tenant_id"],
            ids["member_user_id"],
            "admin",
            actor_role="owner",
            actor_is_platform_admin=False,
        )

        assert membership is not None
        assert membership.role_name == "admin"
    finally:
        db.close()
        Base.metadata.drop_all(engine)


# ── list_tenant_users ───────────────────────────────────────────


def test_list_tenant_users_returns_active_members():
    engine, SessionLocal = _make_db()
    ids = _seed_tenant_with_users(SessionLocal)
    db = SessionLocal()

    try:
        users = list_tenant_users(db, ids["tenant_id"])
        assert len(users) == 3
        emails = {u["email"] for u in users}
        assert "owner@example.com" in emails
        assert "admin@example.com" in emails
        assert "member@example.com" in emails
        assert all(u["status"] == "active" for u in users)
    finally:
        db.close()
        Base.metadata.drop_all(engine)


def test_list_tenant_users_excludes_removed_members():
    engine, SessionLocal = _make_db()
    ids = _seed_tenant_with_users(SessionLocal)
    db = SessionLocal()

    try:
        m = db.query(Membership).filter(
            Membership.user_id == ids["member_user_id"],
            Membership.scope_id == ids["tenant_id"],
        ).first()
        m.status = "removed"
        db.commit()

        users = list_tenant_users(db, ids["tenant_id"])
        assert len(users) == 2
        emails = {u["email"] for u in users}
        assert "member@example.com" not in emails
    finally:
        db.close()
        Base.metadata.drop_all(engine)


def test_list_tenant_users_empty_for_unknown_tenant():
    engine, SessionLocal = _make_db()
    _seed_tenant_with_users(SessionLocal)
    db = SessionLocal()

    try:
        users = list_tenant_users(db, uuid4())
        assert users == []
    finally:
        db.close()
        Base.metadata.drop_all(engine)


# ── list_platform_users ─────────────────────────────────────────


def test_list_platform_users_returns_all_users_sorted():
    engine, SessionLocal = _make_db()
    _seed_tenant_with_users(SessionLocal)
    db = SessionLocal()

    try:
        users = list_platform_users(db)
        assert len(users) == 3
        emails = [u["email"] for u in users]
        assert emails == sorted(emails)
        assert all("memberships" in u for u in users)
    finally:
        db.close()
        Base.metadata.drop_all(engine)


# ── remove_user_from_tenant ─────────────────────────────────────


def test_remove_user_from_tenant_sets_removed_status():
    engine, SessionLocal = _make_db()
    ids = _seed_tenant_with_users(SessionLocal)
    db = SessionLocal()

    try:
        membership = remove_user_from_tenant(db, ids["tenant_id"], ids["member_user_id"])
        assert membership is not None
        assert membership.status == "removed"
    finally:
        db.close()
        Base.metadata.drop_all(engine)


def test_remove_user_returns_none_for_nonexistent():
    engine, SessionLocal = _make_db()
    ids = _seed_tenant_with_users(SessionLocal)
    db = SessionLocal()

    try:
        result = remove_user_from_tenant(db, ids["tenant_id"], uuid4())
        assert result is None
    finally:
        db.close()
        Base.metadata.drop_all(engine)


def test_remove_last_owner_raises():
    engine, SessionLocal = _make_db()
    ids = _seed_tenant_with_users(SessionLocal)
    db = SessionLocal()

    try:
        with pytest.raises(ValueError, match="Cannot remove last owner"):
            remove_user_from_tenant(db, ids["tenant_id"], ids["owner_user_id"])
    finally:
        db.close()
        Base.metadata.drop_all(engine)


# ── update_user_role edge cases ──────────────────────────────────


def test_update_role_returns_none_for_nonexistent_membership():
    engine, SessionLocal = _make_db()
    ids = _seed_tenant_with_users(SessionLocal)
    db = SessionLocal()

    try:
        result = update_user_role(db, ids["tenant_id"], uuid4(), "admin", actor_role="owner")
        assert result is None
    finally:
        db.close()
        Base.metadata.drop_all(engine)


def test_platform_admin_can_modify_owner_role():
    engine, SessionLocal = _make_db()
    ids = _seed_tenant_with_users(SessionLocal)
    db = SessionLocal()

    try:
        second_owner = User(cognito_sub="owner2-sub", email="owner2@example.com", name="Owner 2")
        db.add(second_owner)
        db.flush()
        db.add(Membership(
            user_id=second_owner.id, scope_type="account", scope_id=ids["tenant_id"],
            role_name="account_owner", status="active",
        ))
        db.commit()

        membership = update_user_role(
            db, ids["tenant_id"], ids["owner_user_id"],
            "member", actor_role=None, actor_is_platform_admin=True,
        )
        assert membership.role_name == "member"
    finally:
        db.close()
        Base.metadata.drop_all(engine)


def test_demote_last_owner_raises():
    engine, SessionLocal = _make_db()
    ids = _seed_tenant_with_users(SessionLocal)
    db = SessionLocal()

    try:
        with pytest.raises(ValueError, match="Cannot remove last owner"):
            update_user_role(
                db, ids["tenant_id"], ids["owner_user_id"],
                "member", actor_role="owner", actor_is_platform_admin=True,
            )
    finally:
        db.close()
        Base.metadata.drop_all(engine)

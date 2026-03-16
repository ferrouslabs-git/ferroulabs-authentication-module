"""Unit tests for tenant user-management service role restrictions."""

from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth_usermanagement.models.membership import Membership
from app.auth_usermanagement.models.tenant import Tenant
from app.auth_usermanagement.models.user import User
from app.auth_usermanagement.services.user_management_service import update_user_role
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
        tenant_id=tenant.id,
        role="owner",
        status="active",
    )
    admin_membership = Membership(
        user_id=admin_user.id,
        tenant_id=tenant.id,
        role="admin",
        status="active",
    )
    member_membership = Membership(
        user_id=member_user.id,
        tenant_id=tenant.id,
        role="member",
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
        assert membership.role == "admin"
    finally:
        db.close()
        Base.metadata.drop_all(engine)

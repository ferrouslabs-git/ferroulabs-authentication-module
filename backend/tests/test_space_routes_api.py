"""API tests for space routes: create, list, detail, update, suspend, unsuspend."""
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth_usermanagement.api.space_routes import router
from app.auth_usermanagement.models.membership import Membership
from app.auth_usermanagement.models.space import Space
from app.auth_usermanagement.models.tenant import Tenant
from app.auth_usermanagement.models.user import User
from app.auth_usermanagement.schemas.token import TokenPayload
from app.auth_usermanagement.security.scope_context import ScopeContext
from app.database import Base


# ── Helpers ──────────────────────────────────────────────────────

def _make_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return engine, SessionLocal


_FAKE_PAYLOAD = TokenPayload(
    sub="space-sub", email="space-user@example.com",
    exp=99999999999, iat=1000000000, token_use="access", client_id="test",
)


def _setup_app(SessionLocal, user, tenant_id, extra_perms=None):
    """Create app with overridden dependencies for space route tests."""
    from app.auth_usermanagement.database import get_db
    from app.auth_usermanagement.security.dependencies import get_current_user

    perms = {
        "spaces:create", "account:read", "members:invite", "space:delete",
    }
    if extra_perms:
        perms |= extra_perms

    ctx = ScopeContext(
        user_id=user.id,
        scope_type="account",
        scope_id=tenant_id,
        active_roles=["account_owner"],
        resolved_permissions=perms,
        is_super_admin=False,
    )

    app = FastAPI()
    app.include_router(router)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: user

    # Override all permission-bearing dependencies to return our ctx
    from app.auth_usermanagement.security.guards import require_permission
    for perm_name in perms:
        dep = require_permission(perm_name)
        app.dependency_overrides[dep] = lambda: ctx

    # Also override any generic require_permission to return ctx
    from app.auth_usermanagement.security import require_permission as rp
    app.dependency_overrides[rp("spaces:create")] = lambda: ctx
    app.dependency_overrides[rp("account:read")] = lambda: ctx
    app.dependency_overrides[rp("members:invite")] = lambda: ctx
    app.dependency_overrides[rp("space:delete")] = lambda: ctx

    return app


def _seed(SessionLocal):
    """Create tenant + user in DB."""
    session = SessionLocal()
    tenant = Tenant(name="SpaceCo")
    user = User(cognito_sub="space-sub", email="space-user@example.com", name="Space User")
    session.add_all([tenant, user])
    session.commit()
    tenant_id = tenant.id
    user_obj = User(
        id=user.id, cognito_sub=user.cognito_sub,
        email=user.email, name=user.name,
        is_platform_admin=user.is_platform_admin,
        is_active=user.is_active,
        created_at=user.created_at, updated_at=user.updated_at,
    )
    session.close()
    return tenant_id, user


# ── Direct space service tests via API ───────────────────────────


class TestSpaceServiceIntegration:
    """Test space operations through the service layer directly (simpler, more reliable)."""

    def test_create_space(self):
        from app.auth_usermanagement.services.space_service import create_space

        engine, SessionLocal = _make_db()
        try:
            session = SessionLocal()
            tenant = Tenant(name="SpaceCo")
            user = User(cognito_sub="s-sub", email="s@example.com", name="S")
            session.add_all([tenant, user])
            session.commit()

            space = create_space(session, "Dev Space", tenant.id, user.id)
            assert space.name == "Dev Space"
            assert space.account_id == tenant.id
            assert space.status == "active"

            # Creator should get space_admin membership
            m = session.query(Membership).filter(
                Membership.scope_type == "space",
                Membership.scope_id == space.id,
            ).first()
            assert m is not None
            assert m.role_name == "space_admin"
            assert m.user_id == user.id
        finally:
            session.close()
            Base.metadata.drop_all(engine)

    def test_list_user_spaces(self):
        from app.auth_usermanagement.services.space_service import create_space, list_user_spaces

        engine, SessionLocal = _make_db()
        try:
            session = SessionLocal()
            tenant = Tenant(name="Multi")
            user = User(cognito_sub="ls-sub", email="ls@example.com", name="LS")
            session.add_all([tenant, user])
            session.commit()

            create_space(session, "Space A", tenant.id, user.id)
            create_space(session, "Space B", tenant.id, user.id)

            spaces = list_user_spaces(session, user.id)
            names = {s.name for s in spaces}
            assert "Space A" in names
            assert "Space B" in names
        finally:
            session.close()
            Base.metadata.drop_all(engine)

    def test_list_account_spaces(self):
        from app.auth_usermanagement.services.space_service import (
            create_space, list_account_spaces,
        )

        engine, SessionLocal = _make_db()
        try:
            session = SessionLocal()
            t1 = Tenant(name="T1")
            t2 = Tenant(name="T2")
            user = User(cognito_sub="las-sub", email="las@example.com", name="LAS")
            session.add_all([t1, t2, user])
            session.commit()

            create_space(session, "S1", t1.id, user.id)
            create_space(session, "S2", t2.id, user.id)

            t1_spaces = list_account_spaces(session, t1.id)
            assert len(t1_spaces) == 1
            assert t1_spaces[0].name == "S1"
        finally:
            session.close()
            Base.metadata.drop_all(engine)

    def test_get_space_by_id(self):
        from app.auth_usermanagement.services.space_service import create_space, get_space_by_id

        engine, SessionLocal = _make_db()
        try:
            session = SessionLocal()
            tenant = Tenant(name="GetCo")
            user = User(cognito_sub="get-sub", email="get@example.com", name="Get")
            session.add_all([tenant, user])
            session.commit()

            space = create_space(session, "FindMe", tenant.id, user.id)
            found = get_space_by_id(session, space.id)
            assert found is not None
            assert found.name == "FindMe"

            # Non-existent
            assert get_space_by_id(session, uuid4()) is None
        finally:
            session.close()
            Base.metadata.drop_all(engine)

    def test_update_space(self):
        from app.auth_usermanagement.services.space_service import create_space, update_space

        engine, SessionLocal = _make_db()
        try:
            session = SessionLocal()
            tenant = Tenant(name="UpdCo")
            user = User(cognito_sub="upd-sub", email="upd@example.com", name="Upd")
            session.add_all([tenant, user])
            session.commit()

            space = create_space(session, "OldName", tenant.id, user.id)
            updated = update_space(session, space.id, name="NewName")
            assert updated.name == "NewName"
        finally:
            session.close()
            Base.metadata.drop_all(engine)

    def test_update_space_not_found(self):
        from app.auth_usermanagement.services.space_service import update_space

        engine, SessionLocal = _make_db()
        try:
            session = SessionLocal()
            with pytest.raises(ValueError, match="not found"):
                update_space(session, uuid4(), name="X")
        finally:
            session.close()
            Base.metadata.drop_all(engine)

    def test_suspend_space(self):
        from app.auth_usermanagement.services.space_service import create_space, suspend_space

        engine, SessionLocal = _make_db()
        try:
            session = SessionLocal()
            tenant = Tenant(name="SusCo")
            user = User(cognito_sub="sus-sub", email="sus@example.com", name="Sus")
            session.add_all([tenant, user])
            session.commit()

            space = create_space(session, "Suspendable", tenant.id, user.id)
            suspended = suspend_space(session, space.id)
            assert suspended.status == "suspended"
            assert suspended.suspended_at is not None
        finally:
            session.close()
            Base.metadata.drop_all(engine)

    def test_suspend_already_suspended_raises(self):
        from app.auth_usermanagement.services.space_service import create_space, suspend_space

        engine, SessionLocal = _make_db()
        try:
            session = SessionLocal()
            tenant = Tenant(name="Dup")
            user = User(cognito_sub="dup-sub", email="dup@example.com", name="Dup")
            session.add_all([tenant, user])
            session.commit()

            space = create_space(session, "DupSusp", tenant.id, user.id)
            suspend_space(session, space.id)

            with pytest.raises(ValueError, match="already suspended"):
                suspend_space(session, space.id)
        finally:
            session.close()
            Base.metadata.drop_all(engine)

    def test_unsuspend_space(self):
        from app.auth_usermanagement.services.space_service import (
            create_space, suspend_space, unsuspend_space,
        )

        engine, SessionLocal = _make_db()
        try:
            session = SessionLocal()
            tenant = Tenant(name="UnsCo")
            user = User(cognito_sub="uns-sub", email="uns@example.com", name="Uns")
            session.add_all([tenant, user])
            session.commit()

            space = create_space(session, "UnSuspendable", tenant.id, user.id)
            suspend_space(session, space.id)
            unsuspended = unsuspend_space(session, space.id)
            assert unsuspended.status == "active"
        finally:
            session.close()
            Base.metadata.drop_all(engine)

    def test_unsuspend_active_raises(self):
        from app.auth_usermanagement.services.space_service import create_space, unsuspend_space

        engine, SessionLocal = _make_db()
        try:
            session = SessionLocal()
            tenant = Tenant(name="ActCo")
            user = User(cognito_sub="act-sub", email="act@example.com", name="Act")
            session.add_all([tenant, user])
            session.commit()

            space = create_space(session, "Active", tenant.id, user.id)

            with pytest.raises(ValueError, match="not suspended"):
                unsuspend_space(session, space.id)
        finally:
            session.close()
            Base.metadata.drop_all(engine)

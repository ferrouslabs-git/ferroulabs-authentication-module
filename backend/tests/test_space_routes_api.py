"""API tests for space routes: create, list, detail, update, suspend, unsuspend."""
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth_usermanagement.api.space_routes import router
from app.auth_usermanagement.models.membership import Membership
from app.auth_usermanagement.models.space import Space
from app.auth_usermanagement.models.tenant import Tenant
from app.auth_usermanagement.models.user import User
from app.auth_usermanagement.schemas.token import TokenPayload
from app.auth_usermanagement.security.scope_context import ScopeContext
from app.database import Base
from tests.async_test_utils import make_test_db, make_async_app


# ── Helpers ──────────────────────────────────────────────────────

def _make_db():
    return make_test_db()


_FAKE_PAYLOAD = TokenPayload(
    sub="space-sub", email="space-user@example.com",
    exp=99999999999, iat=1000000000, token_use="access", client_id="test",
)


def _setup_app(AsyncSessionLocal, user, tenant_id, extra_perms=None):
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

    async def override_get_db():
        async with AsyncSessionLocal() as session:
            yield session

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


def _seed(SyncSession):
    """Create tenant + user in DB."""
    session = SyncSession()
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

    @pytest.mark.asyncio
    async def test_create_space(self):
        from app.auth_usermanagement.services.space_service import create_space

        sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
        try:
            session = SyncSession()
            tenant = Tenant(name="SpaceCo")
            user = User(cognito_sub="s-sub", email="s@example.com", name="S")
            session.add_all([tenant, user])
            session.commit()
            tenant_id, user_id = tenant.id, user.id
            session.close()

            async with AsyncSessionLocal() as adb:
                space = await create_space(adb, "Dev Space", tenant_id, user_id)
                assert space.name == "Dev Space"
                assert space.account_id == tenant_id
                assert space.status == "active"

            # Check membership via sync session
            session = SyncSession()
            from sqlalchemy import select as sa_select
            m = session.query(Membership).filter(
                Membership.scope_type == "space",
                Membership.scope_id == space.id,
            ).first()
            assert m is not None
            assert m.role_name == "space_admin"
            assert m.user_id == user_id
            session.close()
        finally:
            Base.metadata.drop_all(sync_engine)

    @pytest.mark.asyncio
    async def test_list_user_spaces(self):
        from app.auth_usermanagement.services.space_service import create_space, list_user_spaces

        sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
        try:
            session = SyncSession()
            tenant = Tenant(name="Multi")
            user = User(cognito_sub="ls-sub", email="ls@example.com", name="LS")
            session.add_all([tenant, user])
            session.commit()
            tenant_id, user_id = tenant.id, user.id
            session.close()

            async with AsyncSessionLocal() as adb:
                await create_space(adb, "Space A", tenant_id, user_id)
                await create_space(adb, "Space B", tenant_id, user_id)
                spaces = await list_user_spaces(adb, user_id)
                names = {s.name for s in spaces}
                assert "Space A" in names
                assert "Space B" in names
        finally:
            Base.metadata.drop_all(sync_engine)

    @pytest.mark.asyncio
    async def test_list_account_spaces(self):
        from app.auth_usermanagement.services.space_service import (
            create_space, list_account_spaces,
        )

        sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
        try:
            session = SyncSession()
            t1 = Tenant(name="T1")
            t2 = Tenant(name="T2")
            user = User(cognito_sub="las-sub", email="las@example.com", name="LAS")
            session.add_all([t1, t2, user])
            session.commit()
            t1_id, t2_id, user_id = t1.id, t2.id, user.id
            session.close()

            async with AsyncSessionLocal() as adb:
                await create_space(adb, "S1", t1_id, user_id)
                await create_space(adb, "S2", t2_id, user_id)
                t1_spaces = await list_account_spaces(adb, t1_id)
                assert len(t1_spaces) == 1
                assert t1_spaces[0].name == "S1"
        finally:
            Base.metadata.drop_all(sync_engine)

    @pytest.mark.asyncio
    async def test_get_space_by_id(self):
        from app.auth_usermanagement.services.space_service import create_space, get_space_by_id

        sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
        try:
            session = SyncSession()
            tenant = Tenant(name="GetCo")
            user = User(cognito_sub="get-sub", email="get@example.com", name="Get")
            session.add_all([tenant, user])
            session.commit()
            tenant_id, user_id = tenant.id, user.id
            session.close()

            async with AsyncSessionLocal() as adb:
                space = await create_space(adb, "FindMe", tenant_id, user_id)
                found = await get_space_by_id(adb, space.id)
                assert found is not None
                assert found.name == "FindMe"
                assert await get_space_by_id(adb, uuid4()) is None
        finally:
            Base.metadata.drop_all(sync_engine)

    @pytest.mark.asyncio
    async def test_update_space(self):
        from app.auth_usermanagement.services.space_service import create_space, update_space

        sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
        try:
            session = SyncSession()
            tenant = Tenant(name="UpdCo")
            user = User(cognito_sub="upd-sub", email="upd@example.com", name="Upd")
            session.add_all([tenant, user])
            session.commit()
            tenant_id, user_id = tenant.id, user.id
            session.close()

            async with AsyncSessionLocal() as adb:
                space = await create_space(adb, "OldName", tenant_id, user_id)
                updated = await update_space(adb, space.id, name="NewName")
                assert updated.name == "NewName"
        finally:
            Base.metadata.drop_all(sync_engine)

    @pytest.mark.asyncio
    async def test_update_space_not_found(self):
        from app.auth_usermanagement.services.space_service import update_space

        sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
        try:
            async with AsyncSessionLocal() as adb:
                with pytest.raises(ValueError, match="not found"):
                    await update_space(adb, uuid4(), name="X")
        finally:
            Base.metadata.drop_all(sync_engine)

    @pytest.mark.asyncio
    async def test_suspend_space(self):
        from app.auth_usermanagement.services.space_service import create_space, suspend_space

        sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
        try:
            session = SyncSession()
            tenant = Tenant(name="SusCo")
            user = User(cognito_sub="sus-sub", email="sus@example.com", name="Sus")
            session.add_all([tenant, user])
            session.commit()
            tenant_id, user_id = tenant.id, user.id
            session.close()

            async with AsyncSessionLocal() as adb:
                space = await create_space(adb, "Suspendable", tenant_id, user_id)
                suspended = await suspend_space(adb, space.id)
                assert suspended.status == "suspended"
                assert suspended.suspended_at is not None
        finally:
            Base.metadata.drop_all(sync_engine)

    @pytest.mark.asyncio
    async def test_suspend_already_suspended_raises(self):
        from app.auth_usermanagement.services.space_service import create_space, suspend_space

        sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
        try:
            session = SyncSession()
            tenant = Tenant(name="Dup")
            user = User(cognito_sub="dup-sub", email="dup@example.com", name="Dup")
            session.add_all([tenant, user])
            session.commit()
            tenant_id, user_id = tenant.id, user.id
            session.close()

            async with AsyncSessionLocal() as adb:
                space = await create_space(adb, "DupSusp", tenant_id, user_id)
                await suspend_space(adb, space.id)
                with pytest.raises(ValueError, match="already suspended"):
                    await suspend_space(adb, space.id)
        finally:
            Base.metadata.drop_all(sync_engine)

    @pytest.mark.asyncio
    async def test_unsuspend_space(self):
        from app.auth_usermanagement.services.space_service import (
            create_space, suspend_space, unsuspend_space,
        )

        sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
        try:
            session = SyncSession()
            tenant = Tenant(name="UnsCo")
            user = User(cognito_sub="uns-sub", email="uns@example.com", name="Uns")
            session.add_all([tenant, user])
            session.commit()
            tenant_id, user_id = tenant.id, user.id
            session.close()

            async with AsyncSessionLocal() as adb:
                space = await create_space(adb, "UnSuspendable", tenant_id, user_id)
                await suspend_space(adb, space.id)
                unsuspended = await unsuspend_space(adb, space.id)
                assert unsuspended.status == "active"
        finally:
            Base.metadata.drop_all(sync_engine)

    @pytest.mark.asyncio
    async def test_unsuspend_active_raises(self):
        from app.auth_usermanagement.services.space_service import create_space, unsuspend_space

        sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
        try:
            session = SyncSession()
            tenant = Tenant(name="ActCo")
            user = User(cognito_sub="act-sub", email="act@example.com", name="Act")
            session.add_all([tenant, user])
            session.commit()
            tenant_id, user_id = tenant.id, user.id
            session.close()

            async with AsyncSessionLocal() as adb:
                space = await create_space(adb, "Active", tenant_id, user_id)
                with pytest.raises(ValueError, match="not suspended"):
                    await unsuspend_space(adb, space.id)
        finally:
            Base.metadata.drop_all(sync_engine)

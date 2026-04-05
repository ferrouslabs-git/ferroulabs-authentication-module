"""Tests for the 6 TrustOS integration gap features.

1. Reactivate membership (service + route)
2. Resend invite by invitation ID (service + route)
3. Role filter on platform user list (service + route)
4. Role filter on tenant user list (service + route)
5. Deactivate membership PATCH alias (route)
6. Status filter on tenant user list (service + route)
"""
from datetime import datetime, timedelta, timezone


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)
from unittest.mock import AsyncMock
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.auth_usermanagement.models.invitation import Invitation
from app.auth_usermanagement.models.membership import Membership
from app.auth_usermanagement.models.tenant import Tenant
from app.auth_usermanagement.models.user import User
from app.auth_usermanagement.services.invitation_service import get_invitation_by_id
from app.auth_usermanagement.services.user_management_service import (
    list_platform_users,
    list_tenant_users,
    reactivate_user_in_tenant,
    remove_user_from_tenant,
)
from app.database import Base
from tests.async_test_utils import make_test_db


# ── DB helpers ───────────────────────────────────────────────────


def _seed(db):
    """Create a tenant with owner, admin, and member users using a sync session."""
    tenant = Tenant(name="GapTest")
    owner = User(cognito_sub="gap-owner", email="owner@gap.io", name="Owner")
    admin = User(cognito_sub="gap-admin", email="admin@gap.io", name="Admin")
    member = User(cognito_sub="gap-member", email="member@gap.io", name="Member")
    db.add_all([tenant, owner, admin, member])
    db.flush()

    for user, role in [(owner, "account_owner"), (admin, "account_admin"), (member, "account_member")]:
        db.add(Membership(
            user_id=user.id,
            scope_type="account",
            scope_id=tenant.id,
            role_name=role,
            status="active",
        ))
    db.commit()

    return dict(
        tenant_id=tenant.id,
        owner_id=owner.id,
        admin_id=admin.id,
        member_id=member.id,
    )


# ═══════════════════════════════════════════════════════════════
# 1. Reactivate membership
# ═══════════════════════════════════════════════════════════════


class TestReactivateMembership:
    @pytest.mark.asyncio
    async def test_reactivate_removed_membership(self, dual_session):
        sync_db, async_db = dual_session
        ids = _seed(sync_db)
        await remove_user_from_tenant(async_db, ids["tenant_id"], ids["member_id"])
        m = await reactivate_user_in_tenant(async_db, ids["tenant_id"], ids["member_id"])
        assert m is not None
        assert m.status == "active"

    @pytest.mark.asyncio
    async def test_reactivate_returns_none_when_already_active(self, dual_session):
        sync_db, async_db = dual_session
        ids = _seed(sync_db)
        result = await reactivate_user_in_tenant(async_db, ids["tenant_id"], ids["member_id"])
        assert result is None

    @pytest.mark.asyncio
    async def test_reactivate_returns_none_for_unknown_user(self, dual_session):
        sync_db, async_db = dual_session
        ids = _seed(sync_db)
        result = await reactivate_user_in_tenant(async_db, ids["tenant_id"], uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_reactivate_returns_none_for_unknown_tenant(self, dual_session):
        sync_db, async_db = dual_session
        ids = _seed(sync_db)
        await remove_user_from_tenant(async_db, ids["tenant_id"], ids["member_id"])
        result = await reactivate_user_in_tenant(async_db, uuid4(), ids["member_id"])
        assert result is None


# ═══════════════════════════════════════════════════════════════
# 2. Get invitation by ID
# ═══════════════════════════════════════════════════════════════


class TestGetInvitationById:
    @pytest.mark.asyncio
    async def test_returns_invitation_matching_id_and_tenant(self, dual_session):
        sync_db, async_db = dual_session
        ids = _seed(sync_db)
        inv = Invitation(
            tenant_id=ids["tenant_id"],
            email="invite@gap.io",
            token="raw-test-token-1",
            token_hash="hash123",
            target_scope_type="account",
            target_scope_id=ids["tenant_id"],
            target_role_name="account_member",
            created_by=ids["owner_id"],
            expires_at=_utcnow() + timedelta(days=7),
        )
        sync_db.add(inv)
        sync_db.commit()
        sync_db.refresh(inv)

        result = await get_invitation_by_id(async_db, ids["tenant_id"], inv.id)
        assert result is not None
        assert result.id == inv.id
        assert result.email == "invite@gap.io"

    @pytest.mark.asyncio
    async def test_returns_none_for_wrong_tenant(self, dual_session):
        sync_db, async_db = dual_session
        ids = _seed(sync_db)
        inv = Invitation(
            tenant_id=ids["tenant_id"],
            email="invite@gap.io",
            token="raw-test-token-2",
            token_hash="hash456",
            target_scope_type="account",
            target_scope_id=ids["tenant_id"],
            target_role_name="account_member",
            created_by=ids["owner_id"],
            expires_at=_utcnow() + timedelta(days=7),
        )
        sync_db.add(inv)
        sync_db.commit()
        sync_db.refresh(inv)

        result = await get_invitation_by_id(async_db, uuid4(), inv.id)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_nonexistent_id(self, dual_session):
        sync_db, async_db = dual_session
        ids = _seed(sync_db)
        result = await get_invitation_by_id(async_db, ids["tenant_id"], uuid4())
        assert result is None


# ═══════════════════════════════════════════════════════════════
# 3. Role filter on platform user list
# ═══════════════════════════════════════════════════════════════


class TestPlatformUsersRoleFilter:
    @pytest.mark.asyncio
    async def test_filter_by_account_owner_returns_only_owners(self, dual_session):
        sync_db, async_db = dual_session
        ids = _seed(sync_db)
        users = await list_platform_users(async_db, role="account_owner")
        assert len(users) == 1
        assert users[0]["email"] == "owner@gap.io"

    @pytest.mark.asyncio
    async def test_filter_by_nonexistent_role_returns_empty(self, dual_session):
        sync_db, async_db = dual_session
        _seed(sync_db)
        users = await list_platform_users(async_db, role="super_god")
        assert users == []

    @pytest.mark.asyncio
    async def test_no_filter_returns_all(self, dual_session):
        sync_db, async_db = dual_session
        _seed(sync_db)
        users = await list_platform_users(async_db)
        assert len(users) == 3


# ═══════════════════════════════════════════════════════════════
# 4. Role filter on tenant user list
# ═══════════════════════════════════════════════════════════════


class TestTenantUsersRoleFilter:
    @pytest.mark.asyncio
    async def test_filter_by_account_admin(self, dual_session):
        sync_db, async_db = dual_session
        ids = _seed(sync_db)
        users = await list_tenant_users(async_db, ids["tenant_id"], role="account_admin")
        assert len(users) == 1
        assert users[0]["email"] == "admin@gap.io"

    @pytest.mark.asyncio
    async def test_filter_by_nonexistent_role_returns_empty(self, dual_session):
        sync_db, async_db = dual_session
        ids = _seed(sync_db)
        users = await list_tenant_users(async_db, ids["tenant_id"], role="viewer")
        assert users == []

    @pytest.mark.asyncio
    async def test_role_filter_combined_with_default_status(self, dual_session):
        """Role filter should still respect default status=active."""
        sync_db, async_db = dual_session
        ids = _seed(sync_db)
        await remove_user_from_tenant(async_db, ids["tenant_id"], ids["member_id"])
        users = await list_tenant_users(async_db, ids["tenant_id"], role="account_member")
        assert users == []  # removed member excluded by default


# ═══════════════════════════════════════════════════════════════
# 5. Deactivate membership (alias for remove)
# ═══════════════════════════════════════════════════════════════
# The deactivate endpoint calls remove_user_from_tenant under the hood.
# Service behaviour already tested; route test below uses TestClient.


# ═══════════════════════════════════════════════════════════════
# 6. Status filter on tenant user list
# ═══════════════════════════════════════════════════════════════


class TestTenantUsersStatusFilter:
    @pytest.mark.asyncio
    async def test_status_removed_shows_removed_members(self, dual_session):
        sync_db, async_db = dual_session
        ids = _seed(sync_db)
        await remove_user_from_tenant(async_db, ids["tenant_id"], ids["member_id"])
        users = await list_tenant_users(async_db, ids["tenant_id"], status_filter="removed")
        assert len(users) == 1
        assert users[0]["email"] == "member@gap.io"
        assert users[0]["status"] == "removed"

    @pytest.mark.asyncio
    async def test_status_active_is_default(self, dual_session):
        sync_db, async_db = dual_session
        ids = _seed(sync_db)
        await remove_user_from_tenant(async_db, ids["tenant_id"], ids["member_id"])
        active = await list_tenant_users(async_db, ids["tenant_id"])
        assert len(active) == 2

        explicit_active = await list_tenant_users(async_db, ids["tenant_id"], status_filter="active")
        assert len(explicit_active) == 2

        assert {u["email"] for u in active} == {u["email"] for u in explicit_active}

    @pytest.mark.asyncio
    async def test_combined_role_and_status_filter(self, dual_session):
        sync_db, async_db = dual_session
        ids = _seed(sync_db)
        await remove_user_from_tenant(async_db, ids["tenant_id"], ids["member_id"])
        # All removed + role=account_member
        users = await list_tenant_users(
            async_db, ids["tenant_id"],
            role="account_member",
            status_filter="removed",
        )
        assert len(users) == 1
        assert users[0]["email"] == "member@gap.io"

        # All removed + role=account_owner → empty
        users2 = await list_tenant_users(
            async_db, ids["tenant_id"],
            role="account_owner",
            status_filter="removed",
        )
        assert users2 == []


# ═══════════════════════════════════════════════════════════════
# Route-level tests (FastAPI TestClient via real app)
# ═══════════════════════════════════════════════════════════════

from fastapi.testclient import TestClient

from app.auth_usermanagement.security import dependencies as security_dependencies
from app.database import Base as _Base, get_db
from app.main import app


def _api_seed(SyncSession):
    """Seed a tenant + owner for route-level tests.  Returns ids dict."""
    db = SyncSession()
    tenant = Tenant(name="RouteTest", plan="free", status="active")
    owner = User(cognito_sub="rt-owner", email="owner@rt.io", name="Owner", is_platform_admin=True)
    member = User(cognito_sub="rt-member", email="member@rt.io", name="Member")
    admin_user = User(cognito_sub="rt-admin", email="admin@rt.io", name="Admin")
    db.add_all([tenant, owner, member, admin_user])
    db.flush()
    db.add_all([
        Membership(user_id=owner.id, scope_type="account", scope_id=tenant.id,
                   role_name="account_owner", status="active"),
        Membership(user_id=member.id, scope_type="account", scope_id=tenant.id,
                   role_name="account_member", status="active"),
        Membership(user_id=admin_user.id, scope_type="account", scope_id=tenant.id,
                   role_name="account_admin", status="active"),
    ])
    db.commit()
    ids = {
        "tenant_id": str(tenant.id),
        "owner_sub": owner.cognito_sub,
        "owner_id": str(owner.id),
        "member_id": str(member.id),
        "admin_id": str(admin_user.id),
    }
    db.close()
    return ids


def _api_client(monkeypatch, AsyncSessionLocal, user_sub):
    async def _override_get_db():
        async with AsyncSessionLocal() as session:
            yield session

    monkeypatch.setattr(
        security_dependencies,
        "verify_token_async",
        AsyncMock(return_value=SimpleNamespace(sub=user_sub)),
    )
    app.dependency_overrides[get_db] = _override_get_db
    return TestClient(app, raise_server_exceptions=True)


def _scoped_headers(tenant_id: str):
    return {"Authorization": "Bearer fake-token", "X-Tenant-ID": tenant_id}


def _auth_headers():
    return {"Authorization": "Bearer fake-token"}


class TestRouteDeactivate:
    def test_deactivate_endpoint_sets_removed(self, monkeypatch):
        sync_engine, SyncSession, async_engine, AsyncSessionLocal = make_test_db()
        ids = _api_seed(SyncSession)
        try:
            with _api_client(monkeypatch, AsyncSessionLocal, ids["owner_sub"]) as c:
                r = c.patch(
                    f"/auth/tenants/{ids['tenant_id']}/users/{ids['member_id']}/deactivate",
                    headers=_scoped_headers(ids["tenant_id"]),
                )
                assert r.status_code == 200
                body = r.json()
                assert body["status"] == "removed"
                assert body["message"] == "User deactivated in tenant"
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_deactivate_nonexistent_user_returns_404(self, monkeypatch):
        sync_engine, SyncSession, async_engine, AsyncSessionLocal = make_test_db()
        ids = _api_seed(SyncSession)
        try:
            with _api_client(monkeypatch, AsyncSessionLocal, ids["owner_sub"]) as c:
                r = c.patch(
                    f"/auth/tenants/{ids['tenant_id']}/users/{uuid4()}/deactivate",
                    headers=_scoped_headers(ids["tenant_id"]),
                )
                assert r.status_code == 404
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)


class TestRouteReactivate:
    def test_reactivate_endpoint_sets_active(self, monkeypatch):
        sync_engine, SyncSession, async_engine, AsyncSessionLocal = make_test_db()
        ids = _api_seed(SyncSession)
        try:
            with _api_client(monkeypatch, AsyncSessionLocal, ids["owner_sub"]) as c:
                hdrs = _scoped_headers(ids["tenant_id"])
                # Deactivate first
                c.patch(
                    f"/auth/tenants/{ids['tenant_id']}/users/{ids['member_id']}/deactivate",
                    headers=hdrs,
                )
                # Now reactivate
                r = c.patch(
                    f"/auth/tenants/{ids['tenant_id']}/users/{ids['member_id']}/reactivate",
                    headers=hdrs,
                )
                assert r.status_code == 200
                body = r.json()
                assert body["status"] == "active"
                assert body["message"] == "User reactivated in tenant"
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_reactivate_already_active_returns_404(self, monkeypatch):
        sync_engine, SyncSession, async_engine, AsyncSessionLocal = make_test_db()
        ids = _api_seed(SyncSession)
        try:
            with _api_client(monkeypatch, AsyncSessionLocal, ids["owner_sub"]) as c:
                r = c.patch(
                    f"/auth/tenants/{ids['tenant_id']}/users/{ids['member_id']}/reactivate",
                    headers=_scoped_headers(ids["tenant_id"]),
                )
                assert r.status_code == 404
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)


class TestRouteRoleFilter:
    def test_tenant_users_with_role_query_param(self, monkeypatch):
        sync_engine, SyncSession, async_engine, AsyncSessionLocal = make_test_db()
        ids = _api_seed(SyncSession)
        try:
            with _api_client(monkeypatch, AsyncSessionLocal, ids["owner_sub"]) as c:
                r = c.get(
                    f"/auth/tenants/{ids['tenant_id']}/users?role=account_owner",
                    headers=_scoped_headers(ids["tenant_id"]),
                )
                assert r.status_code == 200
                users = r.json()
                assert len(users) == 1
                assert users[0]["role"] == "account_owner"
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_tenant_users_with_status_query_param(self, monkeypatch):
        sync_engine, SyncSession, async_engine, AsyncSessionLocal = make_test_db()
        ids = _api_seed(SyncSession)
        try:
            with _api_client(monkeypatch, AsyncSessionLocal, ids["owner_sub"]) as c:
                hdrs = _scoped_headers(ids["tenant_id"])
                # Deactivate
                c.patch(
                    f"/auth/tenants/{ids['tenant_id']}/users/{ids['member_id']}/deactivate",
                    headers=hdrs,
                )
                r = c.get(
                    f"/auth/tenants/{ids['tenant_id']}/users?status=removed",
                    headers=hdrs,
                )
                assert r.status_code == 200
                users = r.json()
                assert len(users) == 1
                assert users[0]["status"] == "removed"
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_platform_users_with_role_query_param(self, monkeypatch):
        sync_engine, SyncSession, async_engine, AsyncSessionLocal = make_test_db()
        ids = _api_seed(SyncSession)
        try:
            with _api_client(monkeypatch, AsyncSessionLocal, ids["owner_sub"]) as c:
                r = c.get(
                    "/auth/platform/users?role=account_admin",
                    headers=_auth_headers(),
                )
                assert r.status_code == 200
                users = r.json()
                assert len(users) == 1
                assert users[0]["email"] == "admin@rt.io"
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)


class TestRouteResendByInvitationId:
    def test_resend_by_id_returns_200(self, monkeypatch):
        sync_engine, SyncSession, async_engine, AsyncSessionLocal = make_test_db()
        ids = _api_seed(SyncSession)
        try:
            # Seed an invitation directly
            from uuid import UUID as _UUID
            db = SyncSession()
            inv = Invitation(
                tenant_id=_UUID(ids["tenant_id"]),
                email="invite@rt.io",
                token="raw-tok-123",
                token_hash="hash789",
                target_scope_type="account",
                target_scope_id=_UUID(ids["tenant_id"]),
                target_role_name="account_member",
                created_by=_UUID(ids["owner_id"]),
                expires_at=_utcnow() + timedelta(days=7),
            )
            db.add(inv)
            db.commit()
            db.refresh(inv)
            inv_id = str(inv.id)
            db.close()

            with _api_client(monkeypatch, AsyncSessionLocal, ids["owner_sub"]) as c:
                r = c.post(
                    f"/auth/tenants/{ids['tenant_id']}/invitations/{inv_id}/resend",
                    headers=_scoped_headers(ids["tenant_id"]),
                )
                assert r.status_code == 200
                body = r.json()
                assert body["email"] == "invite@rt.io"
                assert "token" in body
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_resend_by_id_nonexistent_returns_404(self, monkeypatch):
        sync_engine, SyncSession, async_engine, AsyncSessionLocal = make_test_db()
        ids = _api_seed(SyncSession)
        try:
            with _api_client(monkeypatch, AsyncSessionLocal, ids["owner_sub"]) as c:
                r = c.post(
                    f"/auth/tenants/{ids['tenant_id']}/invitations/{uuid4()}/resend",
                    headers=_scoped_headers(ids["tenant_id"]),
                )
                assert r.status_code == 404
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

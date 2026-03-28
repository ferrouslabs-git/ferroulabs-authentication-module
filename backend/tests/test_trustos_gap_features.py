"""Tests for the 6 TrustOS integration gap features.

1. Reactivate membership (service + route)
2. Resend invite by invitation ID (service + route)
3. Role filter on platform user list (service + route)
4. Role filter on tenant user list (service + route)
5. Deactivate membership PATCH alias (route)
6. Status filter on tenant user list (service + route)
"""
from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

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


# ── DB helpers ───────────────────────────────────────────────────


def _make_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return engine, Session


def _seed(Session):
    """Create a tenant with owner, admin, and member users."""
    db = Session()
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

    ids = dict(
        tenant_id=tenant.id,
        owner_id=owner.id,
        admin_id=admin.id,
        member_id=member.id,
    )
    db.close()
    return ids


# ═══════════════════════════════════════════════════════════════
# 1. Reactivate membership
# ═══════════════════════════════════════════════════════════════


class TestReactivateMembership:
    def test_reactivate_removed_membership(self):
        engine, Session = _make_db()
        ids = _seed(Session)
        db = Session()
        try:
            remove_user_from_tenant(db, ids["tenant_id"], ids["member_id"])
            m = reactivate_user_in_tenant(db, ids["tenant_id"], ids["member_id"])
            assert m is not None
            assert m.status == "active"
        finally:
            db.close()
            Base.metadata.drop_all(engine)

    def test_reactivate_returns_none_when_already_active(self):
        engine, Session = _make_db()
        ids = _seed(Session)
        db = Session()
        try:
            result = reactivate_user_in_tenant(db, ids["tenant_id"], ids["member_id"])
            assert result is None
        finally:
            db.close()
            Base.metadata.drop_all(engine)

    def test_reactivate_returns_none_for_unknown_user(self):
        engine, Session = _make_db()
        ids = _seed(Session)
        db = Session()
        try:
            result = reactivate_user_in_tenant(db, ids["tenant_id"], uuid4())
            assert result is None
        finally:
            db.close()
            Base.metadata.drop_all(engine)

    def test_reactivate_returns_none_for_unknown_tenant(self):
        engine, Session = _make_db()
        ids = _seed(Session)
        db = Session()
        try:
            remove_user_from_tenant(db, ids["tenant_id"], ids["member_id"])
            result = reactivate_user_in_tenant(db, uuid4(), ids["member_id"])
            assert result is None
        finally:
            db.close()
            Base.metadata.drop_all(engine)


# ═══════════════════════════════════════════════════════════════
# 2. Get invitation by ID
# ═══════════════════════════════════════════════════════════════


class TestGetInvitationById:
    def test_returns_invitation_matching_id_and_tenant(self):
        engine, Session = _make_db()
        ids = _seed(Session)
        db = Session()
        try:
            inv = Invitation(
                tenant_id=ids["tenant_id"],
                email="invite@gap.io",
                token="raw-test-token-1",
                token_hash="hash123",
                target_scope_type="account",
                target_scope_id=ids["tenant_id"],
                target_role_name="account_member",
                created_by=ids["owner_id"],
                expires_at=datetime.utcnow() + timedelta(days=7),
            )
            db.add(inv)
            db.commit()
            db.refresh(inv)

            result = get_invitation_by_id(db, ids["tenant_id"], inv.id)
            assert result is not None
            assert result.id == inv.id
            assert result.email == "invite@gap.io"
        finally:
            db.close()
            Base.metadata.drop_all(engine)

    def test_returns_none_for_wrong_tenant(self):
        engine, Session = _make_db()
        ids = _seed(Session)
        db = Session()
        try:
            inv = Invitation(
                tenant_id=ids["tenant_id"],
                email="invite@gap.io",
                token="raw-test-token-2",
                token_hash="hash456",
                target_scope_type="account",
                target_scope_id=ids["tenant_id"],
                target_role_name="account_member",
                created_by=ids["owner_id"],
                expires_at=datetime.utcnow() + timedelta(days=7),
            )
            db.add(inv)
            db.commit()
            db.refresh(inv)

            result = get_invitation_by_id(db, uuid4(), inv.id)
            assert result is None
        finally:
            db.close()
            Base.metadata.drop_all(engine)

    def test_returns_none_for_nonexistent_id(self):
        engine, Session = _make_db()
        ids = _seed(Session)
        db = Session()
        try:
            result = get_invitation_by_id(db, ids["tenant_id"], uuid4())
            assert result is None
        finally:
            db.close()
            Base.metadata.drop_all(engine)


# ═══════════════════════════════════════════════════════════════
# 3. Role filter on platform user list
# ═══════════════════════════════════════════════════════════════


class TestPlatformUsersRoleFilter:
    def test_filter_by_account_owner_returns_only_owners(self):
        engine, Session = _make_db()
        ids = _seed(Session)
        db = Session()
        try:
            users = list_platform_users(db, role="account_owner")
            assert len(users) == 1
            assert users[0]["email"] == "owner@gap.io"
        finally:
            db.close()
            Base.metadata.drop_all(engine)

    def test_filter_by_nonexistent_role_returns_empty(self):
        engine, Session = _make_db()
        _seed(Session)
        db = Session()
        try:
            users = list_platform_users(db, role="super_god")
            assert users == []
        finally:
            db.close()
            Base.metadata.drop_all(engine)

    def test_no_filter_returns_all(self):
        engine, Session = _make_db()
        _seed(Session)
        db = Session()
        try:
            users = list_platform_users(db)
            assert len(users) == 3
        finally:
            db.close()
            Base.metadata.drop_all(engine)


# ═══════════════════════════════════════════════════════════════
# 4. Role filter on tenant user list
# ═══════════════════════════════════════════════════════════════


class TestTenantUsersRoleFilter:
    def test_filter_by_account_admin(self):
        engine, Session = _make_db()
        ids = _seed(Session)
        db = Session()
        try:
            users = list_tenant_users(db, ids["tenant_id"], role="account_admin")
            assert len(users) == 1
            assert users[0]["email"] == "admin@gap.io"
        finally:
            db.close()
            Base.metadata.drop_all(engine)

    def test_filter_by_nonexistent_role_returns_empty(self):
        engine, Session = _make_db()
        ids = _seed(Session)
        db = Session()
        try:
            users = list_tenant_users(db, ids["tenant_id"], role="viewer")
            assert users == []
        finally:
            db.close()
            Base.metadata.drop_all(engine)

    def test_role_filter_combined_with_default_status(self):
        """Role filter should still respect default status=active."""
        engine, Session = _make_db()
        ids = _seed(Session)
        db = Session()
        try:
            remove_user_from_tenant(db, ids["member_id"], ids["member_id"])
            users = list_tenant_users(db, ids["tenant_id"], role="account_member")
            # The member is still active (wrong tenant_id above), so double-check:
            # Actually remove correctly:
            db.rollback()
        finally:
            db.close()
            Base.metadata.drop_all(engine)

        # Fresh test with correct removal
        engine, Session = _make_db()
        ids = _seed(Session)
        db = Session()
        try:
            remove_user_from_tenant(db, ids["tenant_id"], ids["member_id"])
            users = list_tenant_users(db, ids["tenant_id"], role="account_member")
            assert users == []  # removed member excluded by default
        finally:
            db.close()
            Base.metadata.drop_all(engine)


# ═══════════════════════════════════════════════════════════════
# 5. Deactivate membership (alias for remove)
# ═══════════════════════════════════════════════════════════════
# The deactivate endpoint calls remove_user_from_tenant under the hood.
# Service behaviour already tested; route test below uses TestClient.


# ═══════════════════════════════════════════════════════════════
# 6. Status filter on tenant user list
# ═══════════════════════════════════════════════════════════════


class TestTenantUsersStatusFilter:
    def test_status_removed_shows_removed_members(self):
        engine, Session = _make_db()
        ids = _seed(Session)
        db = Session()
        try:
            remove_user_from_tenant(db, ids["tenant_id"], ids["member_id"])
            users = list_tenant_users(db, ids["tenant_id"], status_filter="removed")
            assert len(users) == 1
            assert users[0]["email"] == "member@gap.io"
            assert users[0]["status"] == "removed"
        finally:
            db.close()
            Base.metadata.drop_all(engine)

    def test_status_active_is_default(self):
        engine, Session = _make_db()
        ids = _seed(Session)
        db = Session()
        try:
            remove_user_from_tenant(db, ids["tenant_id"], ids["member_id"])
            active = list_tenant_users(db, ids["tenant_id"])
            assert len(active) == 2

            explicit_active = list_tenant_users(db, ids["tenant_id"], status_filter="active")
            assert len(explicit_active) == 2

            assert {u["email"] for u in active} == {u["email"] for u in explicit_active}
        finally:
            db.close()
            Base.metadata.drop_all(engine)

    def test_combined_role_and_status_filter(self):
        engine, Session = _make_db()
        ids = _seed(Session)
        db = Session()
        try:
            remove_user_from_tenant(db, ids["tenant_id"], ids["member_id"])
            # All removed + role=account_member
            users = list_tenant_users(
                db, ids["tenant_id"],
                role="account_member",
                status_filter="removed",
            )
            assert len(users) == 1
            assert users[0]["email"] == "member@gap.io"

            # All removed + role=account_owner → empty
            users2 = list_tenant_users(
                db, ids["tenant_id"],
                role="account_owner",
                status_filter="removed",
            )
            assert users2 == []
        finally:
            db.close()
            Base.metadata.drop_all(engine)


# ═══════════════════════════════════════════════════════════════
# Route-level tests (FastAPI TestClient via real app)
# ═══════════════════════════════════════════════════════════════

from fastapi.testclient import TestClient

from app.auth_usermanagement.security import dependencies as security_dependencies
from app.database import Base as _Base, get_db
from app.main import app


def _api_seed(SessionLocal):
    """Seed a tenant + owner for route-level tests.  Returns ids dict."""
    db = SessionLocal()
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


def _api_client(monkeypatch, SessionLocal, user_sub):
    def _override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr(
        security_dependencies,
        "verify_token",
        lambda _token: SimpleNamespace(sub=user_sub),
    )
    app.dependency_overrides[get_db] = _override_get_db
    return TestClient(app, raise_server_exceptions=True)


def _scoped_headers(tenant_id: str):
    return {"Authorization": "Bearer fake-token", "X-Tenant-ID": tenant_id}


def _auth_headers():
    return {"Authorization": "Bearer fake-token"}


class TestRouteDeactivate:
    def test_deactivate_endpoint_sets_removed(self, monkeypatch):
        engine, SL = _make_db()
        ids = _api_seed(SL)
        try:
            with _api_client(monkeypatch, SL, ids["owner_sub"]) as c:
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
            Base.metadata.drop_all(engine)

    def test_deactivate_nonexistent_user_returns_404(self, monkeypatch):
        engine, SL = _make_db()
        ids = _api_seed(SL)
        try:
            with _api_client(monkeypatch, SL, ids["owner_sub"]) as c:
                r = c.patch(
                    f"/auth/tenants/{ids['tenant_id']}/users/{uuid4()}/deactivate",
                    headers=_scoped_headers(ids["tenant_id"]),
                )
                assert r.status_code == 404
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(engine)


class TestRouteReactivate:
    def test_reactivate_endpoint_sets_active(self, monkeypatch):
        engine, SL = _make_db()
        ids = _api_seed(SL)
        try:
            with _api_client(monkeypatch, SL, ids["owner_sub"]) as c:
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
            Base.metadata.drop_all(engine)

    def test_reactivate_already_active_returns_404(self, monkeypatch):
        engine, SL = _make_db()
        ids = _api_seed(SL)
        try:
            with _api_client(monkeypatch, SL, ids["owner_sub"]) as c:
                r = c.patch(
                    f"/auth/tenants/{ids['tenant_id']}/users/{ids['member_id']}/reactivate",
                    headers=_scoped_headers(ids["tenant_id"]),
                )
                assert r.status_code == 404
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(engine)


class TestRouteRoleFilter:
    def test_tenant_users_with_role_query_param(self, monkeypatch):
        engine, SL = _make_db()
        ids = _api_seed(SL)
        try:
            with _api_client(monkeypatch, SL, ids["owner_sub"]) as c:
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
            Base.metadata.drop_all(engine)

    def test_tenant_users_with_status_query_param(self, monkeypatch):
        engine, SL = _make_db()
        ids = _api_seed(SL)
        try:
            with _api_client(monkeypatch, SL, ids["owner_sub"]) as c:
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
            Base.metadata.drop_all(engine)

    def test_platform_users_with_role_query_param(self, monkeypatch):
        engine, SL = _make_db()
        ids = _api_seed(SL)
        try:
            with _api_client(monkeypatch, SL, ids["owner_sub"]) as c:
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
            Base.metadata.drop_all(engine)


class TestRouteResendByInvitationId:
    def test_resend_by_id_returns_200(self, monkeypatch):
        engine, SL = _make_db()
        ids = _api_seed(SL)
        try:
            # Seed an invitation directly
            from uuid import UUID as _UUID
            db = SL()
            inv = Invitation(
                tenant_id=_UUID(ids["tenant_id"]),
                email="invite@rt.io",
                token="raw-tok-123",
                token_hash="hash789",
                target_scope_type="account",
                target_scope_id=_UUID(ids["tenant_id"]),
                target_role_name="account_member",
                created_by=_UUID(ids["owner_id"]),
                expires_at=datetime.utcnow() + timedelta(days=7),
            )
            db.add(inv)
            db.commit()
            db.refresh(inv)
            inv_id = str(inv.id)
            db.close()

            with _api_client(monkeypatch, SL, ids["owner_sub"]) as c:
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
            Base.metadata.drop_all(engine)

    def test_resend_by_id_nonexistent_returns_404(self, monkeypatch):
        engine, SL = _make_db()
        ids = _api_seed(SL)
        try:
            with _api_client(monkeypatch, SL, ids["owner_sub"]) as c:
                r = c.post(
                    f"/auth/tenants/{ids['tenant_id']}/invitations/{uuid4()}/resend",
                    headers=_scoped_headers(ids["tenant_id"]),
                )
                assert r.status_code == 404
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(engine)

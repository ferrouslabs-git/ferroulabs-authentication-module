"""Route-level integration tests covering invitation, space, tenant-user,
session, and auth-routes APIs via TestClient with dependency overrides.

Target: uncovered route handler bodies identified by coverage analysis.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.auth_usermanagement.models.invitation import Invitation
from app.auth_usermanagement.models.membership import Membership
from app.auth_usermanagement.models.session import Session as AuthSession
from app.auth_usermanagement.models.space import Space
from app.auth_usermanagement.models.tenant import Tenant
from app.auth_usermanagement.models.user import User
from app.auth_usermanagement.security import dependencies as security_deps
from app.database import Base, get_db
from app.main import app
from tests.async_test_utils import make_test_db, make_async_app


# ── Helpers ──────────────────────────────────────────────────────


def _utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _make_db():
    sync_engine, SyncSessionLocal, async_engine, AsyncSessionLocal = make_test_db()
    return sync_engine, SyncSessionLocal, async_engine, AsyncSessionLocal


def _seed(SL):
    s = SL()
    admin = User(cognito_sub="admin-sub", email="admin@test.com", name="Admin", is_platform_admin=True)
    owner = User(cognito_sub="owner-sub", email="owner@test.com", name="Owner")
    member = User(cognito_sub="member-sub", email="member@test.com", name="Member")
    outsider = User(cognito_sub="outsider-sub", email="outsider@test.com", name="Outsider")
    tenant = Tenant(name="Acme", plan="pro", status="active")
    s.add_all([admin, owner, member, outsider, tenant])
    s.commit()

    s.add_all([
        Membership(user_id=owner.id, scope_type="account", scope_id=tenant.id,
                   role_name="account_owner", status="active"),
        Membership(user_id=member.id, scope_type="account", scope_id=tenant.id,
                   role_name="account_member", status="active"),
    ])
    s.commit()

    space = Space(name="Alpha", account_id=tenant.id, status="active")
    s.add(space)
    s.commit()

    s.add(Membership(user_id=owner.id, scope_type="space", scope_id=space.id,
                     role_name="space_admin", status="active"))
    s.commit()

    s.refresh(admin); s.refresh(owner); s.refresh(member); s.refresh(outsider)
    s.refresh(tenant); s.refresh(space)
    ids = dict(
        admin_sub=admin.cognito_sub, owner_sub=owner.cognito_sub,
        member_sub=member.cognito_sub, outsider_sub=outsider.cognito_sub,
        admin_id=str(admin.id), owner_id=str(owner.id),
        member_id=str(member.id), outsider_id=str(outsider.id),
        tenant_id=str(tenant.id), space_id=str(space.id),
    )
    s.close()
    return ids


def _client(monkeypatch, AsyncSessionLocal, user_sub):
    async def _override():
        async with AsyncSessionLocal() as session:
            yield session

    monkeypatch.setattr(
        security_deps, "verify_token_async",
        AsyncMock(return_value=SimpleNamespace(sub=user_sub)),
    )
    app.dependency_overrides[get_db] = _override
    return TestClient(app, raise_server_exceptions=False)


def _auth():
    return {"Authorization": "Bearer fake-token"}


def _scoped(tid):
    return {**_auth(), "X-Tenant-ID": tid}


def _scope_headers(scope_type, scope_id):
    return {**_auth(), "X-Scope-Type": scope_type, "X-Scope-ID": scope_id}


# ── Invitation route tests ──────────────────────────────────────


class TestInvitationPreview:
    """GET /invites/{token} — covers invitation_routes lines 62-66."""

    def test_preview_valid_invitation(self, monkeypatch):
        sync_engine, SL, async_engine, ASL = _make_db()
        ids = _seed(SL)
        # Create an invitation directly
        s = SL()
        tenant = s.query(Tenant).first()
        token_raw = "a" * 64
        import hashlib
        token_hash = hashlib.sha256(token_raw.encode()).hexdigest()
        inv = Invitation(
            tenant_id=tenant.id, email="invitee@test.com",
            token_hash=token_hash, token=token_hash,
            target_scope_type="account", target_scope_id=tenant.id,
            target_role_name="account_member",
            expires_at=_utc_now() + timedelta(days=2),
            created_by=s.query(User).filter(User.cognito_sub == "owner-sub").first().id,
        )
        s.add(inv)
        s.commit()
        s.close()
        try:
            with _client(monkeypatch, ASL, ids["owner_sub"]) as c:
                r = c.get(f"/auth/invites/{token_raw}", headers=_auth())
                assert r.status_code == 200
                data = r.json()
                assert data["email"] == "invitee@test.com"
                assert data["tenant_name"] == "Acme"
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_preview_invalid_token_returns_404(self, monkeypatch):
        sync_engine, SL, async_engine, ASL = _make_db()
        ids = _seed(SL)
        try:
            with _client(monkeypatch, ASL, ids["owner_sub"]) as c:
                r = c.get("/auth/invites/nonexistent-token-xyz", headers=_auth())
                assert r.status_code == 404
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)


class TestInvitationAccept:
    """POST /invites/accept — covers invitation_routes lines 208, 230-250."""

    def test_accept_valid_invitation(self, monkeypatch):
        sync_engine, SL, async_engine, ASL = _make_db()
        ids = _seed(SL)
        s = SL()
        tenant = s.query(Tenant).first()
        outsider = s.query(User).filter(User.cognito_sub == "outsider-sub").first()
        token_raw = "b" * 64
        import hashlib
        token_hash = hashlib.sha256(token_raw.encode()).hexdigest()
        inv = Invitation(
            tenant_id=tenant.id, email=outsider.email,
            token_hash=token_hash, token=token_hash,
            target_scope_type="account", target_scope_id=tenant.id,
            target_role_name="account_member",
            expires_at=_utc_now() + timedelta(days=2),
            created_by=s.query(User).filter(User.cognito_sub == "owner-sub").first().id,
        )
        s.add(inv)
        s.commit()
        s.close()
        try:
            with _client(monkeypatch, ASL, ids["outsider_sub"]) as c:
                r = c.post("/auth/invites/accept", json={"token": token_raw}, headers=_auth())
                assert r.status_code == 200
                data = r.json()
                assert data["role_name"] == "account_member"
                assert data["tenant_id"] == ids["tenant_id"]
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_accept_nonexistent_token_returns_404(self, monkeypatch):
        sync_engine, SL, async_engine, ASL = _make_db()
        _seed(SL)
        try:
            with _client(monkeypatch, ASL, "outsider-sub") as c:
                r = c.post("/auth/invites/accept",
                           json={"token": "x" * 64}, headers=_auth())
                assert r.status_code == 404
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)


class TestInvitationRevoke:
    """DELETE /tenants/{tid}/invites/{token} — covers invitation_routes lines 88-107."""

    def test_revoke_invitation(self, monkeypatch):
        sync_engine, SL, async_engine, ASL = _make_db()
        ids = _seed(SL)
        s = SL()
        tenant = s.query(Tenant).first()
        owner = s.query(User).filter(User.cognito_sub == "owner-sub").first()
        token_raw = "c" * 64
        import hashlib
        token_hash = hashlib.sha256(token_raw.encode()).hexdigest()
        inv = Invitation(
            tenant_id=tenant.id, email="revokeme@test.com",
            token_hash=token_hash, token=token_hash,
            target_scope_type="account", target_scope_id=tenant.id,
            target_role_name="account_member",
            expires_at=_utc_now() + timedelta(days=2),
            created_by=owner.id,
        )
        s.add(inv)
        s.commit()
        s.close()
        try:
            with _client(monkeypatch, ASL, ids["owner_sub"]) as c:
                r = c.delete(
                    f"/auth/tenants/{ids['tenant_id']}/invites/{token_raw}",
                    headers=_scoped(ids["tenant_id"]),
                )
                assert r.status_code == 200
                assert r.json()["status"] == "revoked"
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_revoke_nonexistent_returns_404(self, monkeypatch):
        sync_engine, SL, async_engine, ASL = _make_db()
        ids = _seed(SL)
        try:
            with _client(monkeypatch, ASL, ids["owner_sub"]) as c:
                r = c.delete(
                    f"/auth/tenants/{ids['tenant_id']}/invites/nonexistent",
                    headers=_scoped(ids["tenant_id"]),
                )
                assert r.status_code == 404
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)


class TestInvitationResendByToken:
    """POST /tenants/{tid}/invites/{token}/resend — covers lines 124-156."""

    @patch("app.auth_usermanagement.api.invitation_routes.send_invitation_email",
           new_callable=AsyncMock)
    def test_resend_invitation_by_token(self, mock_email, monkeypatch):
        mock_email.return_value = SimpleNamespace(sent=True, detail="ok", provider="ses")
        sync_engine, SL, async_engine, ASL = _make_db()
        ids = _seed(SL)
        s = SL()
        tenant = s.query(Tenant).first()
        owner = s.query(User).filter(User.cognito_sub == "owner-sub").first()
        token_raw = "d" * 64
        import hashlib
        token_hash = hashlib.sha256(token_raw.encode()).hexdigest()
        inv = Invitation(
            tenant_id=tenant.id, email="resendme@test.com",
            token_hash=token_hash, token=token_hash,
            target_scope_type="account", target_scope_id=tenant.id,
            target_role_name="account_member",
            expires_at=_utc_now() + timedelta(days=2),
            created_by=owner.id,
        )
        s.add(inv)
        s.commit()
        s.close()
        try:
            with _client(monkeypatch, ASL, ids["owner_sub"]) as c:
                r = c.post(
                    f"/auth/tenants/{ids['tenant_id']}/invites/{token_raw}/resend",
                    headers=_scoped(ids["tenant_id"]),
                )
                assert r.status_code == 200
                data = r.json()
                assert data["email"] == "resendme@test.com"
                assert data["email_sent"] is True
                # Token should be refreshed (different from original)
                assert len(data["token"]) > 0
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)


class TestInvitationResendById:
    """POST /tenants/{tid}/invitations/{invitation_id}/resend — covers lines 185-186+."""

    @patch("app.auth_usermanagement.api.invitation_routes.send_invitation_email",
           new_callable=AsyncMock)
    def test_resend_by_id(self, mock_email, monkeypatch):
        mock_email.return_value = SimpleNamespace(sent=True, detail="ok", provider="ses")
        sync_engine, SL, async_engine, ASL = _make_db()
        ids = _seed(SL)
        s = SL()
        tenant = s.query(Tenant).first()
        owner = s.query(User).filter(User.cognito_sub == "owner-sub").first()
        token_raw = "e" * 64
        import hashlib
        token_hash = hashlib.sha256(token_raw.encode()).hexdigest()
        inv = Invitation(
            tenant_id=tenant.id, email="resendid@test.com",
            token_hash=token_hash, token=token_hash,
            target_scope_type="account", target_scope_id=tenant.id,
            target_role_name="account_member",
            expires_at=_utc_now() + timedelta(days=2),
            created_by=owner.id,
        )
        s.add(inv)
        s.commit()
        inv_id = str(inv.id)
        s.close()
        try:
            with _client(monkeypatch, ASL, ids["owner_sub"]) as c:
                r = c.post(
                    f"/auth/tenants/{ids['tenant_id']}/invitations/{inv_id}/resend",
                    headers=_scoped(ids["tenant_id"]),
                )
                assert r.status_code == 200
                assert r.json()["email_sent"] is True
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_resend_by_id_not_found(self, monkeypatch):
        sync_engine, SL, async_engine, ASL = _make_db()
        ids = _seed(SL)
        try:
            with _client(monkeypatch, ASL, ids["owner_sub"]) as c:
                r = c.post(
                    f"/auth/tenants/{ids['tenant_id']}/invitations/{uuid4()}/resend",
                    headers=_scoped(ids["tenant_id"]),
                )
                assert r.status_code == 404
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)


class TestInviteEndpoint:
    """POST /invite — covers invitation_routes line 43."""

    @patch("app.auth_usermanagement.api.route_helpers.send_invitation_email",
           new_callable=AsyncMock)
    def test_create_invitation_via_invite(self, mock_email, monkeypatch):
        mock_email.return_value = SimpleNamespace(sent=True, detail="ok", provider="ses")
        sync_engine, SL, async_engine, ASL = _make_db()
        ids = _seed(SL)
        try:
            with _client(monkeypatch, ASL, ids["owner_sub"]) as c:
                r = c.post(
                    "/auth/invite",
                    json={"email": "new@test.com", "role": "member",
                          "target_role_name": "account_member"},
                    headers=_scoped(ids["tenant_id"]),
                )
                assert r.status_code == 200
                data = r.json()
                assert data["email"] == "new@test.com"
                assert data["email_sent"] is True
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)


class TestExplicitTenantInvite:
    """POST /tenants/{tid}/invite — covers invitation_routes lines 55-56."""

    @patch("app.auth_usermanagement.api.route_helpers.send_invitation_email",
           new_callable=AsyncMock)
    def test_invite_to_explicit_tenant(self, mock_email, monkeypatch):
        mock_email.return_value = SimpleNamespace(sent=True, detail="ok", provider="ses")
        sync_engine, SL, async_engine, ASL = _make_db()
        ids = _seed(SL)
        try:
            with _client(monkeypatch, ASL, ids["owner_sub"]) as c:
                r = c.post(
                    f"/auth/tenants/{ids['tenant_id']}/invite",
                    json={"email": "explicit@test.com", "role": "member",
                          "target_role_name": "account_member"},
                    headers=_scoped(ids["tenant_id"]),
                )
                assert r.status_code == 200
                assert r.json()["email"] == "explicit@test.com"
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)


# ── Space route tests ────────────────────────────────────────────


class TestCreateSpace:
    """POST /spaces — covers space_routes lines 35-37."""

    def test_create_space(self, monkeypatch):
        sync_engine, SL, async_engine, ASL = _make_db()
        ids = _seed(SL)
        try:
            with _client(monkeypatch, ASL, ids["owner_sub"]) as c:
                r = c.post(
                    "/auth/spaces",
                    json={"name": "New Space"},
                    headers=_scoped(ids["tenant_id"]),
                )
                assert r.status_code == 201
                data = r.json()
                assert data["name"] == "New Space"
                assert data["status"] == "active"
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)


class TestListMySpaces:
    """GET /spaces/my — covers space_routes line 46."""

    def test_list_my_spaces(self, monkeypatch):
        sync_engine, SL, async_engine, ASL = _make_db()
        ids = _seed(SL)
        try:
            with _client(monkeypatch, ASL, ids["owner_sub"]) as c:
                r = c.get("/auth/spaces/my", headers=_auth())
                assert r.status_code == 200
                data = r.json()
                assert isinstance(data, list)
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)


class TestListAccountSpaces:
    """GET /accounts/{id}/spaces — covers space_routes lines 56-58."""

    def test_list_account_spaces(self, monkeypatch):
        sync_engine, SL, async_engine, ASL = _make_db()
        ids = _seed(SL)
        try:
            with _client(monkeypatch, ASL, ids["owner_sub"]) as c:
                r = c.get(
                    f"/auth/accounts/{ids['tenant_id']}/spaces",
                    headers=_scoped(ids["tenant_id"]),
                )
                assert r.status_code == 200
                data = r.json()
                assert len(data) >= 1
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_list_account_spaces_scope_mismatch_returns_403(self, monkeypatch):
        sync_engine, SL, async_engine, ASL = _make_db()
        ids = _seed(SL)
        other_id = str(uuid4())
        try:
            with _client(monkeypatch, ASL, ids["member_sub"]) as c:
                r = c.get(
                    f"/auth/accounts/{other_id}/spaces",
                    headers=_scoped(ids["tenant_id"]),
                )
                assert r.status_code == 403
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_platform_admin_can_list_any_account_spaces(self, monkeypatch):
        sync_engine, SL, async_engine, ASL = _make_db()
        ids = _seed(SL)
        try:
            with _client(monkeypatch, ASL, ids["admin_sub"]) as c:
                # Platform admin still needs scope headers for route resolution
                r = c.get(
                    f"/auth/accounts/{ids['tenant_id']}/spaces",
                    headers=_scoped(ids["tenant_id"]),
                )
                assert r.status_code == 200
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)


class TestSuspendUnsuspendSpace:
    """POST /spaces/{id}/suspend and /unsuspend — covers lines 119-123, 135-139."""

    def test_suspend_and_unsuspend_space(self, monkeypatch):
        sync_engine, SL, async_engine, ASL = _make_db()
        ids = _seed(SL)
        try:
            # Platform admin has all permissions
            with _client(monkeypatch, ASL, ids["admin_sub"]) as c:
                # Suspend
                r = c.post(
                    f"/auth/spaces/{ids['space_id']}/suspend",
                    headers=_scoped(ids["tenant_id"]),
                )
                assert r.status_code == 200
                assert r.json()["status"] == "suspended"

                # Unsuspend
                r = c.post(
                    f"/auth/spaces/{ids['space_id']}/unsuspend",
                    headers=_scoped(ids["tenant_id"]),
                )
                assert r.status_code == 200
                assert r.json()["status"] == "active"
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_suspend_nonexistent_space_returns_400(self, monkeypatch):
        sync_engine, SL, async_engine, ASL = _make_db()
        ids = _seed(SL)
        try:
            with _client(monkeypatch, ASL, ids["admin_sub"]) as c:
                r = c.post(
                    f"/auth/spaces/{uuid4()}/suspend",
                    headers=_scoped(ids["tenant_id"]),
                )
                assert r.status_code == 400
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)


class TestSpaceInvite:
    """POST /spaces/{id}/invite — covers space_routes lines 71-79."""

    @patch("app.auth_usermanagement.api.route_helpers.send_invitation_email",
           new_callable=AsyncMock)
    def test_invite_to_space(self, mock_email, monkeypatch):
        mock_email.return_value = SimpleNamespace(sent=True, detail="ok", provider="ses")
        sync_engine, SL, async_engine, ASL = _make_db()
        ids = _seed(SL)
        try:
            with _client(monkeypatch, ASL, ids["admin_sub"]) as c:
                r = c.post(
                    f"/auth/spaces/{ids['space_id']}/invite",
                    json={"email": "spaceinvite@test.com", "role": "member"},
                    headers=_scoped(ids["tenant_id"]),
                )
                assert r.status_code == 200
                data = r.json()
                assert data["email"] == "spaceinvite@test.com"
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)


# ── Tenant-user route tests ──────────────────────────────────────


class TestPatchTenantUserRole:
    """PATCH /tenants/{tid}/users/{uid}/role — covers tenant_user_routes lines 50-75."""

    def test_update_user_role(self, monkeypatch):
        sync_engine, SL, async_engine, ASL = _make_db()
        ids = _seed(SL)
        try:
            with _client(monkeypatch, ASL, ids["owner_sub"]) as c:
                r = c.patch(
                    f"/auth/tenants/{ids['tenant_id']}/users/{ids['member_id']}/role",
                    json={"role": "admin"},
                    headers=_scoped(ids["tenant_id"]),
                )
                assert r.status_code == 200
                data = r.json()
                assert data["role"] == "admin"
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_update_role_user_not_found(self, monkeypatch):
        sync_engine, SL, async_engine, ASL = _make_db()
        ids = _seed(SL)
        try:
            with _client(monkeypatch, ASL, ids["owner_sub"]) as c:
                r = c.patch(
                    f"/auth/tenants/{ids['tenant_id']}/users/{uuid4()}/role",
                    json={"role": "admin"},
                    headers=_scoped(ids["tenant_id"]),
                )
                assert r.status_code == 404
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_update_role_to_owner_allowed_by_owner(self, monkeypatch):
        """Account owner can assign owner role."""
        sync_engine, SL, async_engine, ASL = _make_db()
        ids = _seed(SL)
        try:
            with _client(monkeypatch, ASL, ids["owner_sub"]) as c:
                r = c.patch(
                    f"/auth/tenants/{ids['tenant_id']}/users/{ids['member_id']}/role",
                    json={"role": "owner"},
                    headers=_scoped(ids["tenant_id"]),
                )
                assert r.status_code == 200
                assert r.json()["role"] == "owner"
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)


class TestDeleteTenantUser:
    """DELETE /tenants/{tid}/users/{uid} — covers tenant_user_routes lines 91-109."""

    def test_remove_member_from_tenant(self, monkeypatch):
        sync_engine, SL, async_engine, ASL = _make_db()
        ids = _seed(SL)
        try:
            with _client(monkeypatch, ASL, ids["owner_sub"]) as c:
                r = c.delete(
                    f"/auth/tenants/{ids['tenant_id']}/users/{ids['member_id']}",
                    headers=_scoped(ids["tenant_id"]),
                )
                assert r.status_code == 200
                assert r.json()["status"] == "removed"
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_remove_nonexistent_user_returns_404(self, monkeypatch):
        sync_engine, SL, async_engine, ASL = _make_db()
        ids = _seed(SL)
        try:
            with _client(monkeypatch, ASL, ids["owner_sub"]) as c:
                r = c.delete(
                    f"/auth/tenants/{ids['tenant_id']}/users/{uuid4()}",
                    headers=_scoped(ids["tenant_id"]),
                )
                assert r.status_code == 404
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_remove_last_owner_rejected(self, monkeypatch):
        """Cannot remove the last account_owner."""
        sync_engine, SL, async_engine, ASL = _make_db()
        ids = _seed(SL)
        try:
            with _client(monkeypatch, ASL, ids["owner_sub"]) as c:
                r = c.delete(
                    f"/auth/tenants/{ids['tenant_id']}/users/{ids['owner_id']}",
                    headers=_scoped(ids["tenant_id"]),
                )
                assert r.status_code == 400
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)


class TestDeactivateReactivateUser:
    """PATCH /tenants/{tid}/users/{uid}/deactivate + /reactivate."""

    def test_deactivate_and_reactivate(self, monkeypatch):
        sync_engine, SL, async_engine, ASL = _make_db()
        ids = _seed(SL)
        try:
            with _client(monkeypatch, ASL, ids["owner_sub"]) as c:
                # Deactivate
                r = c.patch(
                    f"/auth/tenants/{ids['tenant_id']}/users/{ids['member_id']}/deactivate",
                    headers=_scoped(ids["tenant_id"]),
                )
                assert r.status_code == 200
                assert r.json()["status"] == "removed"

                # Reactivate
                r = c.patch(
                    f"/auth/tenants/{ids['tenant_id']}/users/{ids['member_id']}/reactivate",
                    headers=_scoped(ids["tenant_id"]),
                )
                assert r.status_code == 200
                assert r.json()["status"] == "active"
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)


# ── Session route tests ──────────────────────────────────────────


class TestRevokeAllSessions:
    """DELETE /sessions/all — covers session_routes lines 76-100."""

    def test_revoke_all_sessions(self, monkeypatch):
        sync_engine, SL, async_engine, ASL = _make_db()
        ids = _seed(SL)
        # Create sessions for owner
        s = SL()
        owner = s.query(User).filter(User.cognito_sub == "owner-sub").first()
        for i in range(3):
            s.add(AuthSession(user_id=owner.id, refresh_token_hash=f"hash-{i}"))
        s.commit()
        s.close()
        try:
            with _client(monkeypatch, ASL, ids["owner_sub"]) as c:
                r = c.delete("/auth/sessions/all", headers=_auth())
                assert r.status_code == 200
                data = r.json()
                assert data["revoked_count"] == 3
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_revoke_all_except_current(self, monkeypatch):
        sync_engine, SL, async_engine, ASL = _make_db()
        ids = _seed(SL)
        s = SL()
        owner = s.query(User).filter(User.cognito_sub == "owner-sub").first()
        sessions = [AuthSession(user_id=owner.id, refresh_token_hash=f"h-{i}") for i in range(3)]
        s.add_all(sessions)
        s.commit()
        keep_id = str(sessions[0].id)
        s.close()
        try:
            with _client(monkeypatch, ASL, ids["owner_sub"]) as c:
                r = c.delete(
                    "/auth/sessions/all",
                    headers={**_auth(), "X-Current-Session-ID": keep_id},
                )
                assert r.status_code == 200
                data = r.json()
                assert data["revoked_count"] == 2
                assert data["kept_session_id"] == keep_id
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_revoke_all_invalid_session_id_format(self, monkeypatch):
        sync_engine, SL, async_engine, ASL = _make_db()
        ids = _seed(SL)
        try:
            with _client(monkeypatch, ASL, ids["owner_sub"]) as c:
                r = c.delete(
                    "/auth/sessions/all",
                    headers={**_auth(), "X-Current-Session-ID": "not-a-uuid"},
                )
                assert r.status_code == 400
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)


class TestRevokeSession:
    """DELETE /sessions/{id} — covers session_routes lines 186-197."""

    def test_revoke_single_session(self, monkeypatch):
        sync_engine, SL, async_engine, ASL = _make_db()
        ids = _seed(SL)
        s = SL()
        owner = s.query(User).filter(User.cognito_sub == "owner-sub").first()
        session_obj = AuthSession(user_id=owner.id, refresh_token_hash="revoke-me")
        s.add(session_obj)
        s.commit()
        session_id = str(session_obj.id)
        s.close()
        try:
            with _client(monkeypatch, ASL, ids["owner_sub"]) as c:
                r = c.delete(f"/auth/sessions/{session_id}", headers=_auth())
                assert r.status_code == 200
                data = r.json()
                assert data["session_id"] == session_id
                assert data["revoked_at"] is not None
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_revoke_nonexistent_session_returns_404(self, monkeypatch):
        sync_engine, SL, async_engine, ASL = _make_db()
        ids = _seed(SL)
        try:
            with _client(monkeypatch, ASL, ids["owner_sub"]) as c:
                r = c.delete(f"/auth/sessions/{uuid4()}", headers=_auth())
                assert r.status_code == 404
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)


# ── Auth route tests ─────────────────────────────────────────────


class TestDebugToken:
    """GET /debug-token — gated behind AUTH_DEBUG env var."""

    def test_debug_token_hidden_without_auth_debug(self, monkeypatch):
        """Route returns 404 when AUTH_DEBUG is not set."""
        monkeypatch.delenv("AUTH_DEBUG", raising=False)
        sync_engine, SL, async_engine, ASL = _make_db()
        _seed(SL)
        try:
            with _client(monkeypatch, ASL, "owner-sub") as c:
                r = c.get("/auth/debug-token", headers=_auth())
                assert r.status_code == 404
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_debug_token_missing_header(self, monkeypatch):
        monkeypatch.setenv("AUTH_DEBUG", "1")
        sync_engine, SL, async_engine, ASL = _make_db()
        _seed(SL)
        try:
            with _client(monkeypatch, ASL, "owner-sub") as c:
                r = c.get("/auth/debug-token")
                assert r.status_code == 401
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_debug_token_wrong_scheme(self, monkeypatch):
        monkeypatch.setenv("AUTH_DEBUG", "1")
        sync_engine, SL, async_engine, ASL = _make_db()
        _seed(SL)
        try:
            with _client(monkeypatch, ASL, "owner-sub") as c:
                r = c.get("/auth/debug-token", headers={"Authorization": "Basic abc123"})
                assert r.status_code == 401
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_debug_token_malformed_header(self, monkeypatch):
        monkeypatch.setenv("AUTH_DEBUG", "1")
        sync_engine, SL, async_engine, ASL = _make_db()
        _seed(SL)
        try:
            with _client(monkeypatch, ASL, "owner-sub") as c:
                r = c.get("/auth/debug-token", headers={"Authorization": "BearerTokenNoSpace"})
                assert r.status_code == 401
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_debug_token_valid(self, monkeypatch):
        monkeypatch.setenv("AUTH_DEBUG", "1")
        sync_engine, SL, async_engine, ASL = _make_db()
        _seed(SL)
        try:
            with _client(monkeypatch, ASL, "owner-sub") as c:
                # Also patch verify_token as used in auth_routes directly
                from app.auth_usermanagement.api import auth_routes
                monkeypatch.setattr(
                    auth_routes, "verify_token_async",
                    AsyncMock(return_value=SimpleNamespace(sub="owner-sub", model_dump=lambda: {"sub": "owner-sub"})),
                )
                r = c.get("/auth/debug-token", headers=_auth())
                assert r.status_code == 200
                data = r.json()
                assert data["status"] == "valid"
                assert "claims" in data
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)


class TestSyncMalformedAuth:
    """POST /sync with malformed Authorization — covers auth_routes lines 105, 112-113."""

    def test_sync_malformed_header(self, monkeypatch):
        sync_engine, SL, async_engine, ASL = _make_db()
        _seed(SL)
        try:
            with _client(monkeypatch, ASL, "owner-sub") as c:
                r = c.post("/auth/sync", headers={"Authorization": "NoSpaceHere"})
                assert r.status_code == 401
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_sync_wrong_scheme(self, monkeypatch):
        sync_engine, SL, async_engine, ASL = _make_db()
        _seed(SL)
        try:
            with _client(monkeypatch, ASL, "owner-sub") as c:
                r = c.post("/auth/sync", headers={"Authorization": "Basic token123"})
                assert r.status_code == 401
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)


# ── Dependencies edge-case tests ─────────────────────────────────


class TestInvalidScopeHeaders:
    """Covers dependencies.py lines 269, 286 — invalid scope type / UUID."""

    def test_invalid_scope_type_returns_400(self, monkeypatch):
        sync_engine, SL, async_engine, ASL = _make_db()
        ids = _seed(SL)
        try:
            with _client(monkeypatch, ASL, ids["owner_sub"]) as c:
                r = c.get(
                    f"/auth/tenants/{ids['tenant_id']}/users",
                    headers={**_auth(), "X-Scope-Type": "invalid_type", "X-Scope-ID": ids["tenant_id"]},
                )
                assert r.status_code == 400
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_invalid_scope_id_returns_400(self, monkeypatch):
        sync_engine, SL, async_engine, ASL = _make_db()
        ids = _seed(SL)
        try:
            with _client(monkeypatch, ASL, ids["owner_sub"]) as c:
                r = c.get(
                    f"/auth/tenants/{ids['tenant_id']}/users",
                    headers={**_auth(), "X-Scope-Type": "account", "X-Scope-ID": "not-a-uuid"},
                )
                assert r.status_code == 400
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)


# ── route_helpers edge-case tests ────────────────────────────────


class TestRouteHelpersPermissionSuperset:
    """Covers route_helpers line 106 — invitation with overprivileged role."""

    @patch("app.auth_usermanagement.api.route_helpers.send_invitation_email",
           new_callable=AsyncMock)
    def test_invite_with_higher_role_rejected(self, mock_email, monkeypatch):
        mock_email.return_value = SimpleNamespace(sent=True, detail="ok", provider="ses")
        sync_engine, SL, async_engine, ASL = _make_db()
        ids = _seed(SL)
        try:
            # member has account_member role which lacks members:invite permission
            with _client(monkeypatch, ASL, ids["member_sub"]) as c:
                r = c.post(
                    "/auth/invite",
                    json={
                        "email": "escalate@test.com",
                        "role": "admin",
                        "target_role_name": "account_owner",
                    },
                    headers=_scoped(ids["tenant_id"]),
                )
                assert r.status_code == 403
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)


class TestRouteHelpersEmailFailed:
    """Covers route_helpers line 144 — email_send_failed audit log."""

    @patch("app.auth_usermanagement.api.route_helpers.send_invitation_email",
           new_callable=AsyncMock)
    def test_invitation_with_email_failure_still_succeeds(self, mock_email, monkeypatch):
        mock_email.return_value = SimpleNamespace(sent=False, detail="SES not configured", provider="none")
        sync_engine, SL, async_engine, ASL = _make_db()
        ids = _seed(SL)
        try:
            with _client(monkeypatch, ASL, ids["owner_sub"]) as c:
                r = c.post(
                    "/auth/invite",
                    json={"email": "noemail@test.com", "role": "member",
                          "target_role_name": "account_member"},
                    headers=_scoped(ids["tenant_id"]),
                )
                assert r.status_code == 200
                data = r.json()
                assert data["email_sent"] is False
                assert "not sent" in data["message"].lower()
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)


# ── Platform user route error branches ───────────────────────────


class TestPlatformCognitoOperationErrors:
    """Covers platform_user_routes lines 275/279, 303/307, 331/335, 357/361."""

    def test_disable_cognito_user_not_found_returns_404(self, monkeypatch):
        sync_engine, SL, async_engine, ASL = _make_db()
        ids = _seed(SL)
        try:
            with _client(monkeypatch, ASL, ids["admin_sub"]) as c:
                r = c.post(f"/auth/platform/users/{uuid4()}/cognito/disable", headers=_auth())
                assert r.status_code == 404
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_enable_cognito_user_not_found_returns_404(self, monkeypatch):
        sync_engine, SL, async_engine, ASL = _make_db()
        ids = _seed(SL)
        try:
            with _client(monkeypatch, ASL, ids["admin_sub"]) as c:
                r = c.post(f"/auth/platform/users/{uuid4()}/cognito/enable", headers=_auth())
                assert r.status_code == 404
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_get_cognito_status_user_not_found_returns_404(self, monkeypatch):
        sync_engine, SL, async_engine, ASL = _make_db()
        ids = _seed(SL)
        try:
            with _client(monkeypatch, ASL, ids["admin_sub"]) as c:
                r = c.get(f"/auth/platform/users/{uuid4()}/cognito", headers=_auth())
                assert r.status_code == 404
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_reset_password_user_not_found_returns_404(self, monkeypatch):
        sync_engine, SL, async_engine, ASL = _make_db()
        ids = _seed(SL)
        try:
            with _client(monkeypatch, ASL, ids["admin_sub"]) as c:
                r = c.post(f"/auth/platform/users/{uuid4()}/cognito/reset-password", headers=_auth())
                assert r.status_code == 404
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    @patch("app.auth_usermanagement.api.platform_user_routes.admin_disable_user_async")
    def test_disable_cognito_error_result_returns_400(self, mock_disable, monkeypatch):
        mock_disable.return_value = {"error": "Cognito error"}
        sync_engine, SL, async_engine, ASL = _make_db()
        ids = _seed(SL)
        try:
            with _client(monkeypatch, ASL, ids["admin_sub"]) as c:
                r = c.post(
                    f"/auth/platform/users/{ids['member_id']}/cognito/disable",
                    headers=_auth(),
                )
                assert r.status_code == 400
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    @patch("app.auth_usermanagement.api.platform_user_routes.admin_enable_user_async")
    def test_enable_cognito_error_result_returns_400(self, mock_enable, monkeypatch):
        mock_enable.return_value = {"error": "Cognito error"}
        sync_engine, SL, async_engine, ASL = _make_db()
        ids = _seed(SL)
        try:
            with _client(monkeypatch, ASL, ids["admin_sub"]) as c:
                r = c.post(
                    f"/auth/platform/users/{ids['member_id']}/cognito/enable",
                    headers=_auth(),
                )
                assert r.status_code == 400
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    @patch("app.auth_usermanagement.api.platform_user_routes.admin_get_user_async")
    def test_get_cognito_error_result_returns_404(self, mock_get, monkeypatch):
        mock_get.return_value = {"error": "Cognito error"}
        sync_engine, SL, async_engine, ASL = _make_db()
        ids = _seed(SL)
        try:
            with _client(monkeypatch, ASL, ids["admin_sub"]) as c:
                r = c.get(
                    f"/auth/platform/users/{ids['member_id']}/cognito",
                    headers=_auth(),
                )
                assert r.status_code == 404
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    @patch("app.auth_usermanagement.api.platform_user_routes.admin_reset_user_password_async")
    def test_reset_password_error_result_returns_400(self, mock_reset, monkeypatch):
        mock_reset.return_value = {"error": "Cognito error"}
        sync_engine, SL, async_engine, ASL = _make_db()
        ids = _seed(SL)
        try:
            with _client(monkeypatch, ASL, ids["admin_sub"]) as c:
                r = c.post(
                    f"/auth/platform/users/{ids['member_id']}/cognito/reset-password",
                    headers=_auth(),
                )
                assert r.status_code == 400
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)


class TestPlatformSuspendValueError:
    """Covers platform_user_routes lines 162-163, 199-200 — suspend/unsuspend ValueError."""

    @patch("app.auth_usermanagement.api.platform_user_routes.suspend_user")
    def test_suspend_value_error_returns_404(self, mock_suspend, monkeypatch):
        mock_suspend.side_effect = ValueError("User not found")
        sync_engine, SL, async_engine, ASL = _make_db()
        ids = _seed(SL)
        try:
            with _client(monkeypatch, ASL, ids["admin_sub"]) as c:
                r = c.patch(
                    f"/auth/users/{ids['member_id']}/suspend",
                    headers=_scoped(ids["tenant_id"]),
                )
                assert r.status_code == 404
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    @patch("app.auth_usermanagement.api.platform_user_routes.unsuspend_user")
    def test_unsuspend_value_error_returns_404(self, mock_unsuspend, monkeypatch):
        mock_unsuspend.side_effect = ValueError("User not found")
        sync_engine, SL, async_engine, ASL = _make_db()
        ids = _seed(SL)
        try:
            with _client(monkeypatch, ASL, ids["admin_sub"]) as c:
                r = c.patch(
                    f"/auth/users/{ids['member_id']}/unsuspend",
                    headers=_scoped(ids["tenant_id"]),
                )
                assert r.status_code == 404
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

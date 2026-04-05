"""API tests for medium-priority and nice-to-have endpoints (5-11).

Covers:
  #5  GET  /platform/audit-events
  #6  GET  /spaces/{space_id}
  #7  PATCH /spaces/{space_id}
  #8  POST /tenants/{tenant_id}/invitations/bulk
  #9  GET  /me/memberships
  #10 POST /platform/cleanup
  #11 DELETE /platform/tenants/{tenant_id}
"""

from datetime import datetime, timedelta, UTC
from unittest.mock import AsyncMock
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.auth_usermanagement.models.audit_event import AuditEvent
from app.auth_usermanagement.models.invitation import Invitation
from app.auth_usermanagement.models.membership import Membership
from app.auth_usermanagement.models.space import Space
from app.auth_usermanagement.models.tenant import Tenant
from app.auth_usermanagement.models.user import User
from app.auth_usermanagement.security import dependencies as security_dependencies
from app.database import Base, get_db
from app.main import app
from tests.async_test_utils import make_test_db, make_async_app


def _make_db():
    return make_test_db()


def _utc_now():
    return datetime.now(UTC).replace(tzinfo=None)


def _seed(SyncSession):
    """Seed users, tenant, memberships, spaces, audit events."""
    session = SyncSession()

    admin = User(cognito_sub="admin-sub", email="admin@example.com", name="Admin", is_platform_admin=True)
    owner = User(cognito_sub="owner-sub", email="owner@example.com", name="Owner", is_platform_admin=False)
    member = User(cognito_sub="member-sub", email="member@example.com", name="Member", is_platform_admin=False)
    outsider = User(cognito_sub="outsider-sub", email="outsider@example.com", name="Outsider", is_platform_admin=False)
    tenant = Tenant(name="Acme", plan="pro", status="active")

    session.add_all([admin, owner, member, outsider, tenant])
    session.commit()

    # Account memberships
    session.add_all([
        Membership(user_id=owner.id, scope_type="account", scope_id=tenant.id,
                   role_name="account_owner", status="active"),
        Membership(user_id=member.id, scope_type="account", scope_id=tenant.id,
                   role_name="account_member", status="active"),
    ])
    session.commit()

    # Space
    space = Space(name="Alpha Space", account_id=tenant.id, status="active")
    session.add(space)
    session.commit()

    # Space membership for owner
    session.add(Membership(
        user_id=owner.id, scope_type="space", scope_id=space.id,
        role_name="space_admin", status="active",
    ))
    session.commit()

    # Audit events
    now = _utc_now()
    session.add_all([
        AuditEvent(action="tenant_created", actor_user_id=owner.id,
                   tenant_id=tenant.id, timestamp=now - timedelta(hours=2)),
        AuditEvent(action="user_synced", actor_user_id=member.id,
                   timestamp=now - timedelta(hours=1)),
        AuditEvent(action="tenant_created", actor_user_id=admin.id,
                   tenant_id=tenant.id, timestamp=now),
    ])
    session.commit()

    session.refresh(admin)
    session.refresh(owner)
    session.refresh(member)
    session.refresh(outsider)
    session.refresh(tenant)
    session.refresh(space)

    ids = {
        "admin_sub": admin.cognito_sub,
        "owner_sub": owner.cognito_sub,
        "member_sub": member.cognito_sub,
        "outsider_sub": outsider.cognito_sub,
        "admin_id": str(admin.id),
        "owner_id": str(owner.id),
        "member_id": str(member.id),
        "tenant_id": str(tenant.id),
        "space_id": str(space.id),
    }
    session.close()
    return ids


def _client(monkeypatch, AsyncSessionLocal, user_sub):
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


def _headers():
    return {"Authorization": "Bearer fake-token"}


def _scoped_headers(tenant_id: str):
    return {"Authorization": "Bearer fake-token", "X-Tenant-ID": tenant_id}


# ── #5: GET /platform/audit-events ──────────────────────────────


class TestQueryAuditEvents:
    def test_admin_can_query_all_audit_events(self, monkeypatch):
        sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
        ids = _seed(SyncSession)
        try:
            with _client(monkeypatch, AsyncSessionLocal, ids["admin_sub"]) as c:
                r = c.get("/auth/platform/audit-events", headers=_headers())
                assert r.status_code == 200
                data = r.json()
                assert len(data) >= 3
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_admin_can_filter_by_action(self, monkeypatch):
        sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
        ids = _seed(SyncSession)
        try:
            with _client(monkeypatch, AsyncSessionLocal, ids["admin_sub"]) as c:
                r = c.get("/auth/platform/audit-events?action=tenant_created", headers=_headers())
                assert r.status_code == 200
                data = r.json()
                assert len(data) >= 2
                assert all(e["action"] == "tenant_created" for e in data)
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_admin_can_filter_by_actor(self, monkeypatch):
        sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
        ids = _seed(SyncSession)
        try:
            with _client(monkeypatch, AsyncSessionLocal, ids["admin_sub"]) as c:
                r = c.get(f"/auth/platform/audit-events?actor_user_id={ids['owner_id']}", headers=_headers())
                assert r.status_code == 200
                data = r.json()
                assert len(data) >= 1
                assert all(e["actor_user_id"] == ids["owner_id"] for e in data)
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_admin_can_paginate(self, monkeypatch):
        sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
        ids = _seed(SyncSession)
        try:
            with _client(monkeypatch, AsyncSessionLocal, ids["admin_sub"]) as c:
                r = c.get("/auth/platform/audit-events?limit=1&offset=0", headers=_headers())
                assert r.status_code == 200
                assert len(r.json()) == 1
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_non_admin_blocked(self, monkeypatch):
        sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
        ids = _seed(SyncSession)
        try:
            with _client(monkeypatch, AsyncSessionLocal, ids["owner_sub"]) as c:
                r = c.get("/auth/platform/audit-events", headers=_headers())
                assert r.status_code == 403
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)


# ── #6: GET /spaces/{space_id} ──────────────────────────────────


class TestGetSpaceDetail:
    def test_tenant_member_can_get_space(self, monkeypatch):
        sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
        ids = _seed(SyncSession)
        try:
            with _client(monkeypatch, AsyncSessionLocal, ids["owner_sub"]) as c:
                r = c.get(f"/auth/spaces/{ids['space_id']}", headers=_scoped_headers(ids["tenant_id"]))
                assert r.status_code == 200
                data = r.json()
                assert data["name"] == "Alpha Space"
                assert data["status"] == "active"
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_nonexistent_space_returns_404(self, monkeypatch):
        sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
        ids = _seed(SyncSession)
        try:
            with _client(monkeypatch, AsyncSessionLocal, ids["owner_sub"]) as c:
                r = c.get(f"/auth/spaces/{uuid4()}", headers=_scoped_headers(ids["tenant_id"]))
                assert r.status_code == 404
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)


# ── #7: PATCH /spaces/{space_id} ────────────────────────────────


class TestUpdateSpace:
    def test_owner_can_update_space_name(self, monkeypatch):
        sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
        ids = _seed(SyncSession)
        try:
            with _client(monkeypatch, AsyncSessionLocal, ids["owner_sub"]) as c:
                r = c.patch(
                    f"/auth/spaces/{ids['space_id']}",
                    json={"name": "Renamed Space"},
                    headers=_scoped_headers(ids["tenant_id"]),
                )
                assert r.status_code == 200
                assert r.json()["name"] == "Renamed Space"
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_update_nonexistent_space_returns_404(self, monkeypatch):
        sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
        ids = _seed(SyncSession)
        try:
            with _client(monkeypatch, AsyncSessionLocal, ids["owner_sub"]) as c:
                r = c.patch(
                    f"/auth/spaces/{uuid4()}",
                    json={"name": "Ghost"},
                    headers=_scoped_headers(ids["tenant_id"]),
                )
                assert r.status_code == 404
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_update_with_no_fields_returns_400(self, monkeypatch):
        sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
        ids = _seed(SyncSession)
        try:
            with _client(monkeypatch, AsyncSessionLocal, ids["owner_sub"]) as c:
                r = c.patch(
                    f"/auth/spaces/{ids['space_id']}",
                    json={},
                    headers=_scoped_headers(ids["tenant_id"]),
                )
                assert r.status_code == 400
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)


# ── #8: POST /tenants/{tenant_id}/invitations/bulk ──────────────


class TestBulkInvite:
    def test_owner_can_bulk_invite(self, monkeypatch):
        sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
        ids = _seed(SyncSession)
        try:
            with _client(monkeypatch, AsyncSessionLocal, ids["owner_sub"]) as c:
                r = c.post(
                    f"/auth/tenants/{ids['tenant_id']}/invitations/bulk",
                    json={"invitations": [
                        {"email": "a@example.com", "role": "member"},
                        {"email": "b@example.com", "role": "admin"},
                    ]},
                    headers=_headers(),
                )
                assert r.status_code == 201
                data = r.json()
                assert data["total"] == 2
                assert data["succeeded"] == 2
                assert data["failed"] == 0
                assert len(data["results"]) == 2
                assert all(res["success"] for res in data["results"])
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_admin_can_bulk_invite(self, monkeypatch):
        sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
        ids = _seed(SyncSession)
        try:
            with _client(monkeypatch, AsyncSessionLocal, ids["admin_sub"]) as c:
                r = c.post(
                    f"/auth/tenants/{ids['tenant_id']}/invitations/bulk",
                    json={"invitations": [{"email": "c@example.com"}]},
                    headers=_headers(),
                )
                assert r.status_code == 201
                assert r.json()["succeeded"] == 1
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_outsider_blocked_from_bulk_invite(self, monkeypatch):
        sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
        ids = _seed(SyncSession)
        try:
            with _client(monkeypatch, AsyncSessionLocal, ids["outsider_sub"]) as c:
                r = c.post(
                    f"/auth/tenants/{ids['tenant_id']}/invitations/bulk",
                    json={"invitations": [{"email": "x@example.com"}]},
                    headers=_headers(),
                )
                assert r.status_code == 403
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_empty_list_rejected(self, monkeypatch):
        sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
        ids = _seed(SyncSession)
        try:
            with _client(monkeypatch, AsyncSessionLocal, ids["owner_sub"]) as c:
                r = c.post(
                    f"/auth/tenants/{ids['tenant_id']}/invitations/bulk",
                    json={"invitations": []},
                    headers=_headers(),
                )
                assert r.status_code == 422  # validation error
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_bulk_invite_with_target_role_name(self, monkeypatch):
        sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
        ids = _seed(SyncSession)
        try:
            with _client(monkeypatch, AsyncSessionLocal, ids["owner_sub"]) as c:
                r = c.post(
                    f"/auth/tenants/{ids['tenant_id']}/invitations/bulk",
                    json={"invitations": [
                        {"email": "role@example.com", "role": "member", "target_role_name": "account_admin"},
                    ]},
                    headers=_headers(),
                )
                assert r.status_code == 201
                assert r.json()["succeeded"] == 1
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)


# ── #9: GET /me/memberships ─────────────────────────────────────


class TestGetMyMemberships:
    def test_owner_sees_account_membership(self, monkeypatch):
        sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
        ids = _seed(SyncSession)
        try:
            with _client(monkeypatch, AsyncSessionLocal, ids["owner_sub"]) as c:
                r = c.get("/auth/me/memberships", headers=_headers())
                assert r.status_code == 200
                data = r.json()
                # owner has account + space memberships
                assert len(data) >= 1
                scope_types = {m["scope_type"] for m in data}
                assert "account" in scope_types
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_member_sees_memberships(self, monkeypatch):
        sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
        ids = _seed(SyncSession)
        try:
            with _client(monkeypatch, AsyncSessionLocal, ids["member_sub"]) as c:
                r = c.get("/auth/me/memberships", headers=_headers())
                assert r.status_code == 200
                data = r.json()
                assert len(data) >= 1
                assert data[0]["role"] == "account_member"
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_outsider_sees_empty_memberships(self, monkeypatch):
        sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
        ids = _seed(SyncSession)
        try:
            with _client(monkeypatch, AsyncSessionLocal, ids["outsider_sub"]) as c:
                r = c.get("/auth/me/memberships", headers=_headers())
                assert r.status_code == 200
                assert len(r.json()) == 0
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_membership_includes_tenant_name(self, monkeypatch):
        sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
        ids = _seed(SyncSession)
        try:
            with _client(monkeypatch, AsyncSessionLocal, ids["owner_sub"]) as c:
                r = c.get("/auth/me/memberships", headers=_headers())
                account_memberships = [m for m in r.json() if m["scope_type"] == "account"]
                assert len(account_memberships) >= 1
                assert account_memberships[0]["tenant_name"] == "Acme"
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_unauthenticated_returns_401(self):
        with TestClient(app) as c:
            r = c.get("/auth/me/memberships")
            assert r.status_code == 401


# ── #10: POST /platform/cleanup ─────────────────────────────────


class TestPlatformCleanup:
    def test_admin_can_trigger_cleanup(self, monkeypatch):
        sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
        ids = _seed(SyncSession)
        try:
            with _client(monkeypatch, AsyncSessionLocal, ids["admin_sub"]) as c:
                r = c.post("/auth/platform/cleanup", headers=_headers())
                assert r.status_code == 200
                data = r.json()
                assert "removed" in data
                assert "refresh_tokens" in data["removed"]
                assert "invitations" in data["removed"]
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_non_admin_blocked(self, monkeypatch):
        sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
        ids = _seed(SyncSession)
        try:
            with _client(monkeypatch, AsyncSessionLocal, ids["owner_sub"]) as c:
                r = c.post("/auth/platform/cleanup", headers=_headers())
                assert r.status_code == 403
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)


# ── #11: DELETE /platform/tenants/{tenant_id} ────────────────────


class TestDeleteTenant:
    def test_admin_can_delete_tenant(self, monkeypatch):
        sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
        ids = _seed(SyncSession)
        try:
            with _client(monkeypatch, AsyncSessionLocal, ids["admin_sub"]) as c:
                r = c.delete(f"/auth/platform/tenants/{ids['tenant_id']}", headers=_headers())
                assert r.status_code == 200
                data = r.json()
                assert data["name"] == "Acme"
                assert "permanently deleted" in data["message"].lower()

                # Verify tenant is gone
                r2 = c.get(f"/auth/tenants/{ids['tenant_id']}", headers=_headers())
                assert r2.status_code == 404
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_non_admin_blocked(self, monkeypatch):
        sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
        ids = _seed(SyncSession)
        try:
            with _client(monkeypatch, AsyncSessionLocal, ids["owner_sub"]) as c:
                r = c.delete(f"/auth/platform/tenants/{ids['tenant_id']}", headers=_headers())
                assert r.status_code == 403
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_delete_nonexistent_tenant_returns_404(self, monkeypatch):
        sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
        ids = _seed(SyncSession)
        try:
            with _client(monkeypatch, AsyncSessionLocal, ids["admin_sub"]) as c:
                r = c.delete(f"/auth/platform/tenants/{uuid4()}", headers=_headers())
                assert r.status_code == 404
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

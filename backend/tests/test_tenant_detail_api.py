"""API tests for tenant detail, update, invitation listing, and platform user detail endpoints."""

from datetime import datetime, timedelta, UTC
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth_usermanagement.models.invitation import Invitation
from app.auth_usermanagement.models.membership import Membership
from app.auth_usermanagement.models.tenant import Tenant
from app.auth_usermanagement.models.user import User
from app.auth_usermanagement.security import dependencies as security_dependencies
from app.database import Base, get_db
from app.main import app


def _make_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return engine, SessionLocal


def _utc_now():
    return datetime.now(UTC).replace(tzinfo=None)


def _seed(SessionLocal):
    session = SessionLocal()

    admin = User(
        cognito_sub="admin-sub",
        email="admin@example.com",
        name="Admin",
        is_platform_admin=True,
    )
    owner = User(
        cognito_sub="owner-sub",
        email="owner@example.com",
        name="Owner",
        is_platform_admin=False,
    )
    member = User(
        cognito_sub="member-sub",
        email="member@example.com",
        name="Member",
        is_platform_admin=False,
    )
    outsider = User(
        cognito_sub="outsider-sub",
        email="outsider@example.com",
        name="Outsider",
        is_platform_admin=False,
    )
    tenant = Tenant(name="Acme", plan="pro", status="active")

    session.add_all([admin, owner, member, outsider, tenant])
    session.commit()

    session.add_all([
        Membership(user_id=owner.id, scope_type="account", scope_id=tenant.id,
                   role_name="account_owner", status="active"),
        Membership(user_id=member.id, scope_type="account", scope_id=tenant.id,
                   role_name="account_member", status="active"),
    ])
    session.commit()

    # Seed invitations
    now = _utc_now()
    pending_inv = Invitation(
        tenant_id=tenant.id,
        email="pending@example.com",
        token="hash-pending",
        token_hash="hash-pending",
        expires_at=now + timedelta(days=2),
        created_by=owner.id,
        target_scope_type="account",
        target_scope_id=tenant.id,
        target_role_name="account_member",
    )
    accepted_inv = Invitation(
        tenant_id=tenant.id,
        email="accepted@example.com",
        token="hash-accepted",
        token_hash="hash-accepted",
        expires_at=now + timedelta(days=2),
        accepted_at=now,
        created_by=owner.id,
        target_scope_type="account",
        target_scope_id=tenant.id,
        target_role_name="account_admin",
    )
    session.add_all([pending_inv, accepted_inv])
    session.commit()

    session.refresh(admin)
    session.refresh(owner)
    session.refresh(member)
    session.refresh(outsider)
    session.refresh(tenant)

    ids = {
        "admin_sub": admin.cognito_sub,
        "owner_sub": owner.cognito_sub,
        "member_sub": member.cognito_sub,
        "outsider_sub": outsider.cognito_sub,
        "tenant_id": str(tenant.id),
        "owner_id": str(owner.id),
        "member_id": str(member.id),
    }
    session.close()
    return ids


def _client(monkeypatch, SessionLocal, user_sub):
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


def _headers():
    return {"Authorization": "Bearer fake-token"}


# ── GET /tenants/{tenant_id} ────────────────────────────────────


class TestGetTenantDetail:
    def test_owner_can_get_tenant_detail(self, monkeypatch):
        engine, SessionLocal = _make_db()
        ids = _seed(SessionLocal)
        try:
            with _client(monkeypatch, SessionLocal, ids["owner_sub"]) as c:
                r = c.get(f"/auth/tenants/{ids['tenant_id']}", headers=_headers())
                assert r.status_code == 200
                data = r.json()
                assert data["name"] == "Acme"
                assert data["plan"] == "pro"
                assert data["member_count"] == 2
                assert data["owner_count"] == 1
                assert "updated_at" in data
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(engine)

    def test_platform_admin_can_get_any_tenant(self, monkeypatch):
        engine, SessionLocal = _make_db()
        ids = _seed(SessionLocal)
        try:
            with _client(monkeypatch, SessionLocal, ids["admin_sub"]) as c:
                r = c.get(f"/auth/tenants/{ids['tenant_id']}", headers=_headers())
                assert r.status_code == 200
                assert r.json()["name"] == "Acme"
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(engine)

    def test_outsider_cannot_get_tenant(self, monkeypatch):
        engine, SessionLocal = _make_db()
        ids = _seed(SessionLocal)
        try:
            with _client(monkeypatch, SessionLocal, ids["outsider_sub"]) as c:
                r = c.get(f"/auth/tenants/{ids['tenant_id']}", headers=_headers())
                assert r.status_code == 403
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(engine)

    def test_get_nonexistent_tenant_returns_404(self, monkeypatch):
        engine, SessionLocal = _make_db()
        ids = _seed(SessionLocal)
        try:
            with _client(monkeypatch, SessionLocal, ids["admin_sub"]) as c:
                r = c.get(f"/auth/tenants/{uuid4()}", headers=_headers())
                assert r.status_code == 404
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(engine)


# ── PATCH /tenants/{tenant_id} ──────────────────────────────────


class TestUpdateTenant:
    def test_owner_can_update_tenant_name(self, monkeypatch):
        engine, SessionLocal = _make_db()
        ids = _seed(SessionLocal)
        try:
            with _client(monkeypatch, SessionLocal, ids["owner_sub"]) as c:
                r = c.patch(
                    f"/auth/tenants/{ids['tenant_id']}",
                    json={"name": "Acme Corp"},
                    headers=_headers(),
                )
                assert r.status_code == 200
                assert r.json()["name"] == "Acme Corp"
                assert r.json()["plan"] == "pro"  # unchanged
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(engine)

    def test_owner_can_update_plan(self, monkeypatch):
        engine, SessionLocal = _make_db()
        ids = _seed(SessionLocal)
        try:
            with _client(monkeypatch, SessionLocal, ids["owner_sub"]) as c:
                r = c.patch(
                    f"/auth/tenants/{ids['tenant_id']}",
                    json={"plan": "enterprise"},
                    headers=_headers(),
                )
                assert r.status_code == 200
                assert r.json()["plan"] == "enterprise"
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(engine)

    def test_member_cannot_update_tenant(self, monkeypatch):
        engine, SessionLocal = _make_db()
        ids = _seed(SessionLocal)
        try:
            with _client(monkeypatch, SessionLocal, ids["member_sub"]) as c:
                r = c.patch(
                    f"/auth/tenants/{ids['tenant_id']}",
                    json={"name": "Hacked"},
                    headers=_headers(),
                )
                assert r.status_code == 403
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(engine)

    def test_platform_admin_can_update_any_tenant(self, monkeypatch):
        engine, SessionLocal = _make_db()
        ids = _seed(SessionLocal)
        try:
            with _client(monkeypatch, SessionLocal, ids["admin_sub"]) as c:
                r = c.patch(
                    f"/auth/tenants/{ids['tenant_id']}",
                    json={"name": "Admin Renamed"},
                    headers=_headers(),
                )
                assert r.status_code == 200
                assert r.json()["name"] == "Admin Renamed"
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(engine)

    def test_empty_update_rejected(self, monkeypatch):
        engine, SessionLocal = _make_db()
        ids = _seed(SessionLocal)
        try:
            with _client(monkeypatch, SessionLocal, ids["owner_sub"]) as c:
                r = c.patch(
                    f"/auth/tenants/{ids['tenant_id']}",
                    json={},
                    headers=_headers(),
                )
                assert r.status_code == 400
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(engine)


# ── GET /tenants/{tenant_id}/invitations ─────────────────────────


class TestListTenantInvitations:
    def test_member_can_list_invitations(self, monkeypatch):
        engine, SessionLocal = _make_db()
        ids = _seed(SessionLocal)
        try:
            with _client(monkeypatch, SessionLocal, ids["member_sub"]) as c:
                r = c.get(f"/auth/tenants/{ids['tenant_id']}/invitations", headers=_headers())
                assert r.status_code == 200
                data = r.json()
                assert len(data) == 2
                emails = {inv["email"] for inv in data}
                assert "pending@example.com" in emails
                assert "accepted@example.com" in emails
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(engine)

    def test_filter_by_status_pending(self, monkeypatch):
        engine, SessionLocal = _make_db()
        ids = _seed(SessionLocal)
        try:
            with _client(monkeypatch, SessionLocal, ids["owner_sub"]) as c:
                r = c.get(
                    f"/auth/tenants/{ids['tenant_id']}/invitations?status=pending",
                    headers=_headers(),
                )
                assert r.status_code == 200
                data = r.json()
                assert len(data) == 1
                assert data[0]["email"] == "pending@example.com"
                assert data[0]["status"] == "pending"
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(engine)

    def test_filter_by_status_accepted(self, monkeypatch):
        engine, SessionLocal = _make_db()
        ids = _seed(SessionLocal)
        try:
            with _client(monkeypatch, SessionLocal, ids["owner_sub"]) as c:
                r = c.get(
                    f"/auth/tenants/{ids['tenant_id']}/invitations?status=accepted",
                    headers=_headers(),
                )
                assert r.status_code == 200
                data = r.json()
                assert len(data) == 1
                assert data[0]["email"] == "accepted@example.com"
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(engine)

    def test_outsider_cannot_list_invitations(self, monkeypatch):
        engine, SessionLocal = _make_db()
        ids = _seed(SessionLocal)
        try:
            with _client(monkeypatch, SessionLocal, ids["outsider_sub"]) as c:
                r = c.get(f"/auth/tenants/{ids['tenant_id']}/invitations", headers=_headers())
                assert r.status_code == 403
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(engine)


# ── GET /platform/users/{user_id} ───────────────────────────────


class TestGetPlatformUserDetail:
    def test_platform_admin_can_get_user_detail(self, monkeypatch):
        engine, SessionLocal = _make_db()
        ids = _seed(SessionLocal)
        try:
            with _client(monkeypatch, SessionLocal, ids["admin_sub"]) as c:
                r = c.get(f"/auth/platform/users/{ids['owner_id']}", headers=_headers())
                assert r.status_code == 200
                data = r.json()
                assert data["email"] == "owner@example.com"
                assert data["is_platform_admin"] is False
                assert len(data["memberships"]) >= 1
                acme_m = next(m for m in data["memberships"] if m["role"] == "account_owner")
                assert acme_m["tenant_name"] == "Acme"
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(engine)

    def test_non_admin_cannot_get_user_detail(self, monkeypatch):
        engine, SessionLocal = _make_db()
        ids = _seed(SessionLocal)
        try:
            with _client(monkeypatch, SessionLocal, ids["member_sub"]) as c:
                r = c.get(f"/auth/platform/users/{ids['owner_id']}", headers=_headers())
                assert r.status_code == 403
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(engine)

    def test_get_nonexistent_user_returns_404(self, monkeypatch):
        engine, SessionLocal = _make_db()
        ids = _seed(SessionLocal)
        try:
            with _client(monkeypatch, SessionLocal, ids["admin_sub"]) as c:
                r = c.get(f"/auth/platform/users/{uuid4()}", headers=_headers())
                assert r.status_code == 404
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(engine)

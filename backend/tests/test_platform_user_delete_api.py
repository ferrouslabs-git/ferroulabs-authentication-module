"""API tests for platform-admin user deletion and Cognito admin endpoints."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.auth_usermanagement.models.membership import Membership
from app.auth_usermanagement.models.session import Session as AuthSession
from app.auth_usermanagement.models.tenant import Tenant
from app.auth_usermanagement.models.user import User
from app.auth_usermanagement.security import dependencies as security_dependencies
from app.database import Base, get_db
from app.main import app
from tests.async_test_utils import make_test_db, make_async_app


def _make_db():
    return make_test_db()


def _seed(SyncSession):
    """Seed a platform admin, a regular target user, and a tenant with memberships."""
    session = SyncSession()
    tenant = Tenant(name="Acme Corp")
    admin_user = User(
        cognito_sub="admin-sub",
        email="admin@example.com",
        name="Admin",
        is_platform_admin=True,
    )
    target_user = User(
        cognito_sub="target-sub",
        email="target@example.com",
        name="Target",
    )
    # A second owner so target can be an owner without being the last one
    other_owner = User(
        cognito_sub="other-owner-sub",
        email="other@example.com",
        name="Other Owner",
    )
    session.add_all([tenant, admin_user, target_user, other_owner])
    session.commit()

    session.add_all([
        Membership(user_id=target_user.id, scope_type="account", scope_id=tenant.id, role_name="account_member", status="active"),
        Membership(user_id=other_owner.id, scope_type="account", scope_id=tenant.id, role_name="account_owner", status="active"),
    ])
    session.commit()

    ids = {
        "admin_sub": admin_user.cognito_sub,
        "admin_id": admin_user.id,
        "target_id": target_user.id,
        "target_email": target_user.email,
        "tenant_id": tenant.id,
        "other_owner_id": other_owner.id,
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
    return {"Authorization": "Bearer fake-token", "X-Tenant-ID": str(uuid4())}


# ── DELETE /platform/users/{user_id} ────────────────────────────


@patch("app.auth_usermanagement.services.cognito_admin_service.admin_delete_user")
def test_delete_user_removes_from_cognito_and_db(mock_cognito_delete, monkeypatch):
    sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
    ids = _seed(SyncSession)
    mock_cognito_delete.return_value = {"deleted": True}

    try:
        with _client(monkeypatch, AsyncSessionLocal, ids["admin_sub"]) as client:
            resp = client.delete(
                f"/auth/platform/users/{ids['target_id']}",
                headers=_headers(),
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["email"] == "target@example.com"
            assert "permanently deleted" in body["message"].lower()
            mock_cognito_delete.assert_called_once_with("target@example.com")

        # Verify user is gone from DB
        session = SyncSession()
        assert session.query(User).filter(User.id == ids["target_id"]).first() is None
        assert session.query(Membership).filter(Membership.user_id == ids["target_id"]).count() == 0
        session.close()
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(sync_engine)


@patch("app.auth_usermanagement.services.cognito_admin_service.admin_delete_user")
def test_delete_rejects_self_target(mock_cognito_delete, monkeypatch):
    sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
    ids = _seed(SyncSession)

    try:
        with _client(monkeypatch, AsyncSessionLocal, ids["admin_sub"]) as client:
            resp = client.delete(
                f"/auth/platform/users/{ids['admin_id']}",
                headers=_headers(),
            )
            assert resp.status_code == 400
            mock_cognito_delete.assert_not_called()
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(sync_engine)


@patch("app.auth_usermanagement.services.cognito_admin_service.admin_delete_user")
def test_delete_rejects_platform_admin_target(mock_cognito_delete, monkeypatch):
    """Cannot delete a user who is still a platform admin."""
    sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
    ids = _seed(SyncSession)

    # Make target a platform admin
    session = SyncSession()
    user = session.query(User).filter(User.id == ids["target_id"]).first()
    user.is_platform_admin = True
    session.commit()
    session.close()

    try:
        with _client(monkeypatch, AsyncSessionLocal, ids["admin_sub"]) as client:
            resp = client.delete(
                f"/auth/platform/users/{ids['target_id']}",
                headers=_headers(),
            )
            assert resp.status_code == 400
            assert "platform admin" in resp.json()["detail"].lower()
            mock_cognito_delete.assert_not_called()
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(sync_engine)


@patch("app.auth_usermanagement.services.cognito_admin_service.admin_delete_user")
def test_delete_rejects_last_tenant_owner(mock_cognito_delete, monkeypatch):
    """Cannot delete a user who is the sole owner of a tenant."""
    sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
    ids = _seed(SyncSession)

    # Make target the sole owner of a NEW tenant
    session = SyncSession()
    solo_tenant = Tenant(name="Solo Corp")
    session.add(solo_tenant)
    session.commit()
    session.add(
        Membership(
            user_id=ids["target_id"],
            scope_type="account",
            scope_id=solo_tenant.id,
            role_name="account_owner",
            status="active",
        )
    )
    session.commit()
    session.close()

    try:
        with _client(monkeypatch, AsyncSessionLocal, ids["admin_sub"]) as client:
            resp = client.delete(
                f"/auth/platform/users/{ids['target_id']}",
                headers=_headers(),
            )
            assert resp.status_code == 400
            assert "last owner" in resp.json()["detail"].lower()
            mock_cognito_delete.assert_not_called()
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(sync_engine)


def test_delete_requires_platform_admin(monkeypatch):
    """Regular users cannot delete other users."""
    sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
    session = SyncSession()
    regular = User(cognito_sub="regular-sub", email="regular@example.com", name="Regular")
    target = User(cognito_sub="target-del-sub", email="target-del@example.com", name="T")
    session.add_all([regular, target])
    session.commit()
    target_id = target.id
    session.close()

    try:
        with _client(monkeypatch, AsyncSessionLocal, "regular-sub") as client:
            resp = client.delete(
                f"/auth/platform/users/{target_id}",
                headers=_headers(),
            )
            assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(sync_engine)


# ── Cognito admin endpoints ─────────────────────────────────────


@patch("app.auth_usermanagement.api.platform_user_routes.admin_disable_user_async")
def test_cognito_disable_user(mock_disable, monkeypatch):
    sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
    ids = _seed(SyncSession)
    mock_disable.return_value = {"disabled": True}

    try:
        with _client(monkeypatch, AsyncSessionLocal, ids["admin_sub"]) as client:
            resp = client.post(
                f"/auth/platform/users/{ids['target_id']}/cognito/disable",
                headers=_headers(),
            )
            assert resp.status_code == 200
            assert resp.json()["message"] == "Cognito account disabled"
            mock_disable.assert_called_once_with("target@example.com")
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(sync_engine)


@patch("app.auth_usermanagement.api.platform_user_routes.admin_enable_user_async")
def test_cognito_enable_user(mock_enable, monkeypatch):
    sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
    ids = _seed(SyncSession)
    mock_enable.return_value = {"enabled": True}

    try:
        with _client(monkeypatch, AsyncSessionLocal, ids["admin_sub"]) as client:
            resp = client.post(
                f"/auth/platform/users/{ids['target_id']}/cognito/enable",
                headers=_headers(),
            )
            assert resp.status_code == 200
            assert resp.json()["message"] == "Cognito account enabled"
            mock_enable.assert_called_once_with("target@example.com")
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(sync_engine)


@patch("app.auth_usermanagement.api.platform_user_routes.admin_get_user_async")
def test_get_cognito_user_status(mock_get, monkeypatch):
    sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
    ids = _seed(SyncSession)
    mock_get.return_value = {
        "username": "target@example.com",
        "status": "CONFIRMED",
        "enabled": True,
        "created_at": "2026-01-01",
    }

    try:
        with _client(monkeypatch, AsyncSessionLocal, ids["admin_sub"]) as client:
            resp = client.get(
                f"/auth/platform/users/{ids['target_id']}/cognito",
                headers=_headers(),
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["cognito_status"] == "CONFIRMED"
            assert body["cognito_enabled"] is True
            mock_get.assert_called_once_with("target@example.com")
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(sync_engine)


@patch("app.auth_usermanagement.api.platform_user_routes.admin_reset_user_password_async")
def test_reset_cognito_password(mock_reset, monkeypatch):
    sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
    ids = _seed(SyncSession)
    mock_reset.return_value = {"reset_initiated": True}

    try:
        with _client(monkeypatch, AsyncSessionLocal, ids["admin_sub"]) as client:
            resp = client.post(
                f"/auth/platform/users/{ids['target_id']}/cognito/reset-password",
                headers=_headers(),
            )
            assert resp.status_code == 200
            assert "reset" in resp.json()["message"].lower()
            mock_reset.assert_called_once_with("target@example.com")
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(sync_engine)


@patch("app.auth_usermanagement.api.platform_user_routes.admin_disable_user_async")
def test_cognito_endpoints_require_platform_admin(mock_disable, monkeypatch):
    sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
    session = SyncSession()
    regular = User(cognito_sub="reg-sub", email="reg@example.com", name="Regular")
    target = User(cognito_sub="tgt-sub", email="tgt@example.com", name="Target")
    session.add_all([regular, target])
    session.commit()
    target_id = target.id
    session.close()

    try:
        with _client(monkeypatch, AsyncSessionLocal, "reg-sub") as client:
            resp = client.post(
                f"/auth/platform/users/{target_id}/cognito/disable",
                headers=_headers(),
            )
            assert resp.status_code == 403
            mock_disable.assert_not_called()
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(sync_engine)

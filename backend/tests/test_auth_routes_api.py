"""API tests for auth routes: /auth/sync, /auth/me, /auth/me/memberships."""
from datetime import datetime, UTC
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.async_test_utils import make_test_db, make_async_app

from app.auth_usermanagement.api.auth_routes import router
from app.auth_usermanagement.models.membership import Membership
from app.auth_usermanagement.models.tenant import Tenant
from app.auth_usermanagement.models.user import User
from app.auth_usermanagement.schemas.token import TokenPayload
from app.database import Base


# ── Helpers ──────────────────────────────────────────────────────


def _make_db():
    sync_engine, SyncSession, async_engine, AsyncSessionLocal = make_test_db()
    return sync_engine, SyncSession, async_engine, AsyncSessionLocal


_FAKE_PAYLOAD = TokenPayload(
    sub="test-sub-1",
    email="alice@example.com",
    exp=99999999999,
    iat=1000000000,
    token_use="access",
    client_id="test-client",
)

_FAKE_ID_PAYLOAD = TokenPayload(
    sub="test-sub-1",
    email="alice@example.com",
    exp=99999999999,
    iat=1000000000,
    token_use="id",
    aud="test-client",
)


def _setup_app(AsyncSessionLocal, async_engine):
    """Create a test FastAPI app with auth routes, overriding DB dependency."""
    return make_async_app(router, async_engine, AsyncSessionLocal, prefix="/auth")


# ── POST /auth/sync ─────────────────────────────────────────────


class TestAuthSync:
    @patch("app.auth_usermanagement.api.auth_routes.verify_token_async")
    def test_sync_creates_new_user(self, mock_verify):
        mock_verify.return_value = _FAKE_ID_PAYLOAD
        sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
        try:
            app = _setup_app(AsyncSessionLocal, async_engine)
            client = TestClient(app)
            resp = client.post("/auth/sync", headers={"Authorization": "Bearer fake-token"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["email"] == "alice@example.com"
            assert data["cognito_sub"] == "test-sub-1"
            assert data["message"] == "User synced successfully"
        finally:
            Base.metadata.drop_all(sync_engine)

    @patch("app.auth_usermanagement.api.auth_routes.verify_token_async")
    def test_sync_idempotent(self, mock_verify):
        mock_verify.return_value = _FAKE_ID_PAYLOAD
        sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
        try:
            app = _setup_app(AsyncSessionLocal, async_engine)
            client = TestClient(app)
            resp1 = client.post("/auth/sync", headers={"Authorization": "Bearer fake-token"})
            resp2 = client.post("/auth/sync", headers={"Authorization": "Bearer fake-token"})
            assert resp1.json()["user_id"] == resp2.json()["user_id"]
        finally:
            Base.metadata.drop_all(sync_engine)

    def test_sync_requires_authorization(self):
        sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
        try:
            app = _setup_app(AsyncSessionLocal, async_engine)
            client = TestClient(app)
            resp = client.post("/auth/sync")
            assert resp.status_code == 401
        finally:
            Base.metadata.drop_all(sync_engine)

    def test_sync_rejects_invalid_scheme(self):
        sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
        try:
            app = _setup_app(AsyncSessionLocal, async_engine)
            client = TestClient(app)
            resp = client.post("/auth/sync", headers={"Authorization": "Basic dXNlcjpwYXNz"})
            assert resp.status_code == 401
        finally:
            Base.metadata.drop_all(sync_engine)

    @patch("app.auth_usermanagement.api.auth_routes.verify_token_async")
    def test_sync_missing_email_returns_400(self, mock_verify):
        mock_verify.return_value = TokenPayload(
            sub="no-email-sub", exp=99999999999, iat=1000000000, token_use="access",
        )
        sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
        try:
            app = _setup_app(AsyncSessionLocal, async_engine)
            client = TestClient(app)
            resp = client.post("/auth/sync", headers={"Authorization": "Bearer tok"})
            assert resp.status_code == 400
        finally:
            Base.metadata.drop_all(sync_engine)


# ── GET /auth/me ─────────────────────────────────────────────────


class TestAuthMe:
    @patch("app.auth_usermanagement.security.dependencies.verify_token_async")
    def test_me_returns_user_profile(self, mock_verify):
        mock_verify.return_value = _FAKE_PAYLOAD
        sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
        try:
            # Seed user
            session = SyncSession()
            user = User(cognito_sub="test-sub-1", email="alice@example.com", name="Alice")
            session.add(user)
            session.commit()
            session.close()

            app = _setup_app(AsyncSessionLocal, async_engine)
            client = TestClient(app)
            resp = client.get("/auth/me", headers={"Authorization": "Bearer fake-token"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["email"] == "alice@example.com"
            assert data["cognito_sub"] == "test-sub-1"
        finally:
            Base.metadata.drop_all(sync_engine)

    @patch("app.auth_usermanagement.security.dependencies.verify_token_async")
    def test_me_suspended_user_rejected(self, mock_verify):
        mock_verify.return_value = _FAKE_PAYLOAD
        sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
        try:
            session = SyncSession()
            user = User(
                cognito_sub="test-sub-1", email="alice@example.com",
                name="Alice", is_active=False,
            )
            session.add(user)
            session.commit()
            session.close()

            app = _setup_app(AsyncSessionLocal, async_engine)
            client = TestClient(app)
            resp = client.get("/auth/me", headers={"Authorization": "Bearer fake-token"})
            assert resp.status_code == 401
            assert "suspended" in resp.json()["detail"].lower()
        finally:
            Base.metadata.drop_all(sync_engine)

    def test_me_without_auth_returns_401(self):
        sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
        try:
            app = _setup_app(AsyncSessionLocal, async_engine)
            client = TestClient(app)
            resp = client.get("/auth/me")
            assert resp.status_code in (401, 403)
        finally:
            Base.metadata.drop_all(sync_engine)


# ── GET /auth/me/memberships ────────────────────────────────────


class TestAuthMeMemberships:
    @patch("app.auth_usermanagement.security.dependencies.verify_token_async")
    def test_memberships_returns_active_memberships(self, mock_verify):
        mock_verify.return_value = _FAKE_PAYLOAD
        sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
        try:
            session = SyncSession()
            user = User(cognito_sub="test-sub-1", email="alice@example.com", name="Alice")
            tenant = Tenant(name="Acme Corp")
            session.add_all([user, tenant])
            session.commit()

            session.add(Membership(
                user_id=user.id, scope_type="account", scope_id=tenant.id,
                role_name="account_member", status="active",
            ))
            session.commit()
            session.close()

            app = _setup_app(AsyncSessionLocal, async_engine)
            client = TestClient(app)
            resp = client.get("/auth/me/memberships", headers={"Authorization": "Bearer fake-token"})
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 1
            assert data[0]["scope_type"] == "account"
            assert data[0]["role"] == "account_member"
            assert data[0]["tenant_name"] == "Acme Corp"
        finally:
            Base.metadata.drop_all(sync_engine)

    @patch("app.auth_usermanagement.security.dependencies.verify_token_async")
    def test_memberships_excludes_removed(self, mock_verify):
        mock_verify.return_value = _FAKE_PAYLOAD
        sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
        try:
            session = SyncSession()
            user = User(cognito_sub="test-sub-1", email="alice@example.com", name="Alice")
            tenant = Tenant(name="Old Corp")
            session.add_all([user, tenant])
            session.commit()

            session.add(Membership(
                user_id=user.id, scope_type="account", scope_id=tenant.id,
                role_name="account_member", status="removed",
            ))
            session.commit()
            session.close()

            app = _setup_app(AsyncSessionLocal, async_engine)
            client = TestClient(app)
            resp = client.get("/auth/me/memberships", headers={"Authorization": "Bearer fake-token"})
            assert resp.status_code == 200
            assert len(resp.json()) == 0
        finally:
            Base.metadata.drop_all(sync_engine)

    @patch("app.auth_usermanagement.security.dependencies.verify_token_async")
    def test_memberships_empty_for_new_user(self, mock_verify):
        mock_verify.return_value = _FAKE_PAYLOAD
        sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
        try:
            session = SyncSession()
            user = User(cognito_sub="test-sub-1", email="alice@example.com", name="Alice")
            session.add(user)
            session.commit()
            session.close()

            app = _setup_app(AsyncSessionLocal, async_engine)
            client = TestClient(app)
            resp = client.get("/auth/me/memberships", headers={"Authorization": "Bearer fake-token"})
            assert resp.status_code == 200
            assert resp.json() == []
        finally:
            Base.metadata.drop_all(sync_engine)

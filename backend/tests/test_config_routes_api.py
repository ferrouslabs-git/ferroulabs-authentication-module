"""API tests for config routes: /config/roles, /config/permissions."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth_usermanagement.api.config_routes import router
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
    sub="cfg-sub", email="config-user@example.com",
    exp=99999999999, iat=1000000000, token_use="access", client_id="test",
)


def _setup_app(SessionLocal, user=None, is_super_admin=False):
    from app.auth_usermanagement.database import get_db
    from app.auth_usermanagement.security.dependencies import get_current_user

    app = FastAPI()
    app.include_router(router)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    if user:
        app.dependency_overrides[get_current_user] = lambda: user

    return app


# ── GET /config/roles ────────────────────────────────────────────


class TestGetRoles:
    @patch("app.auth_usermanagement.security.dependencies.verify_token")
    def test_roles_returns_structure(self, mock_verify):
        mock_verify.return_value = _FAKE_PAYLOAD
        engine, SessionLocal = _make_db()
        try:
            session = SessionLocal()
            user = User(cognito_sub="cfg-sub", email="config-user@example.com", name="Config")
            session.add(user)
            session.commit()
            session.close()

            app = _setup_app(SessionLocal)
            # Override get_current_user to return our user
            from app.auth_usermanagement.security.dependencies import get_current_user
            db_s = SessionLocal()
            u = db_s.query(User).first()
            app.dependency_overrides[get_current_user] = lambda: u
            client = TestClient(app)

            resp = client.get("/config/roles", headers={"Authorization": "Bearer tok"})
            assert resp.status_code == 200
            data = resp.json()
            assert "version" in data
            assert "roles" in data
            # Should have at least 'account' and 'space' layers
            assert isinstance(data["roles"], dict)
        finally:
            db_s.close()
            Base.metadata.drop_all(engine)

    def test_roles_requires_auth(self):
        engine, SessionLocal = _make_db()
        try:
            app = _setup_app(SessionLocal)
            client = TestClient(app)
            resp = client.get("/config/roles")
            assert resp.status_code in (401, 403)
        finally:
            Base.metadata.drop_all(engine)


# ── GET /config/permissions ──────────────────────────────────────


class TestGetPermissions:
    @patch("app.auth_usermanagement.security.dependencies.verify_token")
    def test_permissions_as_super_admin(self, mock_verify):
        mock_verify.return_value = _FAKE_PAYLOAD
        engine, SessionLocal = _make_db()
        try:
            session = SessionLocal()
            user = User(
                cognito_sub="cfg-sub", email="config-user@example.com",
                name="SuperAdmin", is_platform_admin=True,
            )
            session.add(user)
            session.commit()
            session.close()

            app = _setup_app(SessionLocal)
            from app.auth_usermanagement.security.dependencies import get_current_user
            from app.auth_usermanagement.security import require_super_admin

            db_s = SessionLocal()
            u = db_s.query(User).first()
            app.dependency_overrides[get_current_user] = lambda: u

            scope_id = uuid4()
            super_ctx = ScopeContext(
                user_id=u.id, scope_type="platform", scope_id=scope_id,
                is_super_admin=True,
            )
            app.dependency_overrides[require_super_admin] = lambda: super_ctx

            client = TestClient(app)
            resp = client.get("/config/permissions", headers={"Authorization": "Bearer tok"})
            assert resp.status_code == 200
            data = resp.json()
            assert "version" in data
            assert "permission_map" in data
            assert "inheritance" in data
        finally:
            db_s.close()
            Base.metadata.drop_all(engine)

    @patch("app.auth_usermanagement.security.dependencies.verify_token")
    def test_permissions_denied_for_non_admin(self, mock_verify):
        mock_verify.return_value = _FAKE_PAYLOAD
        engine, SessionLocal = _make_db()
        try:
            session = SessionLocal()
            user = User(
                cognito_sub="cfg-sub", email="config-user@example.com",
                name="Regular", is_platform_admin=False,
            )
            session.add(user)
            session.commit()
            session.close()

            app = _setup_app(SessionLocal)
            from app.auth_usermanagement.security.dependencies import get_current_user

            db_s = SessionLocal()
            u = db_s.query(User).first()
            app.dependency_overrides[get_current_user] = lambda: u

            client = TestClient(app)
            resp = client.get(
                "/config/permissions",
                headers={
                    "Authorization": "Bearer tok",
                    "X-Scope-Type": "account",
                    "X-Scope-ID": str(uuid4()),
                },
            )
            # Should be 403 (no membership / not super admin)
            assert resp.status_code == 403
        finally:
            db_s.close()
            Base.metadata.drop_all(engine)

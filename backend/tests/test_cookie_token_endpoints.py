"""API tests for cookie/token refresh endpoints."""
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.auth_usermanagement.models.user import User
from app.auth_usermanagement.security import dependencies as security_dependencies


class _FakeSettings:
    cognito_domain = "https://auth.example.com"
    cognito_client_id = "test-client-id"
    cookie_secure = True


def _make_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return engine, SessionLocal


def _seed_user(SessionLocal):
    session = SessionLocal()
    user = User(
        cognito_sub="cookie-test-sub",
        email="cookie-test@example.com",
        name="Cookie Test User",
    )
    session.add(user)
    session.commit()
    sub = user.cognito_sub
    session.close()
    return sub


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _client_with_auth(monkeypatch, SessionLocal, user_sub):
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


# ---------------------------------------------------------------------------
# POST /auth/cookie/store-refresh
# ---------------------------------------------------------------------------

def test_store_refresh_sets_httponly_cookie(monkeypatch):
    _, SessionLocal = _make_db()
    user_sub = _seed_user(SessionLocal)

    try:
        client = _client_with_auth(monkeypatch, SessionLocal, user_sub)
        with patch("app.auth_usermanagement.api.store_refresh_token", return_value="opaque-key-123"):
            resp = client.post(
                "/auth/cookie/store-refresh",
                headers={"Authorization": "Bearer fake-token"},
                json={"refresh_token": "my-cognito-refresh-token"},
            )
        assert resp.status_code == 200
        assert resp.json()["message"] == "Refresh token stored"

        set_cookie = resp.headers.get("set-cookie", "")
        assert "trustos_refresh_token" in set_cookie
        assert "HttpOnly" in set_cookie
        assert "SameSite=strict" in set_cookie.lower() or "samesite=strict" in set_cookie.lower()
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_store_refresh_requires_auth():
    _, SessionLocal = _make_db()

    try:
        with TestClient(app) as client:
            resp = client.post(
                "/auth/cookie/store-refresh",
                json={"refresh_token": "some-token"},
            )
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# POST /auth/token/refresh
# ---------------------------------------------------------------------------

def test_token_refresh_returns_access_token(monkeypatch):
    cognito_response = {
        "access_token": "new-access-token",
        "id_token": "new-id-token",
        "expires_in": 3600,
    }
    with patch(
        "app.auth_usermanagement.api.get_refresh_token",
        return_value="valid-refresh-token",
    ), patch(
        "app.auth_usermanagement.api.call_cognito_refresh",
        return_value=cognito_response,
    ), patch("app.auth_usermanagement.api.get_settings", return_value=_FakeSettings()):
        with TestClient(app) as client:
            resp = client.post(
                "/auth/token/refresh",
                headers={"X-Requested-With": "XMLHttpRequest"},
                cookies={"trustos_refresh_token": "opaque-cookie-key"},
            )

    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"] == "new-access-token"
    assert body["id_token"] == "new-id-token"


def test_token_refresh_rejects_missing_cookie():
    with TestClient(app) as client:
        resp = client.post(
            "/auth/token/refresh",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
    assert resp.status_code == 401


def test_token_refresh_rejects_missing_csrf_header():
    with TestClient(app) as client:
        resp = client.post(
            "/auth/token/refresh",
            cookies={"trustos_refresh_token": "valid-refresh-token"},
        )
    assert resp.status_code == 403


def test_token_refresh_rejects_cognito_error(monkeypatch):
    with patch(
        "app.auth_usermanagement.api.get_refresh_token",
        return_value="expired-refresh-token",
    ), patch(
        "app.auth_usermanagement.api.call_cognito_refresh",
        side_effect=ValueError("Refresh token expired"),
    ), patch("app.auth_usermanagement.api.get_settings", return_value=_FakeSettings()):
        with TestClient(app) as client:
            resp = client.post(
                "/auth/token/refresh",
                headers={"X-Requested-With": "XMLHttpRequest"},
                cookies={"trustos_refresh_token": "opaque-cookie-key"},
            )
    assert resp.status_code == 401
    assert "Refresh token expired" in resp.json()["detail"]


def test_token_refresh_rotates_cookie_when_cognito_returns_new_refresh_token():
    cognito_response = {
        "access_token": "new-access",
        "id_token": "new-id",
        "expires_in": 3600,
        "refresh_token": "rotated-refresh-token",
    }
    with patch(
        "app.auth_usermanagement.api.get_refresh_token",
        return_value="old-refresh-token",
    ), patch(
        "app.auth_usermanagement.api.rotate_refresh_token",
        return_value="new-opaque-key",
    ), patch(
        "app.auth_usermanagement.api.call_cognito_refresh",
        return_value=cognito_response,
    ), patch("app.auth_usermanagement.api.get_settings", return_value=_FakeSettings()):
        with TestClient(app) as client:
            resp = client.post(
                "/auth/token/refresh",
                headers={"X-Requested-With": "XMLHttpRequest"},
                cookies={"trustos_refresh_token": "old-opaque-key"},
            )

    assert resp.status_code == 200
    set_cookie = resp.headers.get("set-cookie", "")
    assert "trustos_refresh_token" in set_cookie
    assert "new-opaque-key" in set_cookie


# ---------------------------------------------------------------------------
# POST /auth/cookie/clear-refresh
# ---------------------------------------------------------------------------

def test_clear_refresh_cookie_removes_cookie():
    with TestClient(app) as client:
        resp = client.post("/auth/cookie/clear-refresh")

    assert resp.status_code == 200
    assert resp.json()["message"] == "Refresh cookie cleared"
    set_cookie = resp.headers.get("set-cookie", "")
    assert "trustos_refresh_token" in set_cookie
    assert "Max-Age=0" in set_cookie


# ---------------------------------------------------------------------------
# Rate limiting — POST /auth/token/refresh
# ---------------------------------------------------------------------------

def test_token_refresh_is_rate_limited():
    """Exceeding the rate limit on /auth/token/refresh returns 429."""
    from app.auth_usermanagement.security.rate_limit_middleware import RateLimitMiddleware

    # Use a very tight limit (2 requests) so the test runs fast.
    original_limit = RateLimitMiddleware.__init__

    def _tight_limit(self, app, limit=2, window_seconds=60):
        original_limit(self, app, limit=limit, window_seconds=window_seconds)

    with patch(
        "app.auth_usermanagement.security.rate_limit_middleware.RateLimitMiddleware.__init__",
        _tight_limit,
    ), patch(
        "app.auth_usermanagement.api.get_refresh_token",
        return_value="some-refresh-token",
    ), patch(
        "app.auth_usermanagement.api.call_cognito_refresh",
        return_value={"access_token": "tok", "id_token": "id", "expires_in": 3600},
    ), patch(
        "app.auth_usermanagement.api.get_settings",
        return_value=_FakeSettings(),
    ):
        # Re-instantiate the app with the patched middleware so limit takes effect.
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware
        from app.auth_usermanagement.api import router as auth_router
        from app.auth_usermanagement.security.rate_limit_middleware import RateLimitMiddleware as RLM
        from app.auth_usermanagement.security.security_headers_middleware import SecurityHeadersMiddleware
        from app.auth_usermanagement.security.tenant_middleware import TenantContextMiddleware

        test_app = FastAPI()
        test_app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
        test_app.add_middleware(TenantContextMiddleware)
        test_app.add_middleware(RLM, limit=2, window_seconds=60)
        test_app.add_middleware(SecurityHeadersMiddleware)
        test_app.include_router(auth_router, prefix="/auth", tags=["auth"])

        with TestClient(test_app) as client:
            headers = {"X-Requested-With": "XMLHttpRequest"}
            cookies = {"trustos_refresh_token": "some-token"}

            resp1 = client.post("/auth/token/refresh", headers=headers, cookies=cookies)
            assert resp1.status_code == 200

            resp2 = client.post("/auth/token/refresh", headers=headers, cookies=cookies)
            assert resp2.status_code == 200

            resp3 = client.post("/auth/token/refresh", headers=headers, cookies=cookies)
            assert resp3.status_code == 429
            assert resp3.json()["detail"] == "Rate limit exceeded. Please retry later."
            assert "Retry-After" in resp3.headers

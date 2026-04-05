"""Unit tests for tenant isolation middleware behavior."""
import asyncio
from unittest.mock import AsyncMock
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
from starlette.requests import Request

from app.database import Base, get_db
from app.main import app
from app.auth_usermanagement.models.membership import Membership
from app.auth_usermanagement.models.tenant import Tenant
from app.auth_usermanagement.models.user import User
from app.auth_usermanagement.security import dependencies as security_dependencies
from app.auth_usermanagement.security.tenant_middleware import TenantContextMiddleware
from tests.async_test_utils import make_test_db


def _build_request(path: str, method: str = "GET", headers: list[tuple[bytes, bytes]] | None = None) -> Request:
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "path": path,
        "headers": headers or [],
        "query_string": b"",
    }
    return Request(scope)


def _noop_asgi_app(scope, receive, send):
    return None


def test_skip_non_auth_route():
    middleware = TenantContextMiddleware(_noop_asgi_app)
    request = _build_request("/health")

    assert middleware._should_skip_middleware(request) is True


def test_skip_invite_token_preview_route():
    middleware = TenantContextMiddleware(_noop_asgi_app)
    request = _build_request(f"/auth/invites/{uuid4()}")

    assert middleware._should_skip_middleware(request) is True


def test_skip_session_routes():
    middleware = TenantContextMiddleware(_noop_asgi_app)
    request = _build_request("/auth/sessions/all", method="DELETE")

    assert middleware._should_skip_middleware(request) is True


def test_protected_route_requires_tenant_header():
    middleware = TenantContextMiddleware(_noop_asgi_app)
    request = _build_request("/auth/tenants/123/users", headers=[(b"authorization", b"Bearer token")])

    async def call_next(_request):
        raise AssertionError("call_next should not run when tenant header is missing")

    response = asyncio.run(middleware.dispatch(request, call_next))

    assert response.status_code == 400
    body = response.body.decode("utf-8")
    assert "X-Tenant-ID header required" in body


def test_custom_auth_prefix_skips_non_matching_paths():
    middleware = TenantContextMiddleware(_noop_asgi_app, auth_prefix="/iam")
    request = _build_request("/auth/tenants/123/users", headers=[(b"authorization", b"Bearer token")])

    assert middleware._should_skip_middleware(request) is True


def test_custom_auth_prefix_protects_matching_paths():
    middleware = TenantContextMiddleware(_noop_asgi_app, auth_prefix="/iam")
    request = _build_request("/iam/tenants/123/users", headers=[(b"authorization", b"Bearer token")])

    async def call_next(_request):
        raise AssertionError("call_next should not run when tenant header is missing")

    response = asyncio.run(middleware.dispatch(request, call_next))

    assert response.status_code == 400
    assert "X-Tenant-ID header required" in response.body.decode("utf-8")


def test_cross_tenant_access_blocked_at_api_level(monkeypatch):
    sync_engine, SyncSession, async_engine, AsyncSessionLocal = make_test_db()

    session = SyncSession()
    user = User(
        cognito_sub="middleware-api-sub",
        email="middleware-api@example.com",
        name="Middleware API User",
    )
    tenant_a = Tenant(name="Tenant A")
    tenant_b = Tenant(name="Tenant B")
    session.add_all([user, tenant_a, tenant_b])
    session.flush()
    session.add(
        Membership(
            user_id=user.id,
            scope_type="account",
            scope_id=tenant_a.id,
            role_name="account_owner",
            status="active",
        )
    )
    session.commit()
    user_sub = user.cognito_sub
    tenant_b_id = str(tenant_b.id)
    session.close()

    async def _override_get_db():
        async with AsyncSessionLocal() as session:
            yield session

    monkeypatch.setattr(
        security_dependencies,
        "verify_token_async",
        AsyncMock(return_value=SimpleNamespace(sub=user_sub)),
    )
    app.dependency_overrides[get_db] = _override_get_db

    try:
        with TestClient(app) as client:
            response = client.get(
                "/auth/tenant-context",
                headers={
                    "Authorization": "Bearer fake-token",
                    "X-Tenant-ID": tenant_b_id,
                },
            )
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(sync_engine)

    assert response.status_code == 403
    assert "Access denied" in response.text

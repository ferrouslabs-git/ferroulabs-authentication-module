"""Unit tests for tenant isolation middleware behavior."""
import asyncio
from uuid import uuid4

from starlette.requests import Request

from app.auth_usermanagement.security.tenant_middleware import TenantContextMiddleware


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

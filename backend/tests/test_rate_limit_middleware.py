"""Unit tests for rate-limit middleware route matching behavior."""
from app.auth_usermanagement.security.rate_limit_middleware import RateLimitMiddleware


def _noop_asgi_app(scope, receive, send):
    return None


def test_default_prefix_protected_routes_match_auth_paths():
    middleware = RateLimitMiddleware(_noop_asgi_app)

    assert middleware._is_protected_path("/auth/debug-token") is True
    assert middleware._is_protected_path("/auth/tenants/abc/invite") is True
    assert middleware._is_protected_path("/iam/debug-token") is False


def test_custom_prefix_protected_routes_match_custom_paths():
    middleware = RateLimitMiddleware(_noop_asgi_app, auth_prefix="/iam")

    assert middleware._is_protected_path("/iam/debug-token") is True
    assert middleware._is_protected_path("/iam/tenants/abc/invite") is True
    assert middleware._is_protected_path("/auth/debug-token") is False

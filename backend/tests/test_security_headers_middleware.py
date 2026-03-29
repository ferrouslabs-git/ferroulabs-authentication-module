"""Unit tests for SecurityHeadersMiddleware."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth_usermanagement.security.security_headers_middleware import SecurityHeadersMiddleware


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/test")
    async def test_endpoint():
        return {"ok": True}

    return app


@pytest.fixture
def client():
    return TestClient(_make_app())


class TestSecurityHeaders:
    def test_x_content_type_options(self, client):
        resp = client.get("/test")
        assert resp.headers["X-Content-Type-Options"] == "nosniff"

    def test_x_frame_options(self, client):
        resp = client.get("/test")
        assert resp.headers["X-Frame-Options"] == "DENY"

    def test_referrer_policy(self, client):
        resp = client.get("/test")
        assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

    def test_permissions_policy(self, client):
        resp = client.get("/test")
        assert resp.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"

    def test_cross_origin_opener_policy(self, client):
        resp = client.get("/test")
        assert resp.headers["Cross-Origin-Opener-Policy"] == "same-origin"

    def test_cross_origin_resource_policy(self, client):
        resp = client.get("/test")
        assert resp.headers["Cross-Origin-Resource-Policy"] == "same-origin"

    def test_content_security_policy(self, client):
        resp = client.get("/test")
        csp = resp.headers["Content-Security-Policy"]
        assert "default-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp
        assert "object-src 'none'" in csp

    def test_x_permitted_cross_domain_policies(self, client):
        resp = client.get("/test")
        assert resp.headers["X-Permitted-Cross-Domain-Policies"] == "none"

    def test_headers_present_on_all_responses(self, client):
        """Even 404s should have security headers."""
        resp = client.get("/nonexistent")
        assert resp.status_code == 404
        assert "X-Content-Type-Options" in resp.headers
        assert "X-Frame-Options" in resp.headers

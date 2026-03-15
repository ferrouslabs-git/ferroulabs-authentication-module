"""Integration test for auth prefix wiring in app bootstrap."""
import importlib

from fastapi.testclient import TestClient


def test_main_uses_configured_auth_prefix(monkeypatch):
    monkeypatch.setenv("AUTH_API_PREFIX", "/iam")

    import app.auth_usermanagement.config as auth_config
    auth_config.get_settings.cache_clear()

    import app.main as main_module
    main_module = importlib.reload(main_module)

    try:
        with TestClient(main_module.app) as client:
            # Route exists under configured prefix; missing auth should yield 401.
            configured = client.get("/iam/debug-token")
            assert configured.status_code == 401

            # Old hardcoded route should not exist anymore.
            legacy = client.get("/auth/debug-token")
            assert legacy.status_code == 404
    finally:
        auth_config.get_settings.cache_clear()

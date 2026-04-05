"""Regression tests for host/module DB ownership boundaries."""
from pathlib import Path


def test_auth_database_module_reuses_host_runtime_objects():
    from app import database as host_db
    from app.auth_usermanagement import database as auth_db

    assert auth_db.Base is host_db.Base
    assert auth_db.AsyncSessionLocal is host_db.AsyncSessionLocal
    assert auth_db.engine is host_db.engine
    assert auth_db.get_db is host_db.get_db


def test_auth_config_does_not_define_database_url():
    from app.auth_usermanagement.config import get_settings

    settings = get_settings()
    assert not hasattr(settings, "database_url")


def test_tenant_middleware_does_not_instantiate_sessionlocal_directly():
    middleware_path = Path(__file__).resolve().parents[1] / "app" / "auth_usermanagement" / "security" / "tenant_middleware.py"
    source = middleware_path.read_text(encoding="utf-8")

    assert "SessionLocal(" not in source

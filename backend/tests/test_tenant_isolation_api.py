"""API-level tenant isolation regression tests."""
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.auth_usermanagement.models.membership import Membership
from app.auth_usermanagement.models.tenant import Tenant
from app.auth_usermanagement.models.user import User
from app.auth_usermanagement.security import dependencies as security_dependencies


def _seed_user_and_tenants(db_session):
    user = User(
        cognito_sub="test-sub-tenant-isolation",
        email="tenant-isolation@example.com",
        name="Tenant Isolation User",
    )
    tenant_a = Tenant(name="Tenant A")
    tenant_b = Tenant(name="Tenant B")

    db_session.add_all([user, tenant_a, tenant_b])
    db_session.flush()

    membership_a = Membership(
        user_id=user.id,
        scope_type="account",
        scope_id=tenant_a.id,
        role_name="account_owner",
        status="active",
    )
    db_session.add(membership_a)
    db_session.commit()

    return {
        "user_id": str(user.id),
        "user_sub": user.cognito_sub,
        "tenant_a_id": str(tenant_a.id),
        "tenant_b_id": str(tenant_b.id),
    }


def test_tenant_context_endpoint_allows_member_tenant(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)

    seed_session = SessionLocal()
    seeded = _seed_user_and_tenants(seed_session)
    seed_session.close()

    def _override_get_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr(
        security_dependencies,
        "verify_token",
        lambda _token: SimpleNamespace(sub=seeded["user_sub"]),
    )
    app.dependency_overrides[get_db] = _override_get_db

    try:
        with TestClient(app) as client:
            response = client.get(
                "/auth/tenant-context",
                headers={
                    "Authorization": "Bearer fake-token",
                    "X-Tenant-ID": seeded["tenant_a_id"],
                },
            )
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)

    assert response.status_code == 200
    payload = response.json()
    assert payload["tenant_id"] == seeded["tenant_a_id"]
    assert payload["user_id"] == seeded["user_id"]


def test_tenant_context_endpoint_blocks_cross_tenant_access(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)

    seed_session = SessionLocal()
    seeded = _seed_user_and_tenants(seed_session)
    seed_session.close()

    def _override_get_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr(
        security_dependencies,
        "verify_token",
        lambda _token: SimpleNamespace(sub=seeded["user_sub"]),
    )
    app.dependency_overrides[get_db] = _override_get_db

    try:
        with TestClient(app) as client:
            response = client.get(
                "/auth/tenant-context",
                headers={
                    "Authorization": "Bearer fake-token",
                    "X-Tenant-ID": seeded["tenant_b_id"],
                },
            )
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)

    assert response.status_code == 403
    assert "Access denied" in response.text

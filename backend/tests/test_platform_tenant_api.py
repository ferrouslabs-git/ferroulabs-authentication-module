"""API tests for platform-admin tenant suspension endpoints."""

from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth_usermanagement.models.membership import Membership
from app.auth_usermanagement.models.tenant import Tenant
from app.auth_usermanagement.models.user import User
from app.auth_usermanagement.security import dependencies as security_dependencies
from app.database import Base, get_db
from app.main import app


def _make_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return engine, SessionLocal


def _seed_users_and_tenant(SessionLocal):
    session = SessionLocal()

    platform_admin = User(
        cognito_sub="platform-admin-sub",
        email="platform-admin@example.com",
        name="Platform Admin",
        is_platform_admin=True,
    )
    regular_user = User(
        cognito_sub="regular-sub",
        email="regular@example.com",
        name="Regular User",
        is_platform_admin=False,
    )
    tenant = Tenant(name="Acme", status="active")
    second_tenant = Tenant(name="Beta Org", status="suspended")

    session.add_all([platform_admin, regular_user, tenant, second_tenant])
    session.commit()

    session.add_all([
        Membership(user_id=platform_admin.id, tenant_id=tenant.id, role="owner", status="active"),
        Membership(user_id=regular_user.id, tenant_id=tenant.id, role="member", status="active"),
        Membership(user_id=regular_user.id, tenant_id=second_tenant.id, role="viewer", status="removed"),
    ])
    session.commit()

    session.refresh(platform_admin)
    session.refresh(regular_user)
    session.refresh(tenant)
    session.refresh(second_tenant)

    result = {
        "platform_sub": platform_admin.cognito_sub,
        "regular_sub": regular_user.cognito_sub,
        "tenant_id": str(tenant.id),
    }

    session.close()
    return result


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


def _auth_headers():
    return {"Authorization": "Bearer fake-token"}


def test_platform_admin_can_suspend_and_unsuspend_tenant(monkeypatch):
    engine, SessionLocal = _make_db()
    ids = _seed_users_and_tenant(SessionLocal)

    try:
        with _client_with_auth(monkeypatch, SessionLocal, ids["platform_sub"]) as client:
            suspend_response = client.patch(
                f"/auth/platform/tenants/{ids['tenant_id']}/suspend",
                headers=_auth_headers(),
            )
            assert suspend_response.status_code == 200
            assert suspend_response.json()["status"] == "suspended"

            unsuspend_response = client.patch(
                f"/auth/platform/tenants/{ids['tenant_id']}/unsuspend",
                headers=_auth_headers(),
            )
            assert unsuspend_response.status_code == 200
            assert unsuspend_response.json()["status"] == "active"
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)


def test_platform_admin_can_list_all_tenants(monkeypatch):
    engine, SessionLocal = _make_db()
    ids = _seed_users_and_tenant(SessionLocal)

    try:
        with _client_with_auth(monkeypatch, SessionLocal, ids["platform_sub"]) as client:
            response = client.get(
                "/auth/platform/tenants",
                headers=_auth_headers(),
            )
            assert response.status_code == 200

            payload = response.json()
            assert len(payload) == 2

            acme = next(tenant for tenant in payload if tenant["name"] == "Acme")
            assert acme["member_count"] == 2
            assert acme["owner_count"] == 1

            beta = next(tenant for tenant in payload if tenant["name"] == "Beta Org")
            assert beta["status"] == "suspended"
            assert beta["member_count"] == 0
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)


def test_non_platform_admin_cannot_suspend_tenant(monkeypatch):
    engine, SessionLocal = _make_db()
    ids = _seed_users_and_tenant(SessionLocal)

    try:
        with _client_with_auth(monkeypatch, SessionLocal, ids["regular_sub"]) as client:
            response = client.patch(
                f"/auth/platform/tenants/{ids['tenant_id']}/suspend",
                headers=_auth_headers(),
            )
            assert response.status_code == 403
            assert response.json()["detail"] == "Only platform administrators can suspend tenant user accounts"
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)

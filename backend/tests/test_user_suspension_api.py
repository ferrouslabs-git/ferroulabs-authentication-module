"""API tests for platform-admin user suspension endpoints."""

from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

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


def _seed_users(SessionLocal):
    session = SessionLocal()
    admin_user = User(
        cognito_sub="platform-admin-sub",
        email="admin@example.com",
        name="Platform Admin",
        is_platform_admin=True,
    )
    target_user = User(
        cognito_sub="target-user-sub",
        email="target@example.com",
        name="Target User",
        is_active=True,
    )
    session.add_all([admin_user, target_user])
    session.commit()
    session.refresh(admin_user)
    session.refresh(target_user)
    admin_id = str(admin_user.id)
    admin_sub = admin_user.cognito_sub
    target_id = str(target_user.id)
    session.close()
    return admin_id, admin_sub, target_id


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
    return {
        "Authorization": "Bearer fake-token",
        "X-Tenant-ID": str(uuid4()),
    }


def test_suspend_and_unsuspend_user_endpoints(monkeypatch):
    engine, SessionLocal = _make_db()
    _, admin_sub, target_id = _seed_users(SessionLocal)

    try:
        with _client_with_auth(monkeypatch, SessionLocal, admin_sub) as client:
            suspend_response = client.patch(
                f"/auth/users/{target_id}/suspend",
                headers=_auth_headers(),
            )
            assert suspend_response.status_code == 200
            suspend_payload = suspend_response.json()
            assert suspend_payload["user_id"] == target_id
            assert suspend_payload["is_active"] is False
            assert suspend_payload["suspended_at"] is not None

            unsuspend_response = client.patch(
                f"/auth/users/{target_id}/unsuspend",
                headers=_auth_headers(),
            )
            assert unsuspend_response.status_code == 200
            unsuspend_payload = unsuspend_response.json()
            assert unsuspend_payload["user_id"] == target_id
            assert unsuspend_payload["is_active"] is True
            assert unsuspend_payload["suspended_at"] is None
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)


def test_suspend_requires_platform_admin(monkeypatch):
    engine, SessionLocal = _make_db()
    session = SessionLocal()
    regular_user = User(
        cognito_sub="regular-user-sub",
        email="regular@example.com",
        name="Regular User",
        is_platform_admin=False,
    )
    target_user = User(
        cognito_sub="target-regular-sub",
        email="target-regular@example.com",
        name="Target Regular",
    )
    session.add_all([regular_user, target_user])
    session.commit()
    session.refresh(regular_user)
    session.refresh(target_user)
    regular_sub = regular_user.cognito_sub
    target_id = str(target_user.id)
    session.close()

    try:
        with _client_with_auth(monkeypatch, SessionLocal, regular_sub) as client:
            response = client.patch(
                f"/auth/users/{target_id}/suspend",
                headers=_auth_headers(),
            )
            assert response.status_code == 403
            assert response.json()["detail"] == "Only platform administrators can suspend user accounts"
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)


def test_suspend_rejects_self_target(monkeypatch):
    engine, SessionLocal = _make_db()
    admin_id, admin_sub, _ = _seed_users(SessionLocal)

    try:
        with _client_with_auth(monkeypatch, SessionLocal, admin_sub) as client:
            response = client.patch(
                f"/auth/users/{admin_id}/suspend",
                headers=_auth_headers(),
            )
            assert response.status_code == 400
            assert response.json()["detail"] == "You cannot suspend your own account"
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)


def test_unsuspend_requires_platform_admin(monkeypatch):
    engine, SessionLocal = _make_db()
    session = SessionLocal()
    regular_user = User(
        cognito_sub="regular-unsuspend-sub",
        email="regular-unsuspend@example.com",
        name="Regular Unsuspend",
        is_platform_admin=False,
    )
    target_user = User(
        cognito_sub="target-unsuspend-sub",
        email="target-unsuspend@example.com",
        name="Target Unsuspend",
        is_active=False,
    )
    session.add_all([regular_user, target_user])
    session.commit()
    session.refresh(regular_user)
    session.refresh(target_user)
    regular_sub = regular_user.cognito_sub
    target_id = str(target_user.id)
    session.close()

    try:
        with _client_with_auth(monkeypatch, SessionLocal, regular_sub) as client:
            response = client.patch(
                f"/auth/users/{target_id}/unsuspend",
                headers=_auth_headers(),
            )
            assert response.status_code == 403
            assert response.json()["detail"] == "Only platform administrators can unsuspend user accounts"
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)


def test_suspend_returns_404_for_missing_user(monkeypatch):
    engine, SessionLocal = _make_db()
    _, admin_sub, _ = _seed_users(SessionLocal)
    missing_user_id = str(uuid4())

    try:
        with _client_with_auth(monkeypatch, SessionLocal, admin_sub) as client:
            response = client.patch(
                f"/auth/users/{missing_user_id}/suspend",
                headers=_auth_headers(),
            )
            assert response.status_code == 404
            assert missing_user_id in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)


def test_unsuspend_returns_404_for_missing_user(monkeypatch):
    engine, SessionLocal = _make_db()
    _, admin_sub, _ = _seed_users(SessionLocal)
    missing_user_id = str(uuid4())

    try:
        with _client_with_auth(monkeypatch, SessionLocal, admin_sub) as client:
            response = client.patch(
                f"/auth/users/{missing_user_id}/unsuspend",
                headers=_auth_headers(),
            )
            assert response.status_code == 404
            assert missing_user_id in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
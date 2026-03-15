"""API tests for session registration and rotation endpoints."""
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.auth_usermanagement.models.user import User
from app.auth_usermanagement.security import dependencies as security_dependencies


def _setup_user(session):
    user = User(
        cognito_sub="session-api-sub",
        email="session-api@example.com",
        name="Session API User",
    )
    session.add(user)
    session.commit()
    return str(user.id), user.cognito_sub


def test_register_and_rotate_session_endpoints(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)

    seed_session = SessionLocal()
    user_id, user_sub = _setup_user(seed_session)
    seed_session.close()

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

    try:
        with TestClient(app) as client:
            register = client.post(
                "/auth/sessions/register",
                headers={"Authorization": "Bearer fake-token"},
                json={
                    "refresh_token": "register-token-123456",
                    "user_agent": "pytest-agent",
                    "ip_address": "10.0.0.10",
                    "device_info": "test-device",
                },
            )
            assert register.status_code == 200
            register_payload = register.json()
            assert register_payload["user_id"] == user_id
            session_id = register_payload["session_id"]

            rotate = client.post(
                f"/auth/sessions/{session_id}/rotate",
                headers={"Authorization": "Bearer fake-token"},
                json={
                    "old_refresh_token": "register-token-123456",
                    "new_refresh_token": "rotated-token-654321",
                },
            )
            assert rotate.status_code == 200
            rotate_payload = rotate.json()
            assert rotate_payload["user_id"] == user_id
            assert rotate_payload["session_id"] != session_id

            rotate_fail = client.post(
                f"/auth/sessions/{session_id}/rotate",
                headers={"Authorization": "Bearer fake-token"},
                json={
                    "old_refresh_token": "register-token-123456",
                    "new_refresh_token": "second-rotate-654321",
                },
            )
            assert rotate_fail.status_code == 404
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)

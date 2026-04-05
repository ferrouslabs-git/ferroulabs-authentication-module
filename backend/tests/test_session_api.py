"""API tests for session registration and rotation endpoints."""
from unittest.mock import AsyncMock
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.main import app
from app.auth_usermanagement.models.user import User
from app.auth_usermanagement.security import dependencies as security_dependencies
from tests.async_test_utils import make_test_db


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
    sync_engine, SyncSession, async_engine, AsyncSessionLocal = make_test_db()

    seed_session = SyncSession()
    user_id, user_sub = _setup_user(seed_session)
    seed_session.close()

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

            list_resp = client.get(
                "/auth/sessions",
                headers={
                    "Authorization": "Bearer fake-token",
                    "X-Current-Session-ID": rotate_payload["session_id"],
                },
            )
            assert list_resp.status_code == 200
            sessions = list_resp.json()
            assert len(sessions) == 1
            assert sessions[0]["session_id"] == rotate_payload["session_id"]
            assert sessions[0]["is_current"] is True

            bad_header = client.get(
                "/auth/sessions",
                headers={
                    "Authorization": "Bearer fake-token",
                    "X-Current-Session-ID": "not-a-uuid",
                },
            )
            assert bad_header.status_code == 400
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(sync_engine)

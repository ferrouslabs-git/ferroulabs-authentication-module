"""Tests for custom_ui auth mode endpoints and cognito admin service."""
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ── Test the Cognito admin service helpers ─────────────────────────

from app.auth_usermanagement.services.cognito_admin_service import (
    _generate_temp_password,
)


class TestTempPasswordGeneration:
    def test_meets_cognito_policy(self):
        """Generated passwords satisfy upper + lower + digit + special."""
        for _ in range(20):
            pw = _generate_temp_password()
            assert len(pw) == 24
            assert any(c.isupper() for c in pw), "missing uppercase"
            assert any(c.islower() for c in pw), "missing lowercase"
            assert any(c.isdigit() for c in pw), "missing digit"
            assert any(c in "!@#$%^&*()-_=+" for c in pw), "missing special"

    def test_randomness(self):
        passwords = {_generate_temp_password() for _ in range(10)}
        assert len(passwords) == 10, "Passwords should be unique"


# ── Test custom_ui_routes gating ─────────────────────────────────

def _make_app(auth_mode: str = "hosted_ui"):
    """Helper that builds a small test app with custom_ui_routes."""
    from app.auth_usermanagement.api.custom_ui_routes import router

    app = FastAPI()
    app.include_router(router)

    # Patch get_settings to return the desired auth_mode
    settings_mock = SimpleNamespace(
        auth_mode=auth_mode,
        cognito_region="eu-west-1",
        cognito_user_pool_id="test-pool",
        cognito_client_id="test-client",
        cognito_domain="https://test.auth.eu-west-1.amazoncognito.com",
    )

    app.dependency_overrides = {}
    return app, settings_mock


class TestCustomUIGating:
    """Custom UI endpoints return 404 when AUTH_MODE != custom_ui."""

    def test_login_returns_404_when_hosted_ui(self):
        app, settings_mock = _make_app("hosted_ui")
        with patch("app.auth_usermanagement.api.custom_ui_routes.get_settings", return_value=settings_mock):
            client = TestClient(app)
            resp = client.post("/custom/login", json={"email": "a@b.com", "password": "pass"})
            assert resp.status_code == 404
            assert "AUTH_MODE=custom_ui" in resp.json()["detail"]

    def test_signup_returns_404_when_hosted_ui(self):
        app, settings_mock = _make_app("hosted_ui")
        with patch("app.auth_usermanagement.api.custom_ui_routes.get_settings", return_value=settings_mock):
            client = TestClient(app)
            resp = client.post("/custom/signup", json={"email": "a@b.com", "password": "Test1234!"})
            assert resp.status_code == 404

    def test_confirm_returns_404_when_hosted_ui(self):
        app, settings_mock = _make_app("hosted_ui")
        with patch("app.auth_usermanagement.api.custom_ui_routes.get_settings", return_value=settings_mock):
            client = TestClient(app)
            resp = client.post("/custom/confirm", json={"email": "a@b.com", "code": "123456"})
            assert resp.status_code == 404

    def test_set_password_returns_404_when_hosted_ui(self):
        app, settings_mock = _make_app("hosted_ui")
        with patch("app.auth_usermanagement.api.custom_ui_routes.get_settings", return_value=settings_mock):
            client = TestClient(app)
            resp = client.post("/custom/set-password", json={
                "email": "a@b.com", "new_password": "Test1234!", "session": "abc"
            })
            assert resp.status_code == 404

    def test_resend_code_returns_404_when_hosted_ui(self):
        app, settings_mock = _make_app("hosted_ui")
        with patch("app.auth_usermanagement.api.custom_ui_routes.get_settings", return_value=settings_mock):
            client = TestClient(app)
            resp = client.post("/custom/resend-code", json={"email": "a@b.com"})
            assert resp.status_code == 404

    def test_forgot_password_returns_404_when_hosted_ui(self):
        app, settings_mock = _make_app("hosted_ui")
        with patch("app.auth_usermanagement.api.custom_ui_routes.get_settings", return_value=settings_mock):
            client = TestClient(app)
            resp = client.post("/custom/forgot-password", json={"email": "a@b.com"})
            assert resp.status_code == 404

    def test_confirm_forgot_password_returns_404_when_hosted_ui(self):
        app, settings_mock = _make_app("hosted_ui")
        with patch("app.auth_usermanagement.api.custom_ui_routes.get_settings", return_value=settings_mock):
            client = TestClient(app)
            resp = client.post("/custom/confirm-forgot-password", json={
                "email": "a@b.com", "code": "123456", "new_password": "NewPass1!"
            })
            assert resp.status_code == 404


class TestCustomUILogin:
    """Login endpoint delegates to cognito_admin_service.initiate_auth."""

    def test_successful_login(self):
        app, settings_mock = _make_app("custom_ui")
        cognito_result = {
            "authenticated": True,
            "access_token": "access_tok",
            "id_token": "id_tok",
            "refresh_token": "refresh_tok",
            "expires_in": 3600,
        }
        with patch("app.auth_usermanagement.api.custom_ui_routes.get_settings", return_value=settings_mock), \
             patch("app.auth_usermanagement.api.custom_ui_routes.initiate_auth_async", return_value=cognito_result):
            client = TestClient(app)
            resp = client.post("/custom/login", json={"email": "a@b.com", "password": "Test1234!"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["authenticated"] is True
            assert data["access_token"] == "access_tok"

    def test_login_with_new_password_challenge(self):
        app, settings_mock = _make_app("custom_ui")
        cognito_result = {
            "authenticated": False,
            "challenge": "NEW_PASSWORD_REQUIRED",
            "session": "session_token_abc",
            "challenge_parameters": {"USER_ID_FOR_SRP": "user@example.com"},
        }
        with patch("app.auth_usermanagement.api.custom_ui_routes.get_settings", return_value=settings_mock), \
             patch("app.auth_usermanagement.api.custom_ui_routes.initiate_auth_async", return_value=cognito_result):
            client = TestClient(app)
            resp = client.post("/custom/login", json={"email": "a@b.com", "password": "TempPass1!"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["authenticated"] is False
            assert data["challenge"] == "NEW_PASSWORD_REQUIRED"
            assert data["session"] == "session_token_abc"

    def test_login_invalid_credentials(self):
        app, settings_mock = _make_app("custom_ui")
        cognito_result = {"error": "Invalid email or password"}
        with patch("app.auth_usermanagement.api.custom_ui_routes.get_settings", return_value=settings_mock), \
             patch("app.auth_usermanagement.api.custom_ui_routes.initiate_auth_async", return_value=cognito_result):
            client = TestClient(app)
            resp = client.post("/custom/login", json={"email": "a@b.com", "password": "wrong"})
            assert resp.status_code == 401
            assert "Invalid" in resp.json()["detail"]


class TestCustomUISignup:
    """Signup endpoint delegates to cognito_admin_service.sign_up_user."""

    def test_successful_signup_needs_confirmation(self):
        app, settings_mock = _make_app("custom_ui")
        cognito_result = {"user_sub": "sub-123", "confirmed": False}
        with patch("app.auth_usermanagement.api.custom_ui_routes.get_settings", return_value=settings_mock), \
             patch("app.auth_usermanagement.api.custom_ui_routes.sign_up_user_async", return_value=cognito_result):
            client = TestClient(app)
            resp = client.post("/custom/signup", json={"email": "new@user.com", "password": "Test1234!"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["user_sub"] == "sub-123"
            assert data["needs_confirmation"] is True

    def test_signup_duplicate_email(self):
        app, settings_mock = _make_app("custom_ui")
        cognito_result = {"error": "An account with this email already exists"}
        with patch("app.auth_usermanagement.api.custom_ui_routes.get_settings", return_value=settings_mock), \
             patch("app.auth_usermanagement.api.custom_ui_routes.sign_up_user_async", return_value=cognito_result):
            client = TestClient(app)
            resp = client.post("/custom/signup", json={"email": "dup@user.com", "password": "Test1234!"})
            assert resp.status_code == 400
            assert "already exists" in resp.json()["detail"]


class TestCustomUISetPassword:
    """Set-password endpoint completes NEW_PASSWORD_REQUIRED challenge."""

    def test_successful_set_password(self):
        app, settings_mock = _make_app("custom_ui")
        cognito_result = {
            "authenticated": True,
            "access_token": "new_access",
            "id_token": "new_id",
            "refresh_token": "new_refresh",
            "expires_in": 3600,
        }
        with patch("app.auth_usermanagement.api.custom_ui_routes.get_settings", return_value=settings_mock), \
             patch("app.auth_usermanagement.api.custom_ui_routes.respond_to_new_password_challenge_async", return_value=cognito_result):
            client = TestClient(app)
            resp = client.post("/custom/set-password", json={
                "email": "invited@user.com",
                "new_password": "MyNewPass1!",
                "session": "session_tok",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["authenticated"] is True
            assert data["access_token"] == "new_access"

    def test_set_password_weak(self):
        app, settings_mock = _make_app("custom_ui")
        cognito_result = {"error": "Password does not meet requirements: too short"}
        with patch("app.auth_usermanagement.api.custom_ui_routes.get_settings", return_value=settings_mock), \
             patch("app.auth_usermanagement.api.custom_ui_routes.respond_to_new_password_challenge_async", return_value=cognito_result):
            client = TestClient(app)
            resp = client.post("/custom/set-password", json={
                "email": "invited@user.com",
                "new_password": "ValidLen8!",
                "session": "session_tok",
            })
            assert resp.status_code == 400


class TestCustomUIConfirm:
    """Confirm endpoint delegates to cognito_admin_service.confirm_sign_up."""

    def test_successful_confirmation(self):
        app, settings_mock = _make_app("custom_ui")
        with patch("app.auth_usermanagement.api.custom_ui_routes.get_settings", return_value=settings_mock), \
             patch("app.auth_usermanagement.api.custom_ui_routes.confirm_sign_up_async", return_value={"confirmed": True}):
            client = TestClient(app)
            resp = client.post("/custom/confirm", json={"email": "a@b.com", "code": "123456"})
            assert resp.status_code == 200
            assert resp.json()["confirmed"] is True

    def test_invalid_code(self):
        app, settings_mock = _make_app("custom_ui")
        with patch("app.auth_usermanagement.api.custom_ui_routes.get_settings", return_value=settings_mock), \
             patch("app.auth_usermanagement.api.custom_ui_routes.confirm_sign_up_async", return_value={"error": "Invalid confirmation code"}):
            client = TestClient(app)
            resp = client.post("/custom/confirm", json={"email": "a@b.com", "code": "000000"})
            assert resp.status_code == 400
            assert "Invalid" in resp.json()["detail"]


class TestCustomUIResendCode:
    def test_successful_resend(self):
        app, settings_mock = _make_app("custom_ui")
        with patch("app.auth_usermanagement.api.custom_ui_routes.get_settings", return_value=settings_mock), \
             patch("app.auth_usermanagement.api.custom_ui_routes.resend_confirmation_code_async", return_value={"sent": True}):
            client = TestClient(app)
            resp = client.post("/custom/resend-code", json={"email": "a@b.com"})
            assert resp.status_code == 200
            assert resp.json()["sent"] is True


class TestInvitationCognitoPreCreation:
    """When AUTH_MODE=custom_ui, creating an invitation should also call
    create_invited_cognito_user to pre-provision the user in Cognito."""

    def test_custom_ui_mode_calls_cognito_admin(self):
        """Verify the route_helpers integration calls cognito admin in custom_ui mode."""
        from app.auth_usermanagement.api.route_helpers import create_invitation_response
        from app.auth_usermanagement.config import Settings

        settings = Settings(
            auth_mode="custom_ui",
            frontend_url="http://localhost:5173",
            cognito_region="eu-west-1",
            cognito_user_pool_id="test-pool",
            cognito_client_id="test-client",
        )

        mock_cognito = AsyncMock(return_value={"cognito_sub": "sub-123", "temp_password": "Tmp!", "status": "FORCE_CHANGE_PASSWORD"})
        mock_email = AsyncMock(return_value=SimpleNamespace(sent=True, provider="ses", detail="ok", message_id="m1"))

        # Create minimal mocks for the invitation flow
        import asyncio
        from uuid import uuid4

        tenant_id = uuid4()
        invite_data = SimpleNamespace(
            email="invited@test.com",
            role="member",
            target_scope_type=None,
            target_scope_id=None,
            target_role_name=None,
        )
        current_user = SimpleNamespace(id=uuid4())

        fake_invitation = SimpleNamespace(
            id=uuid4(),
            tenant_id=tenant_id,
            email="invited@test.com",
            target_role_name="account_member",
            expires_at="2026-04-01T00:00:00",
            status="pending",
            target_scope_type="account",
            target_scope_id=tenant_id,
            tenant=SimpleNamespace(name="Test Tenant"),
        )
        mock_create_inv = MagicMock(return_value=(fake_invitation, "raw_token_abc"))

        with patch("app.auth_usermanagement.api.route_helpers.get_settings", return_value=settings), \
             patch("app.auth_usermanagement.api.route_helpers.create_invitation", mock_create_inv), \
             patch("app.auth_usermanagement.api.route_helpers.send_invitation_email", mock_email), \
             patch("app.auth_usermanagement.api.route_helpers.log_audit_event"), \
             patch("app.auth_usermanagement.services.cognito_admin_service.create_invited_cognito_user_async", mock_cognito):
            result = asyncio.run(
                create_invitation_response(MagicMock(), tenant_id, invite_data, current_user)
            )

        mock_cognito.assert_called_once_with("invited@test.com")

    def test_hosted_ui_mode_does_not_call_cognito_admin(self):
        """In hosted_ui mode, invitation flow should NOT touch Cognito admin."""
        from app.auth_usermanagement.api.route_helpers import create_invitation_response
        from app.auth_usermanagement.config import Settings

        settings = Settings(
            auth_mode="hosted_ui",
            frontend_url="http://localhost:5173",
            cognito_region="eu-west-1",
            cognito_user_pool_id="test-pool",
            cognito_client_id="test-client",
        )

        mock_cognito = AsyncMock()
        mock_email = AsyncMock(return_value=SimpleNamespace(sent=True, provider="ses", detail="ok", message_id="m1"))

        import asyncio
        from uuid import uuid4

        tenant_id = uuid4()
        invite_data = SimpleNamespace(
            email="invited@test.com",
            role="member",
            target_scope_type=None,
            target_scope_id=None,
            target_role_name=None,
        )
        current_user = SimpleNamespace(id=uuid4())

        fake_invitation = SimpleNamespace(
            id=uuid4(),
            tenant_id=tenant_id,
            email="invited@test.com",
            target_role_name="account_member",
            expires_at="2026-04-01T00:00:00",
            status="pending",
            target_scope_type="account",
            target_scope_id=tenant_id,
            tenant=SimpleNamespace(name="Test Tenant"),
        )
        mock_create_inv = MagicMock(return_value=(fake_invitation, "raw_token_abc"))

        with patch("app.auth_usermanagement.api.route_helpers.get_settings", return_value=settings), \
             patch("app.auth_usermanagement.api.route_helpers.create_invitation", mock_create_inv), \
             patch("app.auth_usermanagement.api.route_helpers.send_invitation_email", mock_email), \
             patch("app.auth_usermanagement.api.route_helpers.log_audit_event"), \
             patch("app.auth_usermanagement.services.cognito_admin_service.create_invited_cognito_user_async", mock_cognito):
            result = asyncio.run(
                create_invitation_response(MagicMock(), tenant_id, invite_data, current_user)
            )

        mock_cognito.assert_not_called()


class TestConfigAuthMode:
    """Verify auth_mode defaults and parsing."""

    def test_default_is_hosted_ui(self):
        from app.auth_usermanagement.config import Settings
        # Explicitly pass auth_mode to override .env file value
        s = Settings(
            auth_mode="hosted_ui",
            cognito_region="eu-west-1",
            cognito_user_pool_id="pool",
            cognito_client_id="client",
        )
        assert s.auth_mode == "hosted_ui"

    def test_custom_ui_from_env(self):
        from app.auth_usermanagement.config import Settings
        with patch.dict(os.environ, {"AUTH_MODE": "custom_ui"}):
            s = Settings(
                cognito_region="eu-west-1",
                cognito_user_pool_id="pool",
                cognito_client_id="client",
            )
            assert s.auth_mode == "custom_ui"


class TestCustomUIForgotPassword:
    """Forgot password endpoints delegate to cognito_admin_service."""

    def test_forgot_password_sends_code(self):
        app, settings_mock = _make_app("custom_ui")
        with patch("app.auth_usermanagement.api.custom_ui_routes.get_settings", return_value=settings_mock), \
             patch("app.auth_usermanagement.api.custom_ui_routes.forgot_password_async", return_value={"sent": True, "delivery": {}}):
            client = TestClient(app)
            resp = client.post("/custom/forgot-password", json={"email": "a@b.com"})
            assert resp.status_code == 200
            assert resp.json()["sent"] is True

    def test_forgot_password_rate_limited(self):
        app, settings_mock = _make_app("custom_ui")
        with patch("app.auth_usermanagement.api.custom_ui_routes.get_settings", return_value=settings_mock), \
             patch("app.auth_usermanagement.api.custom_ui_routes.forgot_password_async", return_value={"error": "Too many attempts. Please try again later."}):
            client = TestClient(app)
            resp = client.post("/custom/forgot-password", json={"email": "a@b.com"})
            assert resp.status_code == 400
            assert "Too many" in resp.json()["detail"]

    def test_confirm_forgot_password_success(self):
        app, settings_mock = _make_app("custom_ui")
        with patch("app.auth_usermanagement.api.custom_ui_routes.get_settings", return_value=settings_mock), \
             patch("app.auth_usermanagement.api.custom_ui_routes.confirm_forgot_password_async", return_value={"confirmed": True}):
            client = TestClient(app)
            resp = client.post("/custom/confirm-forgot-password", json={
                "email": "a@b.com", "code": "123456", "new_password": "NewPass1!"
            })
            assert resp.status_code == 200
            assert resp.json()["confirmed"] is True

    def test_confirm_forgot_password_invalid_code(self):
        app, settings_mock = _make_app("custom_ui")
        with patch("app.auth_usermanagement.api.custom_ui_routes.get_settings", return_value=settings_mock), \
             patch("app.auth_usermanagement.api.custom_ui_routes.confirm_forgot_password_async", return_value={"error": "Invalid reset code"}):
            client = TestClient(app)
            resp = client.post("/custom/confirm-forgot-password", json={
                "email": "a@b.com", "code": "000000", "new_password": "NewPass1!"
            })
            assert resp.status_code == 400
            assert "Invalid" in resp.json()["detail"]

    def test_confirm_forgot_password_weak_password(self):
        app, settings_mock = _make_app("custom_ui")
        with patch("app.auth_usermanagement.api.custom_ui_routes.get_settings", return_value=settings_mock), \
             patch("app.auth_usermanagement.api.custom_ui_routes.confirm_forgot_password_async", return_value={"error": "Password does not meet requirements"}):
            client = TestClient(app)
            resp = client.post("/custom/confirm-forgot-password", json={
                "email": "a@b.com", "code": "123456", "new_password": "ValidLen8!"
            })
            assert resp.status_code == 400

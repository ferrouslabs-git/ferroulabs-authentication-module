"""Unit tests for cognito_admin_service custom-UI auth flows.

Covers: initiate_auth, respond_to_new_password_challenge, sign_up_user,
confirm_sign_up, resend_confirmation_code, forgot_password,
confirm_forgot_password — plus error branches for admin_disable_user,
admin_enable_user, admin_get_user, admin_reset_user_password.
"""

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from app.auth_usermanagement.services.cognito_admin_service import (
    admin_disable_user,
    admin_enable_user,
    admin_get_user,
    admin_reset_user_password,
    confirm_forgot_password,
    confirm_sign_up,
    forgot_password,
    initiate_auth,
    resend_confirmation_code,
    respond_to_new_password_challenge,
    sign_up_user,
)


def _client_error(code: str, message: str = "error") -> ClientError:
    return ClientError(
        {"Error": {"Code": code, "Message": message}},
        "TestOp",
    )


# ── initiate_auth ────────────────────────────────────────────────


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_initiate_auth_success_tokens(mock_factory):
    client = MagicMock()
    mock_factory.return_value = client
    client.initiate_auth.return_value = {
        "AuthenticationResult": {
            "AccessToken": "at",
            "IdToken": "it",
            "RefreshToken": "rt",
            "ExpiresIn": 3600,
        }
    }

    result = initiate_auth("u@example.com", "pass123")

    assert result["authenticated"] is True
    assert result["access_token"] == "at"
    assert result["id_token"] == "it"
    assert result["refresh_token"] == "rt"
    assert result["expires_in"] == 3600


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_initiate_auth_challenge_response(mock_factory):
    client = MagicMock()
    mock_factory.return_value = client
    client.initiate_auth.return_value = {
        "ChallengeName": "NEW_PASSWORD_REQUIRED",
        "Session": "sess-123",
        "ChallengeParameters": {"USER_ID_FOR_SRP": "u@example.com"},
    }

    result = initiate_auth("u@example.com", "temp-pass")

    assert result["authenticated"] is False
    assert result["challenge"] == "NEW_PASSWORD_REQUIRED"
    assert result["session"] == "sess-123"


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_initiate_auth_unexpected_response(mock_factory):
    client = MagicMock()
    mock_factory.return_value = client
    client.initiate_auth.return_value = {"SomethingElse": True}

    result = initiate_auth("u@example.com", "pass")

    assert "error" in result
    assert "Unexpected" in result["error"]


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_initiate_auth_not_authorized(mock_factory):
    client = MagicMock()
    mock_factory.return_value = client
    client.initiate_auth.side_effect = _client_error("NotAuthorizedException")

    result = initiate_auth("u@example.com", "wrong")

    assert result["error"] == "Invalid email or password"


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_initiate_auth_user_not_found(mock_factory):
    client = MagicMock()
    mock_factory.return_value = client
    client.initiate_auth.side_effect = _client_error("UserNotFoundException")

    result = initiate_auth("ghost@example.com", "pass")

    assert result["error"] == "Invalid email or password"


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_initiate_auth_user_not_confirmed(mock_factory):
    client = MagicMock()
    mock_factory.return_value = client
    client.initiate_auth.side_effect = _client_error("UserNotConfirmedException")

    result = initiate_auth("u@example.com", "pass")

    assert "not confirmed" in result["error"].lower()


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_initiate_auth_password_reset_required(mock_factory):
    client = MagicMock()
    mock_factory.return_value = client
    client.initiate_auth.side_effect = _client_error("PasswordResetRequiredException")

    result = initiate_auth("u@example.com", "pass")

    assert "reset" in result["error"].lower()


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_initiate_auth_generic_error(mock_factory):
    client = MagicMock()
    mock_factory.return_value = client
    client.initiate_auth.side_effect = _client_error("InternalErrorException", "boom")

    result = initiate_auth("u@example.com", "pass")

    assert "error" in result
    assert "boom" in result["error"]


# ── respond_to_new_password_challenge ────────────────────────────


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_respond_challenge_success(mock_factory):
    client = MagicMock()
    mock_factory.return_value = client
    client.respond_to_auth_challenge.return_value = {
        "AuthenticationResult": {
            "AccessToken": "at2",
            "IdToken": "it2",
            "RefreshToken": "rt2",
            "ExpiresIn": 3600,
        }
    }

    result = respond_to_new_password_challenge("u@example.com", "newPass!", "sess")

    assert result["authenticated"] is True
    assert result["access_token"] == "at2"


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_respond_challenge_unexpected_response(mock_factory):
    client = MagicMock()
    mock_factory.return_value = client
    client.respond_to_auth_challenge.return_value = {"SomethingElse": True}

    result = respond_to_new_password_challenge("u@example.com", "p", "s")

    assert "error" in result


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_respond_challenge_invalid_password(mock_factory):
    client = MagicMock()
    mock_factory.return_value = client
    client.respond_to_auth_challenge.side_effect = _client_error("InvalidPasswordException", "too short")

    result = respond_to_new_password_challenge("u@example.com", "p", "s")

    assert "requirements" in result["error"].lower()


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_respond_challenge_code_mismatch(mock_factory):
    client = MagicMock()
    mock_factory.return_value = client
    client.respond_to_auth_challenge.side_effect = _client_error("CodeMismatchException")

    result = respond_to_new_password_challenge("u@example.com", "p", "s")

    assert "expired" in result["error"].lower()


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_respond_challenge_generic_error(mock_factory):
    client = MagicMock()
    mock_factory.return_value = client
    client.respond_to_auth_challenge.side_effect = _client_error("InternalErrorException", "oops")

    result = respond_to_new_password_challenge("u@example.com", "p", "s")

    assert "error" in result


# ── sign_up_user ─────────────────────────────────────────────────


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_sign_up_user_success(mock_factory):
    client = MagicMock()
    mock_factory.return_value = client
    client.sign_up.return_value = {
        "UserSub": "sub-123",
        "UserConfirmed": False,
        "CodeDeliveryDetails": {"Destination": "u***@example.com"},
    }

    result = sign_up_user("u@example.com", "P@ssw0rd!")

    assert result["user_sub"] == "sub-123"
    assert result["confirmed"] is False


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_sign_up_user_exists(mock_factory):
    client = MagicMock()
    mock_factory.return_value = client
    client.sign_up.side_effect = _client_error("UsernameExistsException")

    result = sign_up_user("dup@example.com", "P@ss")

    assert "already exists" in result["error"]


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_sign_up_invalid_password(mock_factory):
    client = MagicMock()
    mock_factory.return_value = client
    client.sign_up.side_effect = _client_error("InvalidPasswordException", "too short")

    result = sign_up_user("u@example.com", "x")

    assert "requirements" in result["error"].lower()


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_sign_up_invalid_parameter(mock_factory):
    client = MagicMock()
    mock_factory.return_value = client
    client.sign_up.side_effect = _client_error("InvalidParameterException", "bad email")

    result = sign_up_user("bad", "P@ss")

    assert "Invalid input" in result["error"]


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_sign_up_generic_error(mock_factory):
    client = MagicMock()
    mock_factory.return_value = client
    client.sign_up.side_effect = _client_error("ServiceUnavailable", "down")

    result = sign_up_user("u@example.com", "P@ss")

    assert "error" in result


# ── confirm_sign_up ──────────────────────────────────────────────


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_confirm_sign_up_success(mock_factory):
    client = MagicMock()
    mock_factory.return_value = client

    result = confirm_sign_up("u@example.com", "123456")

    assert result["confirmed"] is True


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_confirm_sign_up_code_mismatch(mock_factory):
    client = MagicMock()
    mock_factory.return_value = client
    client.confirm_sign_up.side_effect = _client_error("CodeMismatchException")

    result = confirm_sign_up("u@example.com", "000000")

    assert "Invalid" in result["error"]


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_confirm_sign_up_expired_code(mock_factory):
    client = MagicMock()
    mock_factory.return_value = client
    client.confirm_sign_up.side_effect = _client_error("ExpiredCodeException")

    result = confirm_sign_up("u@example.com", "111111")

    assert "expired" in result["error"].lower()


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_confirm_sign_up_alias_exists(mock_factory):
    client = MagicMock()
    mock_factory.return_value = client
    client.confirm_sign_up.side_effect = _client_error("AliasExistsException")

    result = confirm_sign_up("u@example.com", "123456")

    assert "another account" in result["error"].lower()


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_confirm_sign_up_generic_error(mock_factory):
    client = MagicMock()
    mock_factory.return_value = client
    client.confirm_sign_up.side_effect = _client_error("InternalError", "fail")

    result = confirm_sign_up("u@example.com", "123456")

    assert "error" in result


# ── resend_confirmation_code ─────────────────────────────────────


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_resend_code_success(mock_factory):
    client = MagicMock()
    mock_factory.return_value = client
    client.resend_confirmation_code.return_value = {
        "CodeDeliveryDetails": {"Destination": "u***@example.com"}
    }

    result = resend_confirmation_code("u@example.com")

    assert result["sent"] is True


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_resend_code_generic_error(mock_factory):
    client = MagicMock()
    mock_factory.return_value = client
    client.resend_confirmation_code.side_effect = _client_error("TooManyRequestsException", "slow down")

    result = resend_confirmation_code("u@example.com")

    assert "error" in result


# ── forgot_password ──────────────────────────────────────────────


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_forgot_password_success(mock_factory):
    client = MagicMock()
    mock_factory.return_value = client
    client.forgot_password.return_value = {
        "CodeDeliveryDetails": {"Destination": "u***@example.com"}
    }

    result = forgot_password("u@example.com")

    assert result["sent"] is True


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_forgot_password_user_not_found_hides_existence(mock_factory):
    client = MagicMock()
    mock_factory.return_value = client
    client.forgot_password.side_effect = _client_error("UserNotFoundException")

    result = forgot_password("ghost@example.com")

    # Should NOT reveal that the user doesn't exist
    assert result["sent"] is True


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_forgot_password_limit_exceeded(mock_factory):
    client = MagicMock()
    mock_factory.return_value = client
    client.forgot_password.side_effect = _client_error("LimitExceededException")

    result = forgot_password("u@example.com")

    assert "Too many" in result["error"]


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_forgot_password_invalid_parameter(mock_factory):
    client = MagicMock()
    mock_factory.return_value = client
    client.forgot_password.side_effect = _client_error("InvalidParameterException")

    result = forgot_password("u@example.com")

    assert "contact support" in result["error"].lower()


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_forgot_password_generic_error(mock_factory):
    client = MagicMock()
    mock_factory.return_value = client
    client.forgot_password.side_effect = _client_error("ServiceUnavailable", "down")

    result = forgot_password("u@example.com")

    assert "error" in result


# ── confirm_forgot_password ──────────────────────────────────────


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_confirm_forgot_password_success(mock_factory):
    client = MagicMock()
    mock_factory.return_value = client

    result = confirm_forgot_password("u@example.com", "123456", "NewP@ss1!")

    assert result["confirmed"] is True


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_confirm_forgot_password_code_mismatch(mock_factory):
    client = MagicMock()
    mock_factory.return_value = client
    client.confirm_forgot_password.side_effect = _client_error("CodeMismatchException")

    result = confirm_forgot_password("u@example.com", "000000", "P@ss")

    assert "Invalid" in result["error"]


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_confirm_forgot_password_expired_code(mock_factory):
    client = MagicMock()
    mock_factory.return_value = client
    client.confirm_forgot_password.side_effect = _client_error("ExpiredCodeException")

    result = confirm_forgot_password("u@example.com", "111111", "P@ss")

    assert "expired" in result["error"].lower()


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_confirm_forgot_password_invalid_password(mock_factory):
    client = MagicMock()
    mock_factory.return_value = client
    client.confirm_forgot_password.side_effect = _client_error("InvalidPasswordException", "too short")

    result = confirm_forgot_password("u@example.com", "123456", "x")

    assert "requirements" in result["error"].lower()


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_confirm_forgot_password_generic_error(mock_factory):
    client = MagicMock()
    mock_factory.return_value = client
    client.confirm_forgot_password.side_effect = _client_error("InternalError", "boom")

    result = confirm_forgot_password("u@example.com", "123456", "P@ss")

    assert "error" in result


# ── admin error branches ─────────────────────────────────────────


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_admin_disable_user_not_found(mock_factory):
    client = MagicMock()
    mock_factory.return_value = client
    client.admin_disable_user.side_effect = _client_error("UserNotFoundException")

    result = admin_disable_user("ghost@example.com")

    assert "not found" in result["error"].lower()


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_admin_disable_user_generic_error(mock_factory):
    client = MagicMock()
    mock_factory.return_value = client
    client.admin_disable_user.side_effect = _client_error("InternalError", "kaboom")

    result = admin_disable_user("u@example.com")

    assert "error" in result


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_admin_enable_user_not_found(mock_factory):
    client = MagicMock()
    mock_factory.return_value = client
    client.admin_enable_user.side_effect = _client_error("UserNotFoundException")

    result = admin_enable_user("ghost@example.com")

    assert "not found" in result["error"].lower()


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_admin_enable_user_generic_error(mock_factory):
    client = MagicMock()
    mock_factory.return_value = client
    client.admin_enable_user.side_effect = _client_error("InternalError", "nope")

    result = admin_enable_user("u@example.com")

    assert "error" in result


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_admin_get_user_generic_error(mock_factory):
    client = MagicMock()
    mock_factory.return_value = client
    client.admin_get_user.side_effect = _client_error("InternalError", "fail")

    result = admin_get_user("u@example.com")

    assert "error" in result


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_admin_reset_password_not_found(mock_factory):
    client = MagicMock()
    mock_factory.return_value = client
    client.admin_reset_user_password.side_effect = _client_error("UserNotFoundException")

    result = admin_reset_user_password("ghost@example.com")

    assert "not found" in result["error"].lower()


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_admin_reset_password_invalid_parameter(mock_factory):
    client = MagicMock()
    mock_factory.return_value = client
    client.admin_reset_user_password.side_effect = _client_error("InvalidParameterException")

    result = admin_reset_user_password("u@example.com")

    assert "Cannot reset" in result["error"]


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_admin_reset_password_generic_error(mock_factory):
    client = MagicMock()
    mock_factory.return_value = client
    client.admin_reset_user_password.side_effect = _client_error("InternalError", "nope")

    result = admin_reset_user_password("u@example.com")

    assert "error" in result

"""
Cognito admin operations for custom_ui auth mode.

Uses boto3 AdminCreateUser / AdminSetUserPassword to pre-provision
invited users in FORCE_CHANGE_PASSWORD state, so the frontend can
present a "set password" form instead of the full Hosted UI signup.

This service is ONLY called when AUTH_MODE=custom_ui.
No new DB runtime objects — follows host integration contract.
"""
from __future__ import annotations

import logging
import secrets
import string

import boto3
from botocore.exceptions import ClientError

from ..config import get_settings

logger = logging.getLogger(__name__)


def _generate_temp_password(length: int = 24) -> str:
    """Generate a cryptographically random temporary password.

    Meets Cognito default password policy (upper, lower, digit, special).
    """
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in "!@#$%^&*()-_=+" for c in password)
        if has_upper and has_lower and has_digit and has_special:
            return password


def _get_cognito_client():
    settings = get_settings()
    return boto3.client("cognito-idp", region_name=settings.cognito_region)


def create_invited_cognito_user(email: str) -> dict:
    """Pre-create a Cognito user for an invited email address.

    The user is created with MessageAction=SUPPRESS (Cognito does NOT
    send its own welcome email — our invitation email handles that)
    and a temporary password.  The user lands in FORCE_CHANGE_PASSWORD
    state so the frontend can present a "set your password" form.

    Returns dict with 'cognito_sub' and 'status' on success, or
    'error' key on failure.

    If the user already exists in Cognito the function is idempotent:
    it resets the user to FORCE_CHANGE_PASSWORD so the invite flow
    still works.
    """
    settings = get_settings()
    client = _get_cognito_client()
    temp_password = _generate_temp_password()

    try:
        response = client.admin_create_user(
            UserPoolId=settings.cognito_user_pool_id,
            Username=email,
            UserAttributes=[
                {"Name": "email", "Value": email},
                {"Name": "email_verified", "Value": "true"},
            ],
            TemporaryPassword=temp_password,
            MessageAction="SUPPRESS",  # We send our own email
            DesiredDeliveryMediums=["EMAIL"],
        )
        cognito_sub = None
        for attr in response.get("User", {}).get("Attributes", []):
            if attr["Name"] == "sub":
                cognito_sub = attr["Value"]

        logger.info(
            "Created Cognito user for invitation",
            extra={"email": email, "cognito_sub": cognito_sub},
        )
        return {
            "cognito_sub": cognito_sub,
            "temp_password": temp_password,
            "status": "FORCE_CHANGE_PASSWORD",
        }

    except ClientError as e:
        error_code = e.response["Error"]["Code"]

        if error_code == "UsernameExistsException":
            # User already exists — reset to FORCE_CHANGE_PASSWORD
            try:
                client.admin_set_user_password(
                    UserPoolId=settings.cognito_user_pool_id,
                    Username=email,
                    Password=temp_password,
                    Permanent=False,  # Temporary = FORCE_CHANGE_PASSWORD
                )
                logger.info(
                    "Reset existing Cognito user to FORCE_CHANGE_PASSWORD",
                    extra={"email": email},
                )
                return {
                    "cognito_sub": None,
                    "temp_password": temp_password,
                    "status": "FORCE_CHANGE_PASSWORD",
                }
            except ClientError as reset_err:
                logger.error(
                    "Failed to reset Cognito user password",
                    extra={"email": email, "error": str(reset_err)},
                )
                return {"error": f"Cognito reset failed: {reset_err.response['Error']['Message']}"}

        logger.error(
            "Cognito AdminCreateUser failed",
            extra={"email": email, "error_code": error_code, "error": str(e)},
        )
        return {"error": f"Cognito error: {e.response['Error']['Message']}"}


def initiate_auth(email: str, password: str) -> dict:
    """Authenticate a user via USER_PASSWORD_AUTH flow.

    Returns Cognito tokens on success, or challenge details if
    NEW_PASSWORD_REQUIRED (invited user first login).
    """
    settings = get_settings()
    client = _get_cognito_client()

    try:
        response = client.initiate_auth(
            ClientId=settings.cognito_client_id,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={
                "USERNAME": email,
                "PASSWORD": password,
            },
        )

        # Successful auth — return tokens
        if "AuthenticationResult" in response:
            result = response["AuthenticationResult"]
            return {
                "authenticated": True,
                "access_token": result["AccessToken"],
                "id_token": result["IdToken"],
                "refresh_token": result.get("RefreshToken"),
                "expires_in": result.get("ExpiresIn", 3600),
            }

        # Challenge response (e.g. NEW_PASSWORD_REQUIRED for invited users)
        if "ChallengeName" in response:
            return {
                "authenticated": False,
                "challenge": response["ChallengeName"],
                "session": response["Session"],
                "challenge_parameters": response.get("ChallengeParameters", {}),
            }

        return {"error": "Unexpected Cognito response"}

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_msg = e.response["Error"]["Message"]

        if error_code == "NotAuthorizedException":
            return {"error": "Invalid email or password"}
        if error_code == "UserNotFoundException":
            return {"error": "Invalid email or password"}
        if error_code == "UserNotConfirmedException":
            return {"error": "Account not confirmed. Please check your email."}
        if error_code == "PasswordResetRequiredException":
            return {"error": "Password reset required"}

        logger.error("Cognito InitiateAuth failed", extra={"error_code": error_code, "error": error_msg})
        return {"error": f"Authentication failed: {error_msg}"}


def respond_to_new_password_challenge(email: str, new_password: str, session: str) -> dict:
    """Complete the NEW_PASSWORD_REQUIRED challenge for invited users.

    Called after initiate_auth returns challenge='NEW_PASSWORD_REQUIRED'.
    The user provides their chosen password and the Cognito session token.
    """
    settings = get_settings()
    client = _get_cognito_client()

    try:
        response = client.respond_to_auth_challenge(
            ClientId=settings.cognito_client_id,
            ChallengeName="NEW_PASSWORD_REQUIRED",
            Session=session,
            ChallengeResponses={
                "USERNAME": email,
                "NEW_PASSWORD": new_password,
            },
        )

        if "AuthenticationResult" in response:
            result = response["AuthenticationResult"]
            return {
                "authenticated": True,
                "access_token": result["AccessToken"],
                "id_token": result["IdToken"],
                "refresh_token": result.get("RefreshToken"),
                "expires_in": result.get("ExpiresIn", 3600),
            }

        return {"error": "Unexpected response from Cognito"}

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_msg = e.response["Error"]["Message"]

        if error_code == "InvalidPasswordException":
            return {"error": f"Password does not meet requirements: {error_msg}"}
        if error_code == "CodeMismatchException":
            return {"error": "Session expired. Please restart the sign-in process."}

        logger.error(
            "Cognito RespondToAuthChallenge failed",
            extra={"error_code": error_code, "error": error_msg},
        )
        return {"error": f"Password setup failed: {error_msg}"}


def sign_up_user(email: str, password: str) -> dict:
    """Self-service user signup via Cognito SignUp API.

    Used in custom_ui mode instead of the Hosted UI signup page.
    Returns confirmation status — user may need to verify email.
    """
    settings = get_settings()
    client = _get_cognito_client()

    try:
        response = client.sign_up(
            ClientId=settings.cognito_client_id,
            Username=email,
            Password=password,
            UserAttributes=[
                {"Name": "email", "Value": email},
            ],
        )

        return {
            "user_sub": response["UserSub"],
            "confirmed": response["UserConfirmed"],
            "delivery": response.get("CodeDeliveryDetails", {}),
        }

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_msg = e.response["Error"]["Message"]

        if error_code == "UsernameExistsException":
            return {"error": "An account with this email already exists"}
        if error_code == "InvalidPasswordException":
            return {"error": f"Password does not meet requirements: {error_msg}"}
        if error_code == "InvalidParameterException":
            return {"error": f"Invalid input: {error_msg}"}

        logger.error("Cognito SignUp failed", extra={"error_code": error_code, "error": error_msg})
        return {"error": f"Signup failed: {error_msg}"}


def confirm_sign_up(email: str, confirmation_code: str) -> dict:
    """Confirm a user's email after self-service signup."""
    settings = get_settings()
    client = _get_cognito_client()

    try:
        client.confirm_sign_up(
            ClientId=settings.cognito_client_id,
            Username=email,
            ConfirmationCode=confirmation_code,
        )
        return {"confirmed": True}

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_msg = e.response["Error"]["Message"]

        if error_code == "CodeMismatchException":
            return {"error": "Invalid confirmation code"}
        if error_code == "ExpiredCodeException":
            return {"error": "Confirmation code has expired. Please request a new one."}
        if error_code == "AliasExistsException":
            return {"error": "This email is already confirmed with another account"}

        logger.error("Cognito ConfirmSignUp failed", extra={"error_code": error_code, "error": error_msg})
        return {"error": f"Confirmation failed: {error_msg}"}


def resend_confirmation_code(email: str) -> dict:
    """Resend the email confirmation code for an unconfirmed user."""
    settings = get_settings()
    client = _get_cognito_client()

    try:
        response = client.resend_confirmation_code(
            ClientId=settings.cognito_client_id,
            Username=email,
        )
        return {"sent": True, "delivery": response.get("CodeDeliveryDetails", {})}

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_msg = e.response["Error"]["Message"]
        logger.error("Cognito ResendCode failed", extra={"error_code": error_code, "error": error_msg})
        return {"error": f"Failed to resend code: {error_msg}"}


def forgot_password(email: str) -> dict:
    """Initiate the forgot-password flow — Cognito sends a reset code to the user's email."""
    settings = get_settings()
    client = _get_cognito_client()

    try:
        response = client.forgot_password(
            ClientId=settings.cognito_client_id,
            Username=email,
        )
        return {"sent": True, "delivery": response.get("CodeDeliveryDetails", {})}

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_msg = e.response["Error"]["Message"]

        if error_code == "UserNotFoundException":
            # Don't reveal whether the email exists
            return {"sent": True, "delivery": {}}
        if error_code == "LimitExceededException":
            return {"error": "Too many attempts. Please try again later."}
        if error_code == "InvalidParameterException":
            return {"error": "Cannot reset password for this account. Please contact support."}

        logger.error("Cognito ForgotPassword failed", extra={"error_code": error_code, "error": error_msg})
        return {"error": f"Password reset failed: {error_msg}"}


def confirm_forgot_password(email: str, code: str, new_password: str) -> dict:
    """Complete the forgot-password flow with the reset code and a new password."""
    settings = get_settings()
    client = _get_cognito_client()

    try:
        client.confirm_forgot_password(
            ClientId=settings.cognito_client_id,
            Username=email,
            ConfirmationCode=code,
            Password=new_password,
        )
        return {"confirmed": True}

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_msg = e.response["Error"]["Message"]

        if error_code == "CodeMismatchException":
            return {"error": "Invalid reset code"}
        if error_code == "ExpiredCodeException":
            return {"error": "Reset code has expired. Please request a new one."}
        if error_code == "InvalidPasswordException":
            return {"error": f"Password does not meet requirements: {error_msg}"}

        logger.error("Cognito ConfirmForgotPassword failed", extra={"error_code": error_code, "error": error_msg})
        return {"error": f"Password reset failed: {error_msg}"}

"""Unit tests for cookie_token_service helpers."""
import json
import unittest.mock as mock
import urllib.error
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from fastapi import Response

from app.auth_usermanagement.services.cookie_token_service import (
    COOKIE_MAX_AGE,
    DEFAULT_COOKIE_NAME,
    DEFAULT_COOKIE_PATH,
    call_cognito_refresh,
    clear_refresh_cookie,
    set_refresh_cookie,
)


# ---------------------------------------------------------------------------
# set_refresh_cookie
# ---------------------------------------------------------------------------

def test_set_refresh_cookie_attributes():
    response = Response()
    set_refresh_cookie(response, "my-refresh-token")

    raw = response.headers.get("set-cookie", "")
    assert DEFAULT_COOKIE_NAME in raw
    assert "my-refresh-token" in raw
    assert "HttpOnly" in raw
    assert "SameSite=strict" in raw.lower() or "samesite=strict" in raw.lower()
    assert f"Path={DEFAULT_COOKIE_PATH}" in raw
    assert f"Max-Age={COOKIE_MAX_AGE}" in raw


# ---------------------------------------------------------------------------
# clear_refresh_cookie
# ---------------------------------------------------------------------------

def test_clear_refresh_cookie_zeroes_max_age():
    response = Response()
    clear_refresh_cookie(response)

    raw = response.headers.get("set-cookie", "")
    assert DEFAULT_COOKIE_NAME in raw
    assert "Max-Age=0" in raw


# ---------------------------------------------------------------------------
# call_cognito_refresh — success
# ---------------------------------------------------------------------------

def _make_urlopen_cm(body: dict):
    """Return a context-manager mock that yields a response with the given body."""
    encoded = json.dumps(body).encode("utf-8")
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=encoded)))
    cm.__exit__ = MagicMock(return_value=False)
    return cm


def test_call_cognito_refresh_parses_success_response():
    success_body = {
        "access_token": "new-access",
        "id_token": "new-id",
        "expires_in": 3600,
    }
    with patch("urllib.request.urlopen", return_value=_make_urlopen_cm(success_body)):
        result = call_cognito_refresh(
            refresh_token="old-refresh",
            cognito_domain="https://auth.example.com",
            client_id="client123",
        )

    assert result["access_token"] == "new-access"
    assert result["id_token"] == "new-id"
    assert result["expires_in"] == 3600


# ---------------------------------------------------------------------------
# call_cognito_refresh — Cognito error in HTTP 400 body
# ---------------------------------------------------------------------------

def test_call_cognito_refresh_raises_on_http_error():
    error_body = json.dumps({"error": "invalid_grant", "error_description": "Refresh token expired"}).encode()
    exc = urllib.error.HTTPError(
        url="https://auth.example.com/oauth2/token",
        code=400,
        msg="Bad Request",
        hdrs=None,
        fp=BytesIO(error_body),
    )
    with patch("urllib.request.urlopen", side_effect=exc):
        with pytest.raises(ValueError, match="Refresh token expired"):
            call_cognito_refresh(
                refresh_token="bad-token",
                cognito_domain="https://auth.example.com",
                client_id="client123",
            )


# ---------------------------------------------------------------------------
# call_cognito_refresh — Cognito returns error key in 200 body
# ---------------------------------------------------------------------------

def test_call_cognito_refresh_raises_on_error_in_body():
    error_body = {"error": "invalid_grant", "error_description": "Token has been revoked"}
    with patch("urllib.request.urlopen", return_value=_make_urlopen_cm(error_body)):
        with pytest.raises(ValueError, match="Token has been revoked"):
            call_cognito_refresh(
                refresh_token="revoked",
                cognito_domain="https://auth.example.com",
                client_id="client123",
            )

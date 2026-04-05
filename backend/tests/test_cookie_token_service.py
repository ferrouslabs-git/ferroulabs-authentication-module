"""Unit tests for cookie_token_service helpers."""
import json
import unittest.mock as mock
from unittest.mock import MagicMock, patch, AsyncMock

import httpx
import pytest
import pytest_asyncio
from fastapi import Response

from app.auth_usermanagement.services.cookie_token_service import (
    COOKIE_MAX_AGE,
    DEFAULT_COOKIE_NAME,
    DEFAULT_COOKIE_PATH,
    call_cognito_refresh_async,
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
# call_cognito_refresh_async — success
# ---------------------------------------------------------------------------

def _make_httpx_response(body: dict, status_code: int = 200):
    """Return a mock httpx.Response with the given body."""
    return httpx.Response(status_code=status_code, json=body)


@pytest.mark.asyncio
async def test_call_cognito_refresh_async_parses_success_response():
    success_body = {
        "access_token": "new-access",
        "id_token": "new-id",
        "expires_in": 3600,
    }
    mock_response = _make_httpx_response(success_body)
    with patch("app.auth_usermanagement.services.cookie_token_service.httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.post.return_value = mock_response
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        result = await call_cognito_refresh_async(
            refresh_token="old-refresh",
            cognito_domain="https://auth.example.com",
            client_id="client123",
        )

    assert result["access_token"] == "new-access"
    assert result["id_token"] == "new-id"
    assert result["expires_in"] == 3600


# ---------------------------------------------------------------------------
# call_cognito_refresh_async — Cognito error in HTTP 400 body
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_call_cognito_refresh_async_raises_on_http_error():
    error_body = {"error": "invalid_grant", "error_description": "Refresh token expired"}
    mock_response = _make_httpx_response(error_body, status_code=400)
    with patch("app.auth_usermanagement.services.cookie_token_service.httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.post.return_value = mock_response
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        with pytest.raises(ValueError, match="Refresh token expired"):
            await call_cognito_refresh_async(
                refresh_token="bad-token",
                cognito_domain="https://auth.example.com",
                client_id="client123",
            )


# ---------------------------------------------------------------------------
# call_cognito_refresh_async — Cognito returns error key in 200 body
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_call_cognito_refresh_async_raises_on_error_in_body():
    error_body = {"error": "invalid_grant", "error_description": "Token has been revoked"}
    mock_response = _make_httpx_response(error_body, status_code=200)
    with patch("app.auth_usermanagement.services.cookie_token_service.httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.post.return_value = mock_response
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        with pytest.raises(ValueError, match="Token has been revoked"):
            await call_cognito_refresh_async(
                refresh_token="revoked",
                cognito_domain="https://auth.example.com",
                client_id="client123",
            )

"""
Cookie-based refresh token service.

Handles setting/clearing the HttpOnly refresh token cookie and proxying
token refresh requests to Cognito on behalf of the frontend.

Security properties of the cookie:
- HttpOnly: JS cannot read it
- Secure: HTTPS only (enforced by browser in production)
- SameSite=Strict: blocks cross-site cookie sending entirely
- Path=/auth/token: scoped to the refresh endpoint only, not sent on every request
"""
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, UTC
from threading import Lock
import secrets

from fastapi import Response

COOKIE_NAME = "trustos_refresh_token"
COOKIE_MAX_AGE = 30 * 24 * 60 * 60  # 30 days in seconds


_refresh_store_lock = Lock()
_refresh_store: dict[str, tuple[str, datetime]] = {}


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _purge_expired_tokens() -> None:
    now = _utc_now()
    expired_keys = [key for key, (_token, expires_at) in _refresh_store.items() if expires_at <= now]
    for key in expired_keys:
        _refresh_store.pop(key, None)


def store_refresh_token(refresh_token: str) -> str:
    """Store refresh token server-side and return a short opaque cookie key."""
    key = secrets.token_urlsafe(32)
    expires_at = _utc_now() + timedelta(seconds=COOKIE_MAX_AGE)
    with _refresh_store_lock:
        _purge_expired_tokens()
        _refresh_store[key] = (refresh_token, expires_at)
    return key


def get_refresh_token(cookie_key: str) -> str | None:
    """Resolve an opaque cookie key to a live refresh token."""
    if not cookie_key:
        return None
    with _refresh_store_lock:
        _purge_expired_tokens()
        row = _refresh_store.get(cookie_key)
        if not row:
            return None
        return row[0]


def rotate_refresh_token(cookie_key: str, new_refresh_token: str) -> str:
    """Rotate stored refresh token and return a new cookie key."""
    new_key = store_refresh_token(new_refresh_token)
    with _refresh_store_lock:
        _refresh_store.pop(cookie_key, None)
    return new_key


def revoke_refresh_token(cookie_key: str) -> None:
    """Revoke an opaque cookie key from the server-side refresh store."""
    if not cookie_key:
        return
    with _refresh_store_lock:
        _refresh_store.pop(cookie_key, None)


def set_refresh_cookie(response: Response, cookie_key: str, secure: bool = True) -> None:
    """Attach an HttpOnly opaque refresh-key cookie to a FastAPI response."""
    response.set_cookie(
        key=COOKIE_NAME,
        value=cookie_key,
        httponly=True,
        secure=secure,
        samesite="strict",
        path="/auth/token",
        max_age=COOKIE_MAX_AGE,
    )


def clear_refresh_cookie(response: Response, secure: bool = True) -> None:
    """Expire the refresh-token cookie by setting max_age=0."""
    response.set_cookie(
        key=COOKIE_NAME,
        value="",
        httponly=True,
        secure=secure,
        samesite="strict",
        path="/auth/token",
        max_age=0,
    )


def call_cognito_refresh(refresh_token: str, cognito_domain: str, client_id: str) -> dict:
    """
    Exchange a refresh token for new tokens by calling the Cognito token endpoint.

    Returns the parsed JSON response dict on success.
    Raises ValueError if Cognito returns an error.
    """
    url = f"{cognito_domain}/oauth2/token"
    data = urllib.parse.urlencode(
        {
            "grant_type": "refresh_token",
            "client_id": client_id,
            "refresh_token": refresh_token,
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    import json

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            err = json.loads(body)
        except Exception:
            err = {"error": body}
        raise ValueError(err.get("error_description") or err.get("error") or "Cognito token refresh failed") from exc

    if "error" in result:
        raise ValueError(result.get("error_description") or result.get("error") or "Cognito token refresh failed")

    return result

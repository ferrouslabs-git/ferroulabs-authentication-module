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
import json
from datetime import datetime, timedelta, UTC
import secrets

import httpx
from fastapi import Response
from sqlalchemy.orm import Session

from ..models.refresh_token import RefreshTokenStore

DEFAULT_COOKIE_NAME = "authum_refresh_token"
DEFAULT_CSRF_COOKIE_NAME = "authum_csrf_token"
DEFAULT_COOKIE_PATH = "/auth/token"
COOKIE_MAX_AGE = 30 * 24 * 60 * 60  # 30 days in seconds


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _purge_expired_tokens(db: Session) -> None:
    now = _utc_now()
    db.query(RefreshTokenStore).filter(RefreshTokenStore.expires_at <= now).delete(synchronize_session=False)


def store_refresh_token(db: Session, refresh_token: str) -> str:
    """Store refresh token server-side and return a short opaque cookie key."""
    key = secrets.token_urlsafe(32)
    expires_at = _utc_now() + timedelta(seconds=COOKIE_MAX_AGE)
    _purge_expired_tokens(db)
    db.add(
        RefreshTokenStore(
            cookie_key=key,
            refresh_token=refresh_token,
            expires_at=expires_at,
        )
    )
    db.commit()
    return key


def get_refresh_token(db: Session, cookie_key: str) -> str | None:
    """Resolve an opaque cookie key to a live refresh token."""
    if not cookie_key:
        return None
    _purge_expired_tokens(db)
    row = db.query(RefreshTokenStore).filter(RefreshTokenStore.cookie_key == cookie_key).first()
    if not row:
        return None
    return row.refresh_token


def rotate_refresh_token(db: Session, cookie_key: str, new_refresh_token: str) -> str:
    """Rotate stored refresh token and return a new cookie key."""
    new_key = store_refresh_token(db, new_refresh_token)
    db.query(RefreshTokenStore).filter(RefreshTokenStore.cookie_key == cookie_key).delete(synchronize_session=False)
    db.commit()
    return new_key


def revoke_refresh_token(db: Session, cookie_key: str) -> None:
    """Revoke an opaque cookie key from the server-side refresh store."""
    if not cookie_key:
        return
    db.query(RefreshTokenStore).filter(RefreshTokenStore.cookie_key == cookie_key).delete(synchronize_session=False)
    db.commit()


def set_refresh_cookie(
    response: Response,
    cookie_key: str,
    *,
    secure: bool = True,
    cookie_name: str = DEFAULT_COOKIE_NAME,
    cookie_path: str = DEFAULT_COOKIE_PATH,
) -> None:
    """Attach an HttpOnly opaque refresh-key cookie to a FastAPI response."""
    response.set_cookie(
        key=cookie_name,
        value=cookie_key,
        httponly=True,
        secure=secure,
        samesite="strict",
        path=cookie_path,
        max_age=COOKIE_MAX_AGE,
    )


def clear_refresh_cookie(
    response: Response,
    *,
    secure: bool = True,
    cookie_name: str = DEFAULT_COOKIE_NAME,
    cookie_path: str = DEFAULT_COOKIE_PATH,
) -> None:
    """Expire the refresh-token cookie by setting max_age=0."""
    response.set_cookie(
        key=cookie_name,
        value="",
        httponly=True,
        secure=secure,
        samesite="strict",
        path=cookie_path,
        max_age=0,
    )


def generate_csrf_token() -> str:
    """Return a cryptographically random CSRF token."""
    return secrets.token_urlsafe(32)


def set_csrf_cookie(
    response: Response,
    csrf_token: str,
    *,
    secure: bool = True,
    csrf_cookie_name: str = DEFAULT_CSRF_COOKIE_NAME,
    cookie_path: str = DEFAULT_COOKIE_PATH,
) -> None:
    """Attach a readable (non-HttpOnly) CSRF token cookie to a FastAPI response."""
    response.set_cookie(
        key=csrf_cookie_name,
        value=csrf_token,
        httponly=False,  # JS must be able to read this cookie
        secure=secure,
        samesite="strict",
        path=cookie_path,
        max_age=COOKIE_MAX_AGE,
    )


def clear_csrf_cookie(
    response: Response,
    *,
    secure: bool = True,
    csrf_cookie_name: str = DEFAULT_CSRF_COOKIE_NAME,
    cookie_path: str = DEFAULT_COOKIE_PATH,
) -> None:
    """Expire the CSRF token cookie."""
    response.set_cookie(
        key=csrf_cookie_name,
        value="",
        httponly=False,
        secure=secure,
        samesite="strict",
        path=cookie_path,
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


async def call_cognito_refresh_async(
    refresh_token: str, cognito_domain: str, client_id: str,
) -> dict:
    """Async version — exchange refresh token via httpx.AsyncClient.

    Returns the parsed JSON response dict on success.
    Raises ValueError if Cognito returns an error.
    """
    url = f"{cognito_domain}/oauth2/token"
    data = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "refresh_token": refresh_token,
    }

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10,
            )
        except httpx.HTTPError as exc:
            raise ValueError(f"Cognito token refresh request failed: {exc}") from exc

    if resp.status_code >= 400:
        try:
            err = resp.json()
        except Exception:
            err = {"error": resp.text}
        raise ValueError(
            err.get("error_description") or err.get("error") or "Cognito token refresh failed"
        )

    result = resp.json()
    if "error" in result:
        raise ValueError(
            result.get("error_description") or result.get("error") or "Cognito token refresh failed"
        )

    return result

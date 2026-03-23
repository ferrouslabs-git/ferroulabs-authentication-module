"""
JWT Token Verification for AWS Cognito
Downloads JWKS and validates token signatures
"""
import logging
import threading
import time
from typing import Dict

import requests
from jose import jwt, JWTError
from fastapi import HTTPException, status
from pydantic import ValidationError

from ..config import get_settings
from ..schemas.token import TokenPayload

logger = logging.getLogger(__name__)

JWKS_TTL_SECONDS = 3600  # Re-fetch JWKS every hour


class InvalidTokenError(HTTPException):
    """Custom exception for invalid tokens"""
    def __init__(self, detail: str = "Invalid or expired token"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"}
        )


class _JWKSCache:
    """Thread-safe JWKS cache with TTL.

    Fetches synchronously — safe because it only runs at startup or
    once per TTL window (background threads never block the async loop
    for more than ~1 request; subsequent requests use the cached value).
    """

    def __init__(self, ttl: int = JWKS_TTL_SECONDS):
        self._lock = threading.Lock()
        self._jwks: Dict | None = None
        self._fetched_at: float = 0.0
        self._ttl = ttl

    def _is_stale(self) -> bool:
        return self._jwks is None or (time.monotonic() - self._fetched_at) >= self._ttl

    def _fetch(self) -> Dict:
        settings = get_settings()
        jwks_url = (
            f"https://cognito-idp.{settings.cognito_region}.amazonaws.com/"
            f"{settings.cognito_user_pool_id}/.well-known/jwks.json"
        )
        response = requests.get(jwks_url, timeout=10)
        response.raise_for_status()
        return response.json()

    def get(self) -> Dict:
        if not self._is_stale():
            return self._jwks  # type: ignore[return-value]

        with self._lock:
            # Double-check after acquiring lock
            if not self._is_stale():
                return self._jwks  # type: ignore[return-value]
            try:
                self._jwks = self._fetch()
                self._fetched_at = time.monotonic()
                logger.info("JWKS fetched/refreshed successfully")
            except requests.RequestException as e:
                if self._jwks is not None:
                    logger.warning("JWKS refresh failed, using cached copy: %s", e)
                    return self._jwks
                raise InvalidTokenError(f"Failed to fetch JWKS: {str(e)}")
        return self._jwks  # type: ignore[return-value]

    def invalidate(self) -> None:
        """Force next call to re-fetch (e.g. when a kid is not found)."""
        with self._lock:
            self._fetched_at = 0.0


_jwks_cache = _JWKSCache()


def get_jwks() -> Dict:
    """Return cached Cognito JWKS, refreshing when the TTL expires."""
    return _jwks_cache.get()


def verify_token(token: str, allowed_token_uses: tuple[str, ...] = ("access",)) -> TokenPayload:
    """
    Verify Cognito JWT token and return payload
    
    Args:
        token: JWT token string (from Authorization header)
    
    Returns:
        TokenPayload: Validated token claims
    
    Raises:
        InvalidTokenError: If token is invalid, expired, or signature verification fails
    """
    settings = get_settings()
    
    try:
        # Get JWKS (cached)
        jwks = get_jwks()
        
        # Decode token header to get kid (key ID)
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        
        if not kid:
            raise InvalidTokenError("Token missing 'kid' in header")
        
        # Find matching key in JWKS
        matching_key = None
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                matching_key = key
                break
        
        if not matching_key:
            # Key rotation: invalidate cache and retry once
            _jwks_cache.invalidate()
            jwks = get_jwks()
            for key in jwks.get("keys", []):
                if key.get("kid") == kid:
                    matching_key = key
                    break
            if not matching_key:
                raise InvalidTokenError("No matching key found in JWKS")
        
        issuer = (
            f"https://cognito-idp.{settings.cognito_region}.amazonaws.com/"
            f"{settings.cognito_user_pool_id}"
        )

        # Verify and decode token
        payload = jwt.decode(
            token,
            matching_key,
            algorithms=["RS256"],
            issuer=issuer,
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_aud": False,
                "verify_iss": True,
                "verify_at_hash": False
            }
        )

        token_use = payload.get("token_use")
        if token_use not in allowed_token_uses:
            raise InvalidTokenError(
                f"Invalid token_use '{token_use}'. Expected one of: {', '.join(allowed_token_uses)}"
            )

        # Cognito access tokens typically use client_id claim, while id tokens use aud.
        expected_client_id = settings.cognito_client_id
        audience_ok = False

        if token_use == "access":
            audience_ok = payload.get("client_id") == expected_client_id
            aud_claim = payload.get("aud")
            if not audience_ok and isinstance(aud_claim, str):
                audience_ok = aud_claim == expected_client_id
            if not audience_ok and isinstance(aud_claim, list):
                audience_ok = expected_client_id in aud_claim
        elif token_use == "id":
            aud_claim = payload.get("aud")
            if isinstance(aud_claim, str):
                audience_ok = aud_claim == expected_client_id
            elif isinstance(aud_claim, list):
                audience_ok = expected_client_id in aud_claim

        if not audience_ok:
            raise InvalidTokenError("Token audience/client_id does not match configured app client")
        
        # Validate token payload structure
        return TokenPayload(**payload)
        
    except JWTError as e:
        raise InvalidTokenError(f"JWT validation failed: {str(e)}")
    except ValidationError as e:
        raise InvalidTokenError(f"Token payload validation failed: {str(e)}")
    except ValueError as e:
        raise InvalidTokenError(f"Invalid token payload: {str(e)}")
    except Exception as e:
        raise InvalidTokenError(f"Token verification error: {str(e)}")


def verify_token_optional(token: str | None, allowed_token_uses: tuple[str, ...] = ("access",)) -> TokenPayload | None:
    """
    Verify token if provided, return None if missing
    Useful for endpoints that support optional authentication
    """
    if not token:
        return None
    return verify_token(token, allowed_token_uses=allowed_token_uses)

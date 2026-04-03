"""Unit tests for JWT token verification and JWKS caching."""
import base64
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from jose import jwt

from app.auth_usermanagement.security.jwt_verifier import (
    InvalidTokenError,
    _JWKSCache,
    verify_token,
    verify_token_optional,
    _jwks_cache,
)


# ── Helpers ──────────────────────────────────────────────────────

_TEST_KID = "test-kid-001"

# Generate a real RSA key pair for signing test JWTs
_rsa_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_rsa_public_key = _rsa_private_key.public_key()

# Convert to PEM for jose
_PRIVATE_PEM = _rsa_private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
)

_PUBLIC_PEM = _rsa_public_key.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
)


def _int_to_base64url(n: int) -> str:
    byte_length = (n.bit_length() + 7) // 8
    return base64.urlsafe_b64encode(n.to_bytes(byte_length, "big")).rstrip(b"=").decode()


# Build JWK from the generated key's public numbers
_pub_numbers = _rsa_public_key.public_numbers()
_TEST_JWK_PUBLIC = {
    "kty": "RSA",
    "kid": _TEST_KID,
    "n": _int_to_base64url(_pub_numbers.n),
    "e": _int_to_base64url(_pub_numbers.e),
    "use": "sig",
    "alg": "RS256",
}

_TEST_JWKS = {"keys": [_TEST_JWK_PUBLIC]}


def _make_token(claims: dict, kid: str = _TEST_KID) -> str:
    """Create a signed JWT using the test private key."""
    return jwt.encode(claims, _PRIVATE_PEM, algorithm="RS256", headers={"kid": kid})


def _base_claims(**overrides) -> dict:
    """Return base valid token claims."""
    now = int(time.time())
    claims = {
        "sub": "test-cognito-sub",
        "email": "alice@example.com",
        "token_use": "access",
        "client_id": "test-client-id",
        "iss": "https://cognito-idp.eu-west-1.amazonaws.com/test-pool",
        "iat": now - 10,
        "exp": now + 3600,
    }
    claims.update(overrides)
    return claims


@pytest.fixture(autouse=True)
def _patch_settings(monkeypatch):
    """Ensure JWT verifier uses test settings."""
    settings = SimpleNamespace(
        cognito_region="eu-west-1",
        cognito_user_pool_id="test-pool",
        cognito_client_id="test-client-id",
    )
    monkeypatch.setattr(
        "app.auth_usermanagement.security.jwt_verifier.get_settings",
        lambda: settings,
    )


# ── JWKS Cache tests ────────────────────────────────────────────


class TestJWKSCache:
    def test_cache_returns_fetched_jwks(self):
        cache = _JWKSCache(ttl=60)
        cache._jwks = _TEST_JWKS
        cache._fetched_at = time.monotonic()
        result = cache.get()
        assert result == _TEST_JWKS

    def test_cache_refetches_after_ttl(self):
        cache = _JWKSCache(ttl=1)
        cache._jwks = {"keys": []}
        cache._fetched_at = time.monotonic() - 2  # Expired

        with patch.object(cache, "_fetch_sync", return_value=_TEST_JWKS) as mock_fetch:
            result = cache.get()
            mock_fetch.assert_called_once()
            assert result == _TEST_JWKS

    def test_cache_uses_stale_on_fetch_failure(self):
        cache = _JWKSCache(ttl=1)
        cache._jwks = {"keys": [{"kid": "old"}]}
        cache._fetched_at = time.monotonic() - 2  # Expired

        import httpx
        with patch.object(cache, "_fetch_sync", side_effect=httpx.HTTPError("timeout")):
            result = cache.get()
            assert result == {"keys": [{"kid": "old"}]}

    def test_cache_raises_on_first_fetch_failure(self):
        cache = _JWKSCache(ttl=60)
        # No cached value at all
        import httpx
        with patch.object(cache, "_fetch_sync", side_effect=httpx.HTTPError("timeout")):
            with pytest.raises(InvalidTokenError, match="JWKS"):
                cache.get()

    def test_invalidate_forces_refetch(self):
        cache = _JWKSCache(ttl=3600)
        cache._jwks = {"keys": []}
        cache._fetched_at = time.monotonic()

        assert not cache._is_stale()
        cache.invalidate()
        assert cache._is_stale()


# ── verify_token tests ──────────────────────────────────────────


class TestVerifyToken:
    def test_valid_access_token(self):
        token = _make_token(_base_claims())
        with patch("app.auth_usermanagement.security.jwt_verifier.get_jwks", return_value=_TEST_JWKS):
            payload = verify_token(token)
        assert payload.sub == "test-cognito-sub"
        assert payload.email == "alice@example.com"

    def test_valid_id_token(self):
        claims = _base_claims(token_use="id", aud="test-client-id")
        claims.pop("client_id", None)
        token = _make_token(claims)
        with patch("app.auth_usermanagement.security.jwt_verifier.get_jwks", return_value=_TEST_JWKS):
            payload = verify_token(token, allowed_token_uses=("access", "id"))
        assert payload.sub == "test-cognito-sub"

    def test_rejects_expired_token(self):
        claims = _base_claims(exp=int(time.time()) - 100)
        token = _make_token(claims)
        with patch("app.auth_usermanagement.security.jwt_verifier.get_jwks", return_value=_TEST_JWKS):
            with pytest.raises(InvalidTokenError, match="JWT validation failed"):
                verify_token(token)

    def test_rejects_wrong_issuer(self):
        claims = _base_claims(iss="https://evil.example.com/pool")
        token = _make_token(claims)
        with patch("app.auth_usermanagement.security.jwt_verifier.get_jwks", return_value=_TEST_JWKS):
            with pytest.raises(InvalidTokenError):
                verify_token(token)

    def test_rejects_wrong_client_id(self):
        claims = _base_claims(client_id="wrong-client")
        token = _make_token(claims)
        with patch("app.auth_usermanagement.security.jwt_verifier.get_jwks", return_value=_TEST_JWKS):
            with pytest.raises(InvalidTokenError, match="audience"):
                verify_token(token)

    def test_rejects_wrong_token_use(self):
        claims = _base_claims(token_use="id")
        token = _make_token(claims)
        with patch("app.auth_usermanagement.security.jwt_verifier.get_jwks", return_value=_TEST_JWKS):
            with pytest.raises(InvalidTokenError, match="token_use"):
                verify_token(token)

    def test_rejects_missing_kid(self):
        """Token without kid in header should be rejected."""
        # Manually create a token without kid header
        token = jwt.encode(
            _base_claims(),
            _PRIVATE_PEM,
            algorithm="RS256",
            headers={"kid": None},
        )
        with patch("app.auth_usermanagement.security.jwt_verifier.get_jwks", return_value=_TEST_JWKS):
            with pytest.raises(InvalidTokenError):
                verify_token(token)

    def test_retries_jwks_on_unknown_kid(self):
        """When kid is not found, cache should be invalidated and refetched once."""
        token = _make_token(_base_claims(), kid="rotating-kid")
        new_jwks = {"keys": [{**_TEST_JWK_PUBLIC, "kid": "rotating-kid"}]}

        call_count = 0
        def mock_get_jwks():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"keys": []}  # Old cache — no match
            return new_jwks  # Refreshed — match

        with patch("app.auth_usermanagement.security.jwt_verifier.get_jwks", side_effect=mock_get_jwks), \
             patch("app.auth_usermanagement.security.jwt_verifier._jwks_cache") as mock_cache:
            mock_cache.invalidate = MagicMock()
            payload = verify_token(token)
            assert payload.sub == "test-cognito-sub"
            mock_cache.invalidate.assert_called_once()

    def test_rejects_completely_invalid_token(self):
        with patch("app.auth_usermanagement.security.jwt_verifier.get_jwks", return_value=_TEST_JWKS):
            with pytest.raises(InvalidTokenError):
                verify_token("not-a-jwt-at-all")

    def test_id_token_with_aud_list(self):
        """ID tokens may have aud as a list."""
        claims = _base_claims(token_use="id", aud=["test-client-id", "other-client"])
        claims.pop("client_id", None)
        token = _make_token(claims)
        with patch("app.auth_usermanagement.security.jwt_verifier.get_jwks", return_value=_TEST_JWKS):
            payload = verify_token(token, allowed_token_uses=("id",))
        assert payload.sub == "test-cognito-sub"


# ── verify_token_optional tests ─────────────────────────────────


class TestVerifyTokenOptional:
    def test_returns_none_when_no_token(self):
        result = verify_token_optional(None)
        assert result is None

    def test_returns_none_when_empty_string(self):
        result = verify_token_optional("")
        assert result is None

    def test_returns_payload_when_valid(self):
        token = _make_token(_base_claims())
        with patch("app.auth_usermanagement.security.jwt_verifier.get_jwks", return_value=_TEST_JWKS):
            payload = verify_token_optional(token)
        assert payload is not None
        assert payload.sub == "test-cognito-sub"

"""Real Cognito integration tests.

These tests hit the LIVE Cognito user pool configured in .env.
They are gated behind RUN_COGNITO_TESTS=1 so they don't run in
normal CI unless explicitly enabled.

Run:
    RUN_COGNITO_TESTS=1 pytest tests/test_cognito_integration.py -v
"""
from __future__ import annotations

import os
import secrets
import string
from uuid import uuid4

import boto3
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from tests.async_test_utils import make_test_db, make_async_app

load_dotenv()

RUN_COGNITO_TESTS = os.getenv("RUN_COGNITO_TESTS") == "1"

pytestmark = pytest.mark.skipif(
    not RUN_COGNITO_TESTS,
    reason="Set RUN_COGNITO_TESTS=1 to run live Cognito integration tests.",
)

COGNITO_REGION = os.getenv("COGNITO_REGION", "eu-west-1")
COGNITO_USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID", "")
COGNITO_CLIENT_ID = os.getenv("COGNITO_CLIENT_ID", "")

TEST_EMAIL_PREFIX = "testuser_integration"
TEST_EMAIL_DOMAIN = "ferrouslabs-test.example.com"


def _random_password(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()"
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(length))
        if (any(c.isupper() for c in pw) and any(c.islower() for c in pw)
                and any(c.isdigit() for c in pw) and any(c in "!@#$%^&*()" for c in pw)):
            return pw


def _cognito_client():
    return boto3.client("cognito-idp", region_name=COGNITO_REGION)


def _admin_delete_user(email: str):
    try:
        _cognito_client().admin_delete_user(
            UserPoolId=COGNITO_USER_POOL_ID, Username=email,
        )
    except Exception:
        pass


def _admin_create_confirmed_user(email: str, password: str):
    client = _cognito_client()
    client.admin_create_user(
        UserPoolId=COGNITO_USER_POOL_ID,
        Username=email,
        UserAttributes=[{"Name": "email", "Value": email}, {"Name": "email_verified", "Value": "true"}],
        MessageAction="SUPPRESS",
    )
    client.admin_set_user_password(
        UserPoolId=COGNITO_USER_POOL_ID,
        Username=email,
        Password=password,
        Permanent=True,
    )


def _make_db():
    from app.database import Base
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    SL = sessionmaker(bind=engine)
    return engine, SL


def _app_client(SL):
    from app.database import get_db
    from app.main import app

    def _override():
        db = SL()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override
    return TestClient(app, raise_server_exceptions=False)


# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture()
def test_user():
    unique = uuid4().hex[:8]
    email = f"{TEST_EMAIL_PREFIX}_{unique}@{TEST_EMAIL_DOMAIN}"
    password = _random_password()
    _admin_create_confirmed_user(email, password)
    yield {"email": email, "password": password}
    _admin_delete_user(email)


@pytest.fixture()
def cognito_tokens(test_user):
    client = _cognito_client()
    resp = client.initiate_auth(
        ClientId=COGNITO_CLIENT_ID,
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={"USERNAME": test_user["email"], "PASSWORD": test_user["password"]},
    )
    result = resp["AuthenticationResult"]
    return {
        "access_token": result["AccessToken"],
        "id_token": result["IdToken"],
        "refresh_token": result["RefreshToken"],
        "email": test_user["email"],
        "password": test_user["password"],
    }


# ── 1. Cognito Admin Service — Real Calls ────────────────────────


class TestCognitoAdminServiceReal:

    def test_create_invited_user_and_delete(self):
        from app.auth_usermanagement.services.cognito_admin_service import (
            create_invited_cognito_user,
            admin_delete_user,
            admin_get_user,
        )

        email = f"{TEST_EMAIL_PREFIX}_{uuid4().hex[:8]}@{TEST_EMAIL_DOMAIN}"
        try:
            result = create_invited_cognito_user(email)
            assert result["status"] == "FORCE_CHANGE_PASSWORD"
            assert result["cognito_sub"] is not None
            assert result["temp_password"] is not None

            info = admin_get_user(email)
            assert info["attributes"]["email"] == email
            assert info["status"] in ("FORCE_CHANGE_PASSWORD", "CONFIRMED")
        finally:
            admin_delete_user(email)

    def test_admin_disable_and_enable(self, test_user):
        from app.auth_usermanagement.services.cognito_admin_service import (
            admin_disable_user,
            admin_enable_user,
            admin_get_user,
        )

        result = admin_disable_user(test_user["email"])
        assert result["disabled"] is True

        info = admin_get_user(test_user["email"])
        assert info["enabled"] is False

        result = admin_enable_user(test_user["email"])
        assert result["enabled"] is True

        info = admin_get_user(test_user["email"])
        assert info["enabled"] is True

    def test_admin_get_user(self, test_user):
        from app.auth_usermanagement.services.cognito_admin_service import admin_get_user

        info = admin_get_user(test_user["email"])
        assert info["attributes"]["email"] == test_user["email"]
        assert "status" in info
        assert "enabled" in info
        assert "created_at" in info

    def test_admin_get_nonexistent_user(self):
        from app.auth_usermanagement.services.cognito_admin_service import admin_get_user

        result = admin_get_user(f"nonexistent_{uuid4().hex}@{TEST_EMAIL_DOMAIN}")
        assert "error" in result

    def test_admin_reset_user_password(self, test_user):
        from app.auth_usermanagement.services.cognito_admin_service import admin_reset_user_password

        result = admin_reset_user_password(test_user["email"])
        assert result["reset_initiated"] is True

    def test_initiate_auth_success(self, test_user):
        from app.auth_usermanagement.services.cognito_admin_service import initiate_auth

        result = initiate_auth(test_user["email"], test_user["password"])
        assert result["authenticated"] is True
        assert "access_token" in result
        assert "id_token" in result
        assert "refresh_token" in result

    def test_initiate_auth_wrong_password(self, test_user):
        from app.auth_usermanagement.services.cognito_admin_service import initiate_auth

        result = initiate_auth(test_user["email"], "WrongPassword123!")
        assert "error" in result

    def test_initiate_auth_nonexistent_user(self):
        from app.auth_usermanagement.services.cognito_admin_service import initiate_auth

        result = initiate_auth(f"ghost_{uuid4().hex}@{TEST_EMAIL_DOMAIN}", "Pass123!!")
        assert "error" in result

    def test_sign_up_and_delete(self):
        from app.auth_usermanagement.services.cognito_admin_service import (
            sign_up_user,
            admin_delete_user,
        )

        email = f"{TEST_EMAIL_PREFIX}_{uuid4().hex[:8]}@{TEST_EMAIL_DOMAIN}"
        password = _random_password()
        try:
            result = sign_up_user(email, password)
            assert "user_sub" in result
            assert "confirmed" in result
        finally:
            admin_delete_user(email)

    def test_forgot_password_nonexistent_user(self):
        from app.auth_usermanagement.services.cognito_admin_service import forgot_password

        result = forgot_password(f"ghost_{uuid4().hex}@{TEST_EMAIL_DOMAIN}")
        assert isinstance(result, dict)
        # Should not raise — Cognito hides user existence

    def test_resend_confirmation_code_for_confirmed_user(self, test_user):
        from app.auth_usermanagement.services.cognito_admin_service import resend_confirmation_code

        result = resend_confirmation_code(test_user["email"])
        assert isinstance(result, dict)

    def test_invited_user_login_returns_challenge(self):
        """Create an invited user and verify login returns NEW_PASSWORD_REQUIRED."""
        from app.auth_usermanagement.services.cognito_admin_service import (
            create_invited_cognito_user,
            initiate_auth,
            admin_delete_user,
        )

        email = f"{TEST_EMAIL_PREFIX}_{uuid4().hex[:8]}@{TEST_EMAIL_DOMAIN}"
        try:
            created = create_invited_cognito_user(email)
            result = initiate_auth(email, created["temp_password"])
            assert result.get("challenge") == "NEW_PASSWORD_REQUIRED"
            assert result["authenticated"] is False
            assert "session" in result
        finally:
            admin_delete_user(email)

    def test_invited_user_full_flow(self):
        """Create invited user → login (challenge) → set password → login (tokens)."""
        from app.auth_usermanagement.services.cognito_admin_service import (
            create_invited_cognito_user,
            initiate_auth,
            respond_to_new_password_challenge,
            admin_delete_user,
        )

        email = f"{TEST_EMAIL_PREFIX}_{uuid4().hex[:8]}@{TEST_EMAIL_DOMAIN}"
        permanent_password = _random_password()
        try:
            created = create_invited_cognito_user(email)

            # Step 1: Login with temp password → challenge
            challenge = initiate_auth(email, created["temp_password"])
            assert challenge.get("challenge") == "NEW_PASSWORD_REQUIRED"

            # Step 2: Set permanent password
            set_result = respond_to_new_password_challenge(
                email, permanent_password, challenge["session"],
            )
            assert set_result["authenticated"] is True
            assert "access_token" in set_result

            # Step 3: Login with permanent password → direct tokens
            login = initiate_auth(email, permanent_password)
            assert login["authenticated"] is True
            assert "access_token" in login
        finally:
            admin_delete_user(email)


# ── 2. JWT Verifier — Real Token Validation ──────────────────────


class TestJWTVerifierReal:

    def test_verify_real_access_token(self, cognito_tokens):
        from app.auth_usermanagement.security.jwt_verifier import verify_token

        payload = verify_token(cognito_tokens["access_token"])
        assert payload.sub is not None
        assert payload.token_use == "access"

    def test_verify_real_id_token(self, cognito_tokens):
        from app.auth_usermanagement.security.jwt_verifier import verify_token

        payload = verify_token(cognito_tokens["id_token"], allowed_token_uses=("id",))
        assert payload.sub is not None
        assert payload.email == cognito_tokens["email"]

    def test_verify_expired_token_fails(self):
        from app.auth_usermanagement.security.jwt_verifier import verify_token, InvalidTokenError

        with pytest.raises(InvalidTokenError):
            verify_token("eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0IiwiZXhwIjoxfQ.fake")

    def test_verify_garbage_token_fails(self):
        from app.auth_usermanagement.security.jwt_verifier import verify_token, InvalidTokenError

        with pytest.raises(InvalidTokenError):
            verify_token("not.a.real.token")

    def test_jwks_cache_fetches_real_keys(self):
        from app.auth_usermanagement.security.jwt_verifier import _jwks_cache

        keys = _jwks_cache.get()
        assert "keys" in keys
        assert len(keys["keys"]) >= 1
        assert all("kid" in k for k in keys["keys"])


# ── 3. Custom UI Routes — Full Round-Trip ────────────────────────


class TestCustomUIRoutesReal:

    def test_login_success_returns_tokens(self, test_user):
        from app.database import Base
        from app.main import app

        engine, SL = _make_db()
        try:
            client = _app_client(SL)
            r = client.post("/auth/custom/login", json={
                "email": test_user["email"],
                "password": test_user["password"],
            })
            assert r.status_code == 200
            data = r.json()
            assert data["authenticated"] is True
            assert data["access_token"] is not None
            assert data["id_token"] is not None
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_login_wrong_password(self, test_user):
        from app.database import Base
        from app.main import app

        engine, SL = _make_db()
        try:
            client = _app_client(SL)
            r = client.post("/auth/custom/login", json={
                "email": test_user["email"],
                "password": "WrongPass999!",
            })
            assert r.status_code == 401
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_login_nonexistent_user(self):
        from app.database import Base
        from app.main import app

        engine, SL = _make_db()
        try:
            client = _app_client(SL)
            r = client.post("/auth/custom/login", json={
                "email": f"ghost_{uuid4().hex}@{TEST_EMAIL_DOMAIN}",
                "password": "SomePass123!",
            })
            assert r.status_code == 401
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_signup_creates_user(self):
        from app.database import Base
        from app.main import app

        engine, SL = _make_db()
        email = f"{TEST_EMAIL_PREFIX}_{uuid4().hex[:8]}@{TEST_EMAIL_DOMAIN}"
        try:
            client = _app_client(SL)
            r = client.post("/auth/custom/signup", json={
                "email": email,
                "password": _random_password(),
            })
            assert r.status_code == 200
            data = r.json()
            assert data["user_sub"] is not None
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)
            _admin_delete_user(email)

    def test_forgot_password_endpoint(self, test_user):
        from app.database import Base
        from app.main import app

        engine, SL = _make_db()
        try:
            client = _app_client(SL)
            r = client.post("/auth/custom/forgot-password", json={
                "email": test_user["email"],
            })
            assert r.status_code == 200
            data = r.json()
            assert data["sent"] is True
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_resend_code_endpoint(self, test_user):
        from app.database import Base
        from app.main import app

        engine, SL = _make_db()
        try:
            client = _app_client(SL)
            r = client.post("/auth/custom/resend-code", json={
                "email": test_user["email"],
            })
            # Confirmed user gets 400 ("Cannot resend...")
            assert r.status_code in (200, 400)
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_invited_user_set_password_via_api(self):
        """Full invitation flow through HTTP endpoints."""
        from app.auth_usermanagement.services.cognito_admin_service import (
            create_invited_cognito_user,
            admin_delete_user,
        )
        from app.database import Base
        from app.main import app

        engine, SL = _make_db()
        email = f"{TEST_EMAIL_PREFIX}_{uuid4().hex[:8]}@{TEST_EMAIL_DOMAIN}"
        try:
            created = create_invited_cognito_user(email)
            client = _app_client(SL)

            # Login with temp password → challenge
            r = client.post("/auth/custom/login", json={
                "email": email,
                "password": created["temp_password"],
            })
            assert r.status_code == 200
            data = r.json()
            assert data["challenge"] == "NEW_PASSWORD_REQUIRED"
            assert data["session"] is not None

            # Set permanent password
            permanent_pw = _random_password()
            r = client.post("/auth/custom/set-password", json={
                "email": email,
                "new_password": permanent_pw,
                "session": data["session"],
            })
            assert r.status_code == 200
            data = r.json()
            assert data["authenticated"] is True
            assert data["access_token"] is not None
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)
            admin_delete_user(email)


# ── 4. Sync + Debug-token — Real Token ───────────────────────────


class TestSyncAndDebugWithRealToken:

    def test_sync_creates_user_from_real_token(self, cognito_tokens):
        from app.database import Base
        from app.main import app
        from app.auth_usermanagement.models.tenant import Tenant

        engine, SL = _make_db()
        # Sync needs X-Tenant-ID — create a tenant
        s = SL()
        t = Tenant(name="TestTenant", plan="pro", status="active")
        s.add(t)
        s.commit()
        tid = str(t.id)
        s.close()

        try:
            client = _app_client(SL)
            # Use id_token — access tokens don't carry the email claim
            r = client.post(
                "/auth/sync",
                headers={
                    "Authorization": f"Bearer {cognito_tokens['id_token']}",
                    "X-Tenant-ID": tid,
                },
            )
            assert r.status_code == 200
            data = r.json()
            assert data["email"] == cognito_tokens["email"]
            assert data["cognito_sub"] is not None
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

    def test_debug_token_with_real_token(self, cognito_tokens, monkeypatch):
        monkeypatch.setenv("AUTH_DEBUG", "1")
        from app.database import Base
        from app.main import app

        engine, SL = _make_db()
        try:
            client = _app_client(SL)
            r = client.get(
                "/auth/debug-token",
                headers={"Authorization": f"Bearer {cognito_tokens['access_token']}"},
            )
            assert r.status_code == 200
            data = r.json()
            assert data["status"] == "valid"
            assert data["claims"]["sub"] is not None
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)


# ── 5. Full Auth Round-Trip ───────────────────────────────────────


class TestFullAuthRoundTrip:

    def test_login_sync_debug_roundtrip(self, test_user, monkeypatch):
        monkeypatch.setenv("AUTH_DEBUG", "1")
        from app.database import Base
        from app.main import app
        from app.auth_usermanagement.models.tenant import Tenant

        engine, SL = _make_db()
        s = SL()
        t = Tenant(name="RoundTrip", plan="pro", status="active")
        s.add(t)
        s.commit()
        tid = str(t.id)
        s.close()

        try:
            client = _app_client(SL)

            # Step 1: Login via custom UI
            login_r = client.post("/auth/custom/login", json={
                "email": test_user["email"],
                "password": test_user["password"],
            })
            assert login_r.status_code == 200
            access_token = login_r.json()["access_token"]
            id_token = login_r.json()["id_token"]

            # Step 2: Sync user with id_token (has email claim)
            sync_r = client.post(
                "/auth/sync",
                headers={
                    "Authorization": f"Bearer {id_token}",
                    "X-Tenant-ID": tid,
                },
            )
            assert sync_r.status_code == 200
            assert sync_r.json()["email"] == test_user["email"]

            # Step 3: Debug token
            debug_r = client.get(
                "/auth/debug-token",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            assert debug_r.status_code == 200
            assert debug_r.json()["status"] == "valid"
        finally:
            app.dependency_overrides.clear()
            Base.metadata.drop_all(sync_engine)

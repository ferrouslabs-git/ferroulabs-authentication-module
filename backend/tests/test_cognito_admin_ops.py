"""Unit tests for cognito_admin_service admin operations and user_service.delete_user."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.auth_usermanagement.models.membership import Membership
from app.auth_usermanagement.models.session import Session as AuthSession
from app.auth_usermanagement.models.invitation import Invitation
from app.auth_usermanagement.models.tenant import Tenant
from app.auth_usermanagement.models.user import User
from app.auth_usermanagement.services.cognito_admin_service import (
    admin_delete_user,
    admin_disable_user,
    admin_enable_user,
    admin_get_user,
    admin_reset_user_password,
    create_invited_cognito_user,
)
from app.auth_usermanagement.services.user_service import delete_user
from app.database import Base
from tests.async_test_utils import make_test_db, make_async_app


def _make_db():
    return make_test_db()


# ── cognito_admin_service unit tests ─────────────────────────────


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_admin_delete_user_success(mock_client_factory):
    client = MagicMock()
    mock_client_factory.return_value = client

    result = admin_delete_user("alice@example.com")

    assert result["deleted"] is True
    client.admin_delete_user.assert_called_once()


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_admin_delete_user_not_found_is_idempotent(mock_client_factory):
    from botocore.exceptions import ClientError

    client = MagicMock()
    mock_client_factory.return_value = client
    client.admin_delete_user.side_effect = ClientError(
        {"Error": {"Code": "UserNotFoundException", "Message": "User not found"}},
        "AdminDeleteUser",
    )

    result = admin_delete_user("ghost@example.com")

    assert result["deleted"] is True
    assert result.get("already_absent") is True


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_admin_disable_user_success(mock_client_factory):
    client = MagicMock()
    mock_client_factory.return_value = client

    result = admin_disable_user("alice@example.com")

    assert result["disabled"] is True
    client.admin_disable_user.assert_called_once()


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_admin_enable_user_success(mock_client_factory):
    client = MagicMock()
    mock_client_factory.return_value = client

    result = admin_enable_user("alice@example.com")

    assert result["enabled"] is True
    client.admin_enable_user.assert_called_once()


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_admin_get_user_returns_status(mock_client_factory):
    client = MagicMock()
    mock_client_factory.return_value = client
    client.admin_get_user.return_value = {
        "Username": "alice@example.com",
        "UserStatus": "CONFIRMED",
        "Enabled": True,
        "UserCreateDate": "2026-01-01T00:00:00Z",
        "UserLastModifiedDate": "2026-03-01T00:00:00Z",
        "UserAttributes": [
            {"Name": "sub", "Value": "abc-123"},
            {"Name": "email", "Value": "alice@example.com"},
        ],
    }

    result = admin_get_user("alice@example.com")

    assert result["status"] == "CONFIRMED"
    assert result["enabled"] is True
    assert result["attributes"]["email"] == "alice@example.com"


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_admin_get_user_not_found(mock_client_factory):
    from botocore.exceptions import ClientError

    client = MagicMock()
    mock_client_factory.return_value = client
    client.admin_get_user.side_effect = ClientError(
        {"Error": {"Code": "UserNotFoundException", "Message": "Not found"}},
        "AdminGetUser",
    )

    result = admin_get_user("ghost@example.com")

    assert "error" in result


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_admin_reset_user_password_success(mock_client_factory):
    client = MagicMock()
    mock_client_factory.return_value = client

    result = admin_reset_user_password("alice@example.com")

    assert result["reset_initiated"] is True
    client.admin_reset_user_password.assert_called_once()


# ── user_service.delete_user unit tests ──────────────────────────


@patch("app.auth_usermanagement.services.cognito_admin_service.admin_delete_user")
@pytest.mark.asyncio
async def test_delete_user_removes_all_related_records(mock_cognito_delete):
    sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()
    mock_cognito_delete.return_value = {"deleted": True}

    session = SyncSession()
    tenant = Tenant(name="Test Tenant")
    user = User(cognito_sub="del-sub-1", email="del@example.com", name="Del User")
    session.add_all([tenant, user])
    session.commit()

    session.add(Membership(user_id=user.id, scope_type="account", scope_id=tenant.id, role_name="account_member", status="active"))
    session.add(AuthSession(user_id=user.id, refresh_token_hash="abc123"))
    session.commit()
    user_id = user.id
    session.close()

    try:
        async with AsyncSessionLocal() as adb:
            result = await delete_user(user_id, adb)

            assert result["deleted"] is True
            assert result["email"] == "del@example.com"

        # Verify cleanup with sync session
        session = SyncSession()
        assert session.query(User).filter(User.id == user_id).first() is None
        assert session.query(Membership).filter(Membership.user_id == user_id).count() == 0
        assert session.query(AuthSession).filter(AuthSession.user_id == user_id).count() == 0
        session.close()
    finally:
        Base.metadata.drop_all(sync_engine)


@patch("app.auth_usermanagement.services.cognito_admin_service.admin_delete_user")
@pytest.mark.asyncio
async def test_delete_user_rejects_platform_admin(mock_cognito_delete):
    sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()

    session = SyncSession()
    user = User(cognito_sub="admin-del", email="admin-del@example.com", name="PA", is_platform_admin=True)
    session.add(user)
    session.commit()
    user_id = user.id
    session.close()

    try:
        async with AsyncSessionLocal() as adb:
            with pytest.raises(ValueError, match="platform admin"):
                await delete_user(user_id, adb)
        mock_cognito_delete.assert_not_called()
    finally:
        Base.metadata.drop_all(sync_engine)


@patch("app.auth_usermanagement.services.cognito_admin_service.admin_delete_user")
@pytest.mark.asyncio
async def test_delete_user_rejects_last_owner(mock_cognito_delete):
    sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()

    session = SyncSession()
    tenant = Tenant(name="Sole Owner Corp")
    user = User(cognito_sub="sole-owner", email="sole@example.com", name="Sole")
    session.add_all([tenant, user])
    session.commit()
    session.add(Membership(user_id=user.id, scope_type="account", scope_id=tenant.id, role_name="account_owner", status="active"))
    session.commit()
    user_id = user.id
    session.close()

    try:
        async with AsyncSessionLocal() as adb:
            with pytest.raises(ValueError, match="last owner"):
                await delete_user(user_id, adb)
        mock_cognito_delete.assert_not_called()
    finally:
        Base.metadata.drop_all(sync_engine)


@patch("app.auth_usermanagement.services.cognito_admin_service.admin_delete_user")
@pytest.mark.asyncio
async def test_delete_user_not_found(mock_cognito_delete):
    sync_engine, SyncSession, async_engine, AsyncSessionLocal = _make_db()

    try:
        async with AsyncSessionLocal() as adb:
            with pytest.raises(ValueError, match="not found"):
                await delete_user(uuid4(), adb)
    finally:
        Base.metadata.drop_all(sync_engine)


# ── create_invited_cognito_user tests ─────────────────────────────────


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_create_invited_cognito_user_success(mock_client_factory):
    client = MagicMock()
    mock_client_factory.return_value = client
    client.admin_create_user.return_value = {
        "User": {
            "Attributes": [
                {"Name": "sub", "Value": "new-sub-123"},
                {"Name": "email", "Value": "invite@example.com"},
            ],
        }
    }

    result = create_invited_cognito_user("invite@example.com")

    assert result["cognito_sub"] == "new-sub-123"
    assert result["status"] == "FORCE_CHANGE_PASSWORD"
    assert "temp_password" in result
    client.admin_create_user.assert_called_once()
    call_kwargs = client.admin_create_user.call_args[1]
    assert call_kwargs["MessageAction"] == "SUPPRESS"


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_create_invited_cognito_user_already_exists_resets_password(mock_client_factory):
    """When user already exists, it should reset to FORCE_CHANGE_PASSWORD."""
    from botocore.exceptions import ClientError

    client = MagicMock()
    mock_client_factory.return_value = client
    client.admin_create_user.side_effect = ClientError(
        {"Error": {"Code": "UsernameExistsException", "Message": "User exists"}},
        "AdminCreateUser",
    )

    result = create_invited_cognito_user("existing@example.com")

    assert result["status"] == "FORCE_CHANGE_PASSWORD"
    assert "temp_password" in result
    client.admin_set_user_password.assert_called_once()
    call_kwargs = client.admin_set_user_password.call_args[1]
    assert call_kwargs["Permanent"] is False


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_create_invited_cognito_user_other_client_error(mock_client_factory):
    """Non-UsernameExistsException errors should return error dict."""
    from botocore.exceptions import ClientError

    client = MagicMock()
    mock_client_factory.return_value = client
    client.admin_create_user.side_effect = ClientError(
        {"Error": {"Code": "InternalErrorException", "Message": "Service unavailable"}},
        "AdminCreateUser",
    )

    result = create_invited_cognito_user("fail@example.com")

    assert "error" in result
    assert "Service unavailable" in result["error"]


@patch("app.auth_usermanagement.services.cognito_admin_service._get_cognito_client")
def test_create_invited_cognito_user_reset_fails(mock_client_factory):
    """When user exists but password reset also fails, should return error."""
    from botocore.exceptions import ClientError

    client = MagicMock()
    mock_client_factory.return_value = client
    client.admin_create_user.side_effect = ClientError(
        {"Error": {"Code": "UsernameExistsException", "Message": "User exists"}},
        "AdminCreateUser",
    )
    client.admin_set_user_password.side_effect = ClientError(
        {"Error": {"Code": "InternalErrorException", "Message": "Reset failed"}},
        "AdminSetUserPassword",
    )

    result = create_invited_cognito_user("fail-reset@example.com")

    assert "error" in result
    assert "Reset failed" in result["error"]

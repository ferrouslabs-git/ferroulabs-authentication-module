"""
Tests for user account suspension functionality.
"""
import pytest
from uuid import uuid4
from datetime import datetime, UTC

from app.auth_usermanagement.models.user import User
from app.auth_usermanagement.services.user_service import (
    suspend_user,
    unsuspend_user,
    get_user_by_id,
)


def utc_now():
    """Return current UTC datetime without timezone info."""
    return datetime.now(UTC).replace(tzinfo=None)


@pytest.mark.asyncio
async def test_suspend_user(dual_session):
    """Test suspending a user account."""
    sync_db, async_db = dual_session
    user = User(
        cognito_sub="test-sub-123",
        email="test@example.com",
        name="Test User",
        is_active=True,
    )
    sync_db.add(user)
    sync_db.commit()
    sync_db.refresh(user)

    suspended = await suspend_user(user.id, async_db)

    assert suspended.is_active is False
    assert suspended.suspended_at is not None
    assert suspended.suspended_at <= utc_now()
    assert suspended.id == user.id


@pytest.mark.asyncio
async def test_unsuspend_user(dual_session):
    """Test unsuspending a previously suspended user."""
    sync_db, async_db = dual_session
    user = User(
        cognito_sub="test-sub-456",
        email="suspended@example.com",
        name="Suspended User",
        is_active=False,
        suspended_at=utc_now(),
    )
    sync_db.add(user)
    sync_db.commit()
    sync_db.refresh(user)

    unsuspended = await unsuspend_user(user.id, async_db)

    assert unsuspended.is_active is True
    assert unsuspended.suspended_at is None
    assert unsuspended.id == user.id


@pytest.mark.asyncio
async def test_suspend_nonexistent_user(dual_session):
    """Test suspending a user that doesn't exist."""
    sync_db, async_db = dual_session
    fake_user_id = uuid4()

    with pytest.raises(ValueError, match=f"User {fake_user_id} not found"):
        await suspend_user(fake_user_id, async_db)


@pytest.mark.asyncio
async def test_unsuspend_nonexistent_user(dual_session):
    """Test unsuspending a user that doesn't exist."""
    sync_db, async_db = dual_session
    fake_user_id = uuid4()

    with pytest.raises(ValueError, match=f"User {fake_user_id} not found"):
        await unsuspend_user(fake_user_id, async_db)


@pytest.mark.asyncio
async def test_suspend_already_suspended_user(dual_session):
    """Test suspending a user that is already suspended (idempotent)."""
    sync_db, async_db = dual_session
    user = User(
        cognito_sub="test-sub-789",
        email="already-suspended@example.com",
        name="Already Suspended",
        is_active=False,
        suspended_at=utc_now(),
    )
    sync_db.add(user)
    sync_db.commit()
    sync_db.refresh(user)

    original_suspended_at = user.suspended_at

    suspended = await suspend_user(user.id, async_db)

    assert suspended.is_active is False
    assert suspended.suspended_at is not None
    assert suspended.suspended_at >= original_suspended_at


@pytest.mark.asyncio
async def test_unsuspend_active_user(dual_session):
    """Test unsuspending a user that is already active (idempotent)."""
    sync_db, async_db = dual_session
    user = User(
        cognito_sub="test-sub-101",
        email="active@example.com",
        name="Active User",
        is_active=True,
    )
    sync_db.add(user)
    sync_db.commit()
    sync_db.refresh(user)

    unsuspended = await unsuspend_user(user.id, async_db)

    assert unsuspended.is_active is True
    assert unsuspended.suspended_at is None


def test_new_users_are_active_by_default(db_session):
    """Test that newly created users have is_active=True by default."""
    user = User(
        cognito_sub="test-sub-202",
        email="new@example.com",
        name="New User",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.is_active is True
    assert user.suspended_at is None


@pytest.mark.asyncio
async def test_suspend_user_calls_cognito_global_sign_out(dual_session, monkeypatch):
    """Verify that suspending a user triggers a Cognito global sign-out."""
    sync_db, async_db = dual_session
    user = User(
        cognito_sub="sign-out-sub",
        email="signout@example.com",
        name="Sign Out User",
        is_active=True,
    )
    sync_db.add(user)
    sync_db.commit()
    sync_db.refresh(user)

    calls = []

    class FakeCognitoClient:
        def admin_user_global_sign_out(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setenv("COGNITO_USER_POOL_ID", "eu-west-1_TestPool")
    from app.auth_usermanagement.config import get_settings
    get_settings.cache_clear()

    monkeypatch.setattr(
        "app.auth_usermanagement.services.user_service.boto3",
        type("FakeBoto3", (), {"client": staticmethod(lambda *a, **kw: FakeCognitoClient())})(),
    )

    await suspend_user(user.id, async_db)

    assert len(calls) == 1
    assert calls[0]["UserPoolId"] == "eu-west-1_TestPool"
    assert calls[0]["Username"] == "sign-out-sub"

    get_settings.cache_clear()

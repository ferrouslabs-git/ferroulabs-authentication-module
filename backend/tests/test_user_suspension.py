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


def test_suspend_user(db_session):
    """Test suspending a user account."""
    # Create a test user
    user = User(
        cognito_sub="test-sub-123",
        email="test@example.com",
        name="Test User",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Suspend the user
    suspended = suspend_user(user.id, db_session)

    assert suspended.is_active is False
    assert suspended.suspended_at is not None
    assert suspended.suspended_at <= utc_now()
    assert suspended.id == user.id


def test_unsuspend_user(db_session):
    """Test unsuspending a previously suspended user."""
    # Create a suspended user
    user = User(
        cognito_sub="test-sub-456",
        email="suspended@example.com",
        name="Suspended User",
        is_active=False,
        suspended_at=utc_now(),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Unsuspend the user
    unsuspended = unsuspend_user(user.id, db_session)

    assert unsuspended.is_active is True
    assert unsuspended.suspended_at is None
    assert unsuspended.id == user.id


def test_suspend_nonexistent_user(db_session):
    """Test suspending a user that doesn't exist."""
    fake_user_id = uuid4()

    with pytest.raises(ValueError, match=f"User {fake_user_id} not found"):
        suspend_user(fake_user_id, db_session)


def test_unsuspend_nonexistent_user(db_session):
    """Test unsuspending a user that doesn't exist."""
    fake_user_id = uuid4()

    with pytest.raises(ValueError, match=f"User {fake_user_id} not found"):
        unsuspend_user(fake_user_id, db_session)


def test_suspend_already_suspended_user(db_session):
    """Test suspending a user that is already suspended (idempotent)."""
    user = User(
        cognito_sub="test-sub-789",
        email="already-suspended@example.com",
        name="Already Suspended",
        is_active=False,
        suspended_at=utc_now(),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    original_suspended_at = user.suspended_at

    # Suspend again
    suspended = suspend_user(user.id, db_session)

    assert suspended.is_active is False
    assert suspended.suspended_at is not None
    # Suspended_at should be updated to new timestamp
    assert suspended.suspended_at >= original_suspended_at


def test_unsuspend_active_user(db_session):
    """Test unsuspending a user that is already active (idempotent)."""
    user = User(
        cognito_sub="test-sub-101",
        email="active@example.com",
        name="Active User",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Unsuspend (should be no-op)
    unsuspended = unsuspend_user(user.id, db_session)

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


def test_suspend_user_calls_cognito_global_sign_out(db_session, monkeypatch):
    """Verify that suspending a user triggers a Cognito global sign-out."""
    user = User(
        cognito_sub="sign-out-sub",
        email="signout@example.com",
        name="Sign Out User",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    calls = []

    class FakeCognitoClient:
        def admin_user_global_sign_out(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setenv("COGNITO_USER_POOL_ID", "eu-west-1_TestPool")
    # Clear the lru_cache so Settings picks up the new env var
    from app.auth_usermanagement.config import get_settings
    get_settings.cache_clear()

    monkeypatch.setattr(
        "app.auth_usermanagement.services.user_service.boto3",
        type("FakeBoto3", (), {"client": staticmethod(lambda *a, **kw: FakeCognitoClient())})(),
    )

    suspend_user(user.id, db_session)

    assert len(calls) == 1
    assert calls[0]["UserPoolId"] == "eu-west-1_TestPool"
    assert calls[0]["Username"] == "sign-out-sub"

    # Restore cached settings
    get_settings.cache_clear()

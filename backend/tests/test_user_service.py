"""Unit tests for user_service — sync, promote, demote."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.auth_usermanagement.models.user import User
from app.auth_usermanagement.services.user_service import (
    demote_from_platform_admin,
    promote_to_platform_admin,
    sync_user_from_cognito,
)


# ── sync_user_from_cognito ───────────────────────────────────────


def test_sync_creates_new_user(db_session):
    payload = SimpleNamespace(sub="cognito-abc", email="new@example.com", name="New User")
    user = sync_user_from_cognito(payload, db_session)

    assert user.cognito_sub == "cognito-abc"
    assert user.email == "new@example.com"
    assert user.name == "New User"
    assert user.is_active is True


def test_sync_updates_existing_user_by_sub(db_session):
    existing = User(cognito_sub="cognito-xyz", email="old@example.com", name="Old")
    db_session.add(existing)
    db_session.commit()

    payload = SimpleNamespace(sub="cognito-xyz", email="updated@example.com", name="Updated")
    user = sync_user_from_cognito(payload, db_session)

    assert user.id == existing.id
    assert user.email == "updated@example.com"
    assert user.name == "Updated"


def test_sync_handles_cognito_recreation_by_email(db_session):
    """When a Cognito user is deleted and recreated with a new sub but same email."""
    existing = User(cognito_sub="old-sub", email="same@example.com", name="Same")
    db_session.add(existing)
    db_session.commit()

    payload = SimpleNamespace(sub="new-sub", email="same@example.com", name="Same Updated")
    user = sync_user_from_cognito(payload, db_session)

    assert user.id == existing.id
    assert user.cognito_sub == "new-sub"
    assert user.name == "Same Updated"


def test_sync_raises_when_email_missing():
    payload = SimpleNamespace(sub="some-sub", email=None, name="NoEmail")

    with pytest.raises(ValueError, match="Token missing email claim"):
        sync_user_from_cognito(payload, None)


def test_sync_idempotent_no_change(db_session):
    existing = User(cognito_sub="sub-same", email="stable@example.com", name="Stable")
    db_session.add(existing)
    db_session.commit()

    payload = SimpleNamespace(sub="sub-same", email="stable@example.com", name="Stable")
    user = sync_user_from_cognito(payload, db_session)

    assert user.id == existing.id
    assert user.email == "stable@example.com"


def test_sync_without_name_preserves_none(db_session):
    payload = SimpleNamespace(sub="sub-noname", email="noname@example.com", name=None)
    user = sync_user_from_cognito(payload, db_session)

    assert user.email == "noname@example.com"
    assert user.name is None


# ── promote_to_platform_admin ────────────────────────────────────


def test_promote_to_platform_admin(db_session):
    user = User(cognito_sub="promo-sub", email="promo@example.com", name="P")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    result = promote_to_platform_admin(user.id, db_session)
    assert result.is_platform_admin is True


def test_promote_nonexistent_user_raises(db_session):
    with pytest.raises(ValueError, match="not found"):
        promote_to_platform_admin(uuid4(), db_session)


def test_promote_already_admin_is_idempotent(db_session):
    user = User(cognito_sub="admin-sub", email="admin@example.com",
                name="A", is_platform_admin=True)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    result = promote_to_platform_admin(user.id, db_session)
    assert result.is_platform_admin is True


# ── demote_from_platform_admin ───────────────────────────────────


def test_demote_from_platform_admin(db_session):
    u1 = User(cognito_sub="d1", email="d1@example.com", name="D1", is_platform_admin=True)
    u2 = User(cognito_sub="d2", email="d2@example.com", name="D2", is_platform_admin=True)
    db_session.add_all([u1, u2])
    db_session.commit()
    db_session.refresh(u1)

    result = demote_from_platform_admin(u1.id, db_session)
    assert result.is_platform_admin is False


def test_demote_last_platform_admin_raises(db_session):
    sole_admin = User(cognito_sub="solo", email="solo@example.com",
                      name="Solo", is_platform_admin=True)
    db_session.add(sole_admin)
    db_session.commit()
    db_session.refresh(sole_admin)

    with pytest.raises(ValueError, match="Cannot remove the last platform administrator"):
        demote_from_platform_admin(sole_admin.id, db_session)


def test_demote_nonexistent_user_raises(db_session):
    with pytest.raises(ValueError, match="not found"):
        demote_from_platform_admin(uuid4(), db_session)


def test_demote_non_admin_is_safe(db_session):
    """Demoting a user who isn't platform admin should succeed (no-op guard)."""
    user = User(cognito_sub="nonadmin", email="na@example.com",
                name="NA", is_platform_admin=False)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    result = demote_from_platform_admin(user.id, db_session)
    assert result.is_platform_admin is False

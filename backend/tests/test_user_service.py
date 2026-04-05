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


@pytest.mark.asyncio
async def test_sync_creates_new_user(dual_session):
    sync_db, async_db = dual_session
    payload = SimpleNamespace(sub="cognito-abc", email="new@example.com", name="New User")
    user = await sync_user_from_cognito(payload, async_db)

    assert user.cognito_sub == "cognito-abc"
    assert user.email == "new@example.com"
    assert user.name == "New User"
    assert user.is_active is True


@pytest.mark.asyncio
async def test_sync_updates_existing_user_by_sub(dual_session):
    sync_db, async_db = dual_session
    existing = User(cognito_sub="cognito-xyz", email="old@example.com", name="Old")
    sync_db.add(existing)
    sync_db.commit()

    payload = SimpleNamespace(sub="cognito-xyz", email="updated@example.com", name="Updated")
    user = await sync_user_from_cognito(payload, async_db)

    assert user.id == existing.id
    assert user.email == "updated@example.com"
    assert user.name == "Updated"


@pytest.mark.asyncio
async def test_sync_handles_cognito_recreation_by_email(dual_session):
    """When a Cognito user is deleted and recreated with a new sub but same email."""
    sync_db, async_db = dual_session
    existing = User(cognito_sub="old-sub", email="same@example.com", name="Same")
    sync_db.add(existing)
    sync_db.commit()

    payload = SimpleNamespace(sub="new-sub", email="same@example.com", name="Same Updated")
    user = await sync_user_from_cognito(payload, async_db)

    assert user.id == existing.id
    assert user.cognito_sub == "new-sub"
    assert user.name == "Same Updated"


@pytest.mark.asyncio
async def test_sync_raises_when_email_missing():
    payload = SimpleNamespace(sub="some-sub", email=None, name="NoEmail")

    with pytest.raises(ValueError, match="Token missing email claim"):
        await sync_user_from_cognito(payload, None)


@pytest.mark.asyncio
async def test_sync_idempotent_no_change(dual_session):
    sync_db, async_db = dual_session
    existing = User(cognito_sub="sub-same", email="stable@example.com", name="Stable")
    sync_db.add(existing)
    sync_db.commit()

    payload = SimpleNamespace(sub="sub-same", email="stable@example.com", name="Stable")
    user = await sync_user_from_cognito(payload, async_db)

    assert user.id == existing.id
    assert user.email == "stable@example.com"


@pytest.mark.asyncio
async def test_sync_without_name_preserves_none(dual_session):
    sync_db, async_db = dual_session
    payload = SimpleNamespace(sub="sub-noname", email="noname@example.com", name=None)
    user = await sync_user_from_cognito(payload, async_db)

    assert user.email == "noname@example.com"
    assert user.name is None


# ── promote_to_platform_admin ────────────────────────────────────


@pytest.mark.asyncio
async def test_promote_to_platform_admin(dual_session):
    sync_db, async_db = dual_session
    user = User(cognito_sub="promo-sub", email="promo@example.com", name="P")
    sync_db.add(user)
    sync_db.commit()
    sync_db.refresh(user)

    result = await promote_to_platform_admin(user.id, async_db)
    assert result.is_platform_admin is True


@pytest.mark.asyncio
async def test_promote_nonexistent_user_raises(dual_session):
    sync_db, async_db = dual_session
    with pytest.raises(ValueError, match="not found"):
        await promote_to_platform_admin(uuid4(), async_db)


@pytest.mark.asyncio
async def test_promote_already_admin_is_idempotent(dual_session):
    sync_db, async_db = dual_session
    user = User(cognito_sub="admin-sub", email="admin@example.com",
                name="A", is_platform_admin=True)
    sync_db.add(user)
    sync_db.commit()
    sync_db.refresh(user)

    result = await promote_to_platform_admin(user.id, async_db)
    assert result.is_platform_admin is True


# ── demote_from_platform_admin ───────────────────────────────────


@pytest.mark.asyncio
async def test_demote_from_platform_admin(dual_session):
    sync_db, async_db = dual_session
    u1 = User(cognito_sub="d1", email="d1@example.com", name="D1", is_platform_admin=True)
    u2 = User(cognito_sub="d2", email="d2@example.com", name="D2", is_platform_admin=True)
    sync_db.add_all([u1, u2])
    sync_db.commit()
    sync_db.refresh(u1)

    result = await demote_from_platform_admin(u1.id, async_db)
    assert result.is_platform_admin is False


@pytest.mark.asyncio
async def test_demote_last_platform_admin_raises(dual_session):
    sync_db, async_db = dual_session
    sole_admin = User(cognito_sub="solo", email="solo@example.com",
                      name="Solo", is_platform_admin=True)
    sync_db.add(sole_admin)
    sync_db.commit()
    sync_db.refresh(sole_admin)

    with pytest.raises(ValueError, match="Cannot remove the last platform administrator"):
        await demote_from_platform_admin(sole_admin.id, async_db)


@pytest.mark.asyncio
async def test_demote_nonexistent_user_raises(dual_session):
    sync_db, async_db = dual_session
    with pytest.raises(ValueError, match="not found"):
        await demote_from_platform_admin(uuid4(), async_db)


@pytest.mark.asyncio
async def test_demote_non_admin_is_safe(dual_session):
    """Demoting a user who isn't platform admin should succeed (no-op guard)."""
    sync_db, async_db = dual_session
    user = User(cognito_sub="nonadmin", email="na@example.com",
                name="NA", is_platform_admin=False)
    sync_db.add(user)
    sync_db.commit()
    sync_db.refresh(user)

    result = await demote_from_platform_admin(user.id, async_db)
    assert result.is_platform_admin is False

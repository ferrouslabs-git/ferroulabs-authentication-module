"""Tests for Space service (Task 9).

Covers: create space, list user/account spaces, suspend/unsuspend lifecycle.
"""
from uuid import uuid4

import pytest

from app.auth_usermanagement.models.membership import Membership
from app.auth_usermanagement.models.space import Space
from app.auth_usermanagement.models.tenant import Tenant
from app.auth_usermanagement.services.space_service import (
    create_space,
    list_account_spaces,
    list_user_spaces,
    suspend_space,
    unsuspend_space,
)


# ── Tests using dual_session (sync setup + async service calls) ────────


class TestCreateSpace:
    @pytest.mark.asyncio
    async def test_create_space_returns_space_with_name(self, dual_session):
        sync_db, async_db = dual_session
        space = await create_space(async_db, "My Space", account_id=None, creator_user_id=uuid4())
        assert space.name == "My Space"
        assert space.status == "active"
        assert space.id is not None

    @pytest.mark.asyncio
    async def test_create_space_with_account_id(self, dual_session):
        sync_db, async_db = dual_session
        tenant = Tenant(name="Acme")
        sync_db.add(tenant)
        sync_db.commit()

        space = await create_space(async_db, "Team Space", account_id=tenant.id, creator_user_id=uuid4())
        assert space.account_id == tenant.id

    @pytest.mark.asyncio
    async def test_creator_gets_space_admin_membership(self, dual_session):
        sync_db, async_db = dual_session
        creator = uuid4()
        await create_space(async_db, "S1", account_id=None, creator_user_id=creator)
        await async_db.commit()

        sync_db.expire_all()
        membership = (
            sync_db.query(Membership)
            .filter(Membership.user_id == creator)
            .first()
        )
        assert membership is not None
        assert membership.scope_type == "space"
        assert membership.role_name == "space_admin"
        assert membership.status == "active"


class TestListSpaces:
    async def _setup_spaces(self, sync_db, async_db):
        """Create 2 spaces: user is member of space1, not space2."""
        tenant = Tenant(name="Acme")
        sync_db.add(tenant)
        sync_db.commit()

        user_id = uuid4()
        space1 = await create_space(async_db, "Alpha", account_id=tenant.id, creator_user_id=user_id)
        space2 = await create_space(async_db, "Beta", account_id=tenant.id, creator_user_id=uuid4())
        await async_db.commit()
        return user_id, tenant.id, space1, space2

    @pytest.mark.asyncio
    async def test_list_user_spaces_returns_only_member_spaces(self, dual_session):
        sync_db, async_db = dual_session
        user_id, _, space1, space2 = await self._setup_spaces(sync_db, async_db)
        spaces = await list_user_spaces(async_db, user_id)

        ids = [s.id for s in spaces]
        assert space1.id in ids
        assert space2.id not in ids

    @pytest.mark.asyncio
    async def test_list_account_spaces_returns_all_account_spaces(self, dual_session):
        sync_db, async_db = dual_session
        _, account_id, space1, space2 = await self._setup_spaces(sync_db, async_db)
        spaces = await list_account_spaces(async_db, account_id)

        ids = [s.id for s in spaces]
        assert space1.id in ids
        assert space2.id in ids

    @pytest.mark.asyncio
    async def test_list_account_spaces_excludes_other_account(self, dual_session):
        sync_db, async_db = dual_session
        t1 = Tenant(name="T1")
        t2 = Tenant(name="T2")
        sync_db.add_all([t1, t2])
        sync_db.commit()

        await create_space(async_db, "S-T1", account_id=t1.id, creator_user_id=uuid4())
        await create_space(async_db, "S-T2", account_id=t2.id, creator_user_id=uuid4())
        await async_db.commit()

        spaces = await list_account_spaces(async_db, t1.id)
        assert all(s.account_id == t1.id for s in spaces)
        assert len(spaces) == 1


class TestSuspendUnsuspend:
    @pytest.mark.asyncio
    async def test_suspend_space(self, dual_session):
        sync_db, async_db = dual_session
        space = await create_space(async_db, "S", account_id=None, creator_user_id=uuid4())
        suspended = await suspend_space(async_db, space.id)

        assert suspended.status == "suspended"
        assert suspended.suspended_at is not None

    @pytest.mark.asyncio
    async def test_suspend_already_suspended_raises(self, dual_session):
        sync_db, async_db = dual_session
        space = await create_space(async_db, "S", account_id=None, creator_user_id=uuid4())
        await suspend_space(async_db, space.id)

        with pytest.raises(ValueError, match="already suspended"):
            await suspend_space(async_db, space.id)

    @pytest.mark.asyncio
    async def test_unsuspend_space(self, dual_session):
        sync_db, async_db = dual_session
        space = await create_space(async_db, "S", account_id=None, creator_user_id=uuid4())
        await suspend_space(async_db, space.id)
        active = await unsuspend_space(async_db, space.id)

        assert active.status == "active"
        assert active.suspended_at is None

    @pytest.mark.asyncio
    async def test_unsuspend_active_space_raises(self, dual_session):
        sync_db, async_db = dual_session
        space = await create_space(async_db, "S", account_id=None, creator_user_id=uuid4())

        with pytest.raises(ValueError, match="not suspended"):
            await unsuspend_space(async_db, space.id)

    @pytest.mark.asyncio
    async def test_suspend_nonexistent_raises(self, dual_session):
        sync_db, async_db = dual_session
        with pytest.raises(ValueError, match="not found"):
            await suspend_space(async_db, uuid4())

    @pytest.mark.asyncio
    async def test_unsuspend_nonexistent_raises(self, dual_session):
        sync_db, async_db = dual_session
        with pytest.raises(ValueError, match="not found"):
            await unsuspend_space(async_db, uuid4())


class TestSpaceEdgeCases:
    @pytest.mark.asyncio
    async def test_create_space_without_account_id(self, dual_session):
        """Standalone space (no parent account) works fine."""
        sync_db, async_db = dual_session
        space = await create_space(async_db, "Standalone", account_id=None, creator_user_id=uuid4())
        assert space.account_id is None
        assert space.status == "active"

    @pytest.mark.asyncio
    async def test_list_user_spaces_empty_for_no_memberships(self, dual_session):
        sync_db, async_db = dual_session
        spaces = await list_user_spaces(async_db, uuid4())
        assert spaces == []

    @pytest.mark.asyncio
    async def test_list_account_spaces_empty_for_unknown_account(self, dual_session):
        sync_db, async_db = dual_session
        spaces = await list_account_spaces(async_db, uuid4())
        assert spaces == []

    @pytest.mark.asyncio
    async def test_list_user_spaces_excludes_removed_membership(self, dual_session):
        sync_db, async_db = dual_session
        creator = uuid4()
        await create_space(async_db, "S", account_id=None, creator_user_id=creator)
        await async_db.commit()

        # Remove the membership via sync
        sync_db.expire_all()
        m = sync_db.query(Membership).filter(
            Membership.user_id == creator
        ).first()
        m.status = "removed"
        sync_db.commit()

        spaces = await list_user_spaces(async_db, creator)
        assert spaces == []

    @pytest.mark.asyncio
    async def test_suspend_then_unsuspend_restores_state(self, dual_session):
        """Full lifecycle: active → suspended → active."""
        sync_db, async_db = dual_session
        space = await create_space(async_db, "SLC", account_id=None, creator_user_id=uuid4())
        await suspend_space(async_db, space.id)
        restored = await unsuspend_space(async_db, space.id)

        assert restored.status == "active"
        assert restored.suspended_at is None

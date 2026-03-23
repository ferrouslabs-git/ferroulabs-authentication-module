"""Tests for Space service (Task 9).

Covers: create space, list user/account spaces, suspend/unsuspend lifecycle.
"""
from uuid import uuid4

import pytest

from app.auth_usermanagement.models.membership import Membership
from app.auth_usermanagement.models.space import Space
from app.auth_usermanagement.services.space_service import (
    create_space,
    list_account_spaces,
    list_user_spaces,
    suspend_space,
    unsuspend_space,
)


# ── Tests using real SQLite session (conftest.db_session) ────────


class TestCreateSpace:
    def test_create_space_returns_space_with_name(self, db_session):
        space = create_space(db_session, "My Space", account_id=None, creator_user_id=uuid4())
        assert space.name == "My Space"
        assert space.status == "active"
        assert space.id is not None

    def test_create_space_with_account_id(self, db_session):
        from app.auth_usermanagement.models.tenant import Tenant

        tenant = Tenant(name="Acme")
        db_session.add(tenant)
        db_session.commit()

        space = create_space(db_session, "Team Space", account_id=tenant.id, creator_user_id=uuid4())
        assert space.account_id == tenant.id

    def test_creator_gets_space_admin_membership(self, db_session):
        creator = uuid4()
        space = create_space(db_session, "S1", account_id=None, creator_user_id=creator)

        membership = (
            db_session.query(Membership)
            .filter(Membership.user_id == creator, Membership.scope_id == space.id)
            .first()
        )
        assert membership is not None
        assert membership.scope_type == "space"
        assert membership.role_name == "space_admin"
        assert membership.status == "active"


class TestListSpaces:
    def _setup_spaces(self, db_session):
        """Create 2 spaces: user is member of space1, not space2."""
        from app.auth_usermanagement.models.tenant import Tenant

        tenant = Tenant(name="Acme")
        db_session.add(tenant)
        db_session.commit()

        user_id = uuid4()
        space1 = create_space(db_session, "Alpha", account_id=tenant.id, creator_user_id=user_id)
        space2 = create_space(db_session, "Beta", account_id=tenant.id, creator_user_id=uuid4())
        return user_id, tenant.id, space1, space2

    def test_list_user_spaces_returns_only_member_spaces(self, db_session):
        user_id, _, space1, space2 = self._setup_spaces(db_session)
        spaces = list_user_spaces(db_session, user_id)

        ids = [s.id for s in spaces]
        assert space1.id in ids
        assert space2.id not in ids

    def test_list_account_spaces_returns_all_account_spaces(self, db_session):
        _, account_id, space1, space2 = self._setup_spaces(db_session)
        spaces = list_account_spaces(db_session, account_id)

        ids = [s.id for s in spaces]
        assert space1.id in ids
        assert space2.id in ids

    def test_list_account_spaces_excludes_other_account(self, db_session):
        from app.auth_usermanagement.models.tenant import Tenant

        t1 = Tenant(name="T1")
        t2 = Tenant(name="T2")
        db_session.add_all([t1, t2])
        db_session.commit()

        create_space(db_session, "S-T1", account_id=t1.id, creator_user_id=uuid4())
        create_space(db_session, "S-T2", account_id=t2.id, creator_user_id=uuid4())

        spaces = list_account_spaces(db_session, t1.id)
        assert all(s.account_id == t1.id for s in spaces)
        assert len(spaces) == 1


class TestSuspendUnsuspend:
    def test_suspend_space(self, db_session):
        space = create_space(db_session, "S", account_id=None, creator_user_id=uuid4())
        suspended = suspend_space(db_session, space.id)

        assert suspended.status == "suspended"
        assert suspended.suspended_at is not None

    def test_suspend_already_suspended_raises(self, db_session):
        space = create_space(db_session, "S", account_id=None, creator_user_id=uuid4())
        suspend_space(db_session, space.id)

        with pytest.raises(ValueError, match="already suspended"):
            suspend_space(db_session, space.id)

    def test_unsuspend_space(self, db_session):
        space = create_space(db_session, "S", account_id=None, creator_user_id=uuid4())
        suspend_space(db_session, space.id)
        active = unsuspend_space(db_session, space.id)

        assert active.status == "active"
        assert active.suspended_at is None

    def test_unsuspend_active_space_raises(self, db_session):
        space = create_space(db_session, "S", account_id=None, creator_user_id=uuid4())

        with pytest.raises(ValueError, match="not suspended"):
            unsuspend_space(db_session, space.id)

    def test_suspend_nonexistent_raises(self, db_session):
        with pytest.raises(ValueError, match="not found"):
            suspend_space(db_session, uuid4())

    def test_unsuspend_nonexistent_raises(self, db_session):
        with pytest.raises(ValueError, match="not found"):
            unsuspend_space(db_session, uuid4())


class TestSpaceEdgeCases:
    def test_create_space_without_account_id(self, db_session):
        """Standalone space (no parent account) works fine."""
        space = create_space(db_session, "Standalone", account_id=None, creator_user_id=uuid4())
        assert space.account_id is None
        assert space.status == "active"

    def test_list_user_spaces_empty_for_no_memberships(self, db_session):
        spaces = list_user_spaces(db_session, uuid4())
        assert spaces == []

    def test_list_account_spaces_empty_for_unknown_account(self, db_session):
        spaces = list_account_spaces(db_session, uuid4())
        assert spaces == []

    def test_list_user_spaces_excludes_removed_membership(self, db_session):
        creator = uuid4()
        space = create_space(db_session, "S", account_id=None, creator_user_id=creator)

        # Remove the membership
        m = db_session.query(Membership).filter(
            Membership.user_id == creator, Membership.scope_id == space.id
        ).first()
        m.status = "removed"
        db_session.commit()

        spaces = list_user_spaces(db_session, creator)
        assert spaces == []

    def test_suspend_then_unsuspend_restores_state(self, db_session):
        """Full lifecycle: active → suspended → active."""
        space = create_space(db_session, "SLC", account_id=None, creator_user_id=uuid4())
        suspend_space(db_session, space.id)
        restored = unsuspend_space(db_session, space.id)

        assert restored.status == "active"
        assert restored.suspended_at is None

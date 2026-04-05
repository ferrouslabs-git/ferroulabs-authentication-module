"""Tests for scoped invitation flow (Task 8).

Covers: account-scope invite, space-scope invite, invite authority
validation, accept creates scoped membership, legacy default fallback.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

from app.auth_usermanagement.models.invitation import Invitation
from app.auth_usermanagement.models.membership import Membership
from app.auth_usermanagement.services.invitation_service import (
    accept_invitation,
    create_invitation,
)


# ── Fake DB helpers ──────────────────────────────────────────────

class _FakeResult:
    """Mimics SQLAlchemy CursorResult."""
    def __init__(self, rows):
        self._rows = rows if isinstance(rows, list) else ([rows] if rows is not None else [])

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _FakeSession:
    def __init__(self, membership_result=None, pending_invites=None):
        self.membership_result = membership_result
        self.pending_invites = pending_invites or []
        self.added = []
        self.commits = 0
        self.refreshed = []

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1

    async def flush(self):
        pass

    async def refresh(self, obj, attribute_names=None):
        self.refreshed.append(obj)

    async def execute(self, stmt, *args, **kwargs):
        stmt_str = str(stmt)
        if "invitation" in stmt_str.lower():
            return _FakeResult(self.pending_invites)
        if "membership" in stmt_str.lower():
            return _FakeResult(self.membership_result)
        return _FakeResult(None)


# ── Test helpers ─────────────────────────────────────────────────

def _make_invitation(**overrides):
    defaults = dict(
        id=uuid4(),
        tenant_id=uuid4(),
        email="user@example.com",
        token="tok",
        expires_at=_utcnow() + timedelta(days=7),
        created_by=uuid4(),
        target_scope_type="account",
        target_scope_id=uuid4(),
        target_role_name="account_member",
    )
    defaults.update(overrides)
    return Invitation(**defaults)


# ── Create invitation: scope columns ────────────────────────────

class TestCreateScopedInvitation:
    @pytest.mark.asyncio
    async def test_account_scope_invite(self):
        """Account-scope invite creates invitation with target_scope_type=account."""
        db = _FakeSession()
        tenant_id = uuid4()

        inv = (await create_invitation(
            db=db,
            tenant_id=tenant_id,
            email="a@example.com",
            role="admin",
            created_by=uuid4(),
            target_scope_type="account",
            target_scope_id=tenant_id,
            target_role_name="account_admin",
        ))[0]

        assert inv.target_scope_type == "account"
        assert inv.target_scope_id == tenant_id
        assert inv.target_role_name == "account_admin"

    @pytest.mark.asyncio
    async def test_space_scope_invite(self):
        """Space-scope invite creates invitation with target_scope_type=space."""
        db = _FakeSession()
        tenant_id = uuid4()
        space_id = uuid4()

        inv = (await create_invitation(
            db=db,
            tenant_id=tenant_id,
            email="b@example.com",
            role="member",
            created_by=uuid4(),
            target_scope_type="space",
            target_scope_id=space_id,
            target_role_name="space_member",
        ))[0]

        assert inv.target_scope_type == "space"
        assert inv.target_scope_id == space_id
        assert inv.target_role_name == "space_member"

    @pytest.mark.asyncio
    async def test_legacy_invite_defaults_to_account_scope(self):
        """Legacy invite (no scope fields) defaults to account scope."""
        db = _FakeSession()
        tenant_id = uuid4()

        inv = (await create_invitation(
            db=db,
            tenant_id=tenant_id,
            email="c@example.com",
            role="member",
            created_by=uuid4(),
        ))[0]

        assert inv.target_scope_type == "account"
        assert inv.target_scope_id == tenant_id
        assert inv.target_role_name == "account_member"


# ── Invite authority (route_helpers level) ───────────────────────

class TestInviteAuthority:
    """Authority checks are enforced in create_invitation_response. We test
    the permission comparison logic used by the helper via the config."""

    def test_admin_cannot_invite_owner(self):
        """account_admin permissions are a subset of account_owner, so
        account_admin cannot invite to account_owner role."""
        from app.auth_usermanagement.services.auth_config_loader import get_auth_config

        config = get_auth_config()
        admin_perms = config.permissions_for_role("account_admin")
        owner_perms = config.permissions_for_role("account_owner")

        # owner has permissions that admin doesn't → admin can't invite owner
        assert not owner_perms.issubset(admin_perms)

    def test_owner_can_invite_admin(self):
        """account_owner holds superset of account_admin permissions."""
        from app.auth_usermanagement.services.auth_config_loader import get_auth_config

        config = get_auth_config()
        admin_perms = config.permissions_for_role("account_admin")
        owner_perms = config.permissions_for_role("account_owner")

        assert admin_perms.issubset(owner_perms)

    def test_space_admin_can_invite_space_member(self):
        """space_admin holds superset of space_member permissions."""
        from app.auth_usermanagement.services.auth_config_loader import get_auth_config

        config = get_auth_config()
        admin_perms = config.permissions_for_role("space_admin")
        member_perms = config.permissions_for_role("space_member")

        assert member_perms.issubset(admin_perms)


# ── Accept invitation: scoped membership ─────────────────────────

class TestAcceptScopedInvitation:
    @pytest.mark.asyncio
    async def test_accept_creates_account_scoped_membership(self):
        """Accept invitation creates membership with scope_type=account."""
        db = _FakeSession(membership_result=None)
        inv = _make_invitation(
            email="new@example.com",
            target_scope_type="account",
            target_scope_id=uuid4(),
            target_role_name="account_admin",
        )
        user = SimpleNamespace(id=uuid4(), email="new@example.com")

        membership = await accept_invitation(db, inv, user)

        assert membership.scope_type == "account"
        assert membership.scope_id == inv.target_scope_id
        assert membership.role_name == "account_admin"
        assert membership.status == "active"

    @pytest.mark.asyncio
    async def test_accept_creates_space_scoped_membership(self):
        """Accept invitation in space scope creates scope_type=space membership."""
        db = _FakeSession(membership_result=None)
        space_id = uuid4()
        inv = _make_invitation(
            email="space@example.com",
            target_scope_type="space",
            target_scope_id=space_id,
            target_role_name="space_member",
        )
        user = SimpleNamespace(id=uuid4(), email="space@example.com")

        membership = await accept_invitation(db, inv, user)

        assert membership.scope_type == "space"
        assert membership.scope_id == space_id
        assert membership.role_name == "space_member"
        assert membership.status == "active"

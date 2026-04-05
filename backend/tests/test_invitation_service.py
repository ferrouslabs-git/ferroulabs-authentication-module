"""Unit tests for invitation lifecycle service behavior."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

import pytest

from app.auth_usermanagement.models.invitation import Invitation
from app.auth_usermanagement.models.membership import Membership
from app.auth_usermanagement.services.invitation_service import (
    accept_invitation,
    create_invitation,
    resend_invitation,
    revoke_invitation,
)


class _FakeResult:
    """Mimics SQLAlchemy CursorResult for select queries."""
    def __init__(self, rows):
        self._rows = rows if isinstance(rows, list) else ([rows] if rows is not None else [])

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None

    def scalar_one(self):
        if not self._rows:
            raise Exception("No rows")
        return self._rows[0]

    def scalars(self):
        return self

    def all(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None


class _FakeSession:
    """Async-compatible fake session for unit tests."""
    def __init__(self, membership_result=None):
        self.membership_result = membership_result
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
        """Route selects based on model being queried."""
        # Inspect the statement to figure out which model is being queried
        stmt_str = str(stmt)
        if "membership" in stmt_str.lower():
            return _FakeResult(self.membership_result)
        return _FakeResult(None)


class _InviteCreateSession(_FakeSession):
    def __init__(self, pending_invites=None):
        super().__init__(membership_result=None)
        self.pending_invites = pending_invites or []

    async def execute(self, stmt, *args, **kwargs):
        stmt_str = str(stmt)
        if "invitation" in stmt_str.lower():
            return _FakeResult(self.pending_invites)
        return await super().execute(stmt, *args, **kwargs)


def _invitation(email: str = "user@example.com", role_name: str = "account_member", days: int = 7, accepted: bool = False):
    inv = Invitation(
        id=uuid4(),
        tenant_id=uuid4(),
        email=email,
        token="tok",
        expires_at=_utcnow() + timedelta(days=days),
        created_by=uuid4(),
        target_scope_type="account",
        target_scope_id=uuid4(),
        target_role_name=role_name,
    )
    if accepted:
        inv.accepted_at = _utcnow()
    return inv


@pytest.mark.asyncio
async def test_create_invitation_normalizes_email_and_persists():
    db = _InviteCreateSession()
    tenant_id = uuid4()
    creator = uuid4()

    invitation, raw_token = await create_invitation(
        db=db,
        tenant_id=tenant_id,
        email="  PERSON@Example.COM  ",
        role="viewer",
        created_by=creator,
        expires_in_days=3,
    )

    assert invitation.email == "person@example.com"
    assert invitation.tenant_id == tenant_id
    assert invitation.created_by == creator
    assert invitation.target_role_name == "account_member"
    assert invitation.token
    assert raw_token  # raw token is returned separately
    assert invitation.token != raw_token  # DB stores hash, not plaintext
    assert db.commits == 1
    assert invitation in db.added


@pytest.mark.asyncio
async def test_create_invitation_expires_previous_pending_for_same_email_and_tenant():
    tenant_id = uuid4()
    pending = Invitation(
        id=uuid4(),
        tenant_id=tenant_id,
        email="person@example.com",
        target_role_name="account_member",
        token="old",
        expires_at=_utcnow() + timedelta(days=5),
        created_by=uuid4(),
    )
    original_expiry = pending.expires_at
    db = _InviteCreateSession(pending_invites=[pending])

    invitation = (await create_invitation(
        db=db,
        tenant_id=tenant_id,
        email="PERSON@example.com",
        role="admin",
        created_by=uuid4(),
    ))[0]  # unpack invitation from tuple

    assert pending.expires_at <= _utcnow()
    assert pending.expires_at < original_expiry
    assert invitation.token != pending.token
    assert db.commits == 1


@pytest.mark.asyncio
async def test_accept_invitation_rejects_expired_token():
    db = _FakeSession()
    invitation = _invitation(days=-1)
    user = SimpleNamespace(id=uuid4(), email="user@example.com")

    with pytest.raises(ValueError, match="expired"):
        await accept_invitation(db, invitation, user)


@pytest.mark.asyncio
async def test_accept_invitation_rejects_email_mismatch():
    db = _FakeSession()
    invitation = _invitation(email="invited@example.com")
    user = SimpleNamespace(id=uuid4(), email="other@example.com")

    with pytest.raises(PermissionError, match="does not match"):
        await accept_invitation(db, invitation, user)


@pytest.mark.asyncio
async def test_accept_invitation_rejects_revoked_invitation():
    db = _FakeSession()
    invitation = _invitation()
    invitation.revoked_at = _utcnow()
    user = SimpleNamespace(id=uuid4(), email="user@example.com")

    with pytest.raises(ValueError, match="revoked"):
        await accept_invitation(db, invitation, user)


@pytest.mark.asyncio
async def test_accept_invitation_reactivates_existing_membership_without_downgrade():
    existing = Membership(
        user_id=uuid4(),
        scope_type="account",
        scope_id=uuid4(),
        role_name="account_owner",
        status="removed",
    )
    db = _FakeSession(membership_result=existing)

    invitation = Invitation(
        id=uuid4(),
        tenant_id=uuid4(),
        email="user@example.com",
        token="tok",
        expires_at=_utcnow() + timedelta(days=1),
        created_by=uuid4(),
        target_scope_type="account",
        target_scope_id=existing.scope_id,
        target_role_name="account_member",
    )
    user = SimpleNamespace(id=existing.user_id, email="user@example.com")

    membership = await accept_invitation(db, invitation, user)

    assert membership is existing
    assert membership.role_name == "account_owner"
    assert membership.status == "active"
    assert invitation.accepted_at is not None
    assert db.commits == 1


@pytest.mark.asyncio
async def test_accept_invitation_creates_membership_for_new_user():
    db = _FakeSession(membership_result=None)
    invitation = _invitation(email="new@example.com", role_name="account_admin")
    user = SimpleNamespace(id=uuid4(), email="new@example.com")

    membership = await accept_invitation(db, invitation, user)

    assert membership.user_id == user.id
    assert membership.scope_type == "account"
    assert membership.role_name == "account_admin"
    assert membership.status == "active"
    assert invitation.accepted_at is not None
    assert db.commits == 1
    assert any(isinstance(obj, Membership) for obj in db.added)


@pytest.mark.asyncio
async def test_revoke_invitation_marks_pending_invitation_revoked():
    db = _FakeSession()
    invitation = _invitation()

    result = await revoke_invitation(db, invitation)

    assert result is invitation
    assert invitation.revoked_at is not None
    assert invitation.is_revoked
    assert invitation.status == "revoked"
    assert db.commits == 1


@pytest.mark.asyncio
async def test_revoke_invitation_rejects_accepted_invitation():
    db = _FakeSession()
    invitation = _invitation(accepted=True)

    with pytest.raises(ValueError, match="cannot be revoked"):
        await revoke_invitation(db, invitation)


# ── Corner cases ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_revoke_already_revoked_invitation_raises():
    db = _FakeSession()
    invitation = _invitation()
    invitation.revoked_at = _utcnow()

    with pytest.raises(ValueError, match="already revoked"):
        await revoke_invitation(db, invitation)


@pytest.mark.asyncio
async def test_accept_already_accepted_invitation_raises():
    db = _FakeSession()
    invitation = _invitation(accepted=True)
    user = SimpleNamespace(id=uuid4(), email="user@example.com")

    with pytest.raises(ValueError, match="already been accepted"):
        await accept_invitation(db, invitation, user)


@pytest.mark.asyncio
async def test_accept_invitation_upgrades_when_invited_role_has_more_permissions():
    """When the invited role has permissions not in the existing role, upgrade."""
    existing = Membership(
        user_id=uuid4(),
        scope_type="account",
        scope_id=uuid4(),
        role_name="account_member",
        status="active",
    )
    db = _FakeSession(membership_result=existing)

    invitation = Invitation(
        id=uuid4(),
        tenant_id=uuid4(),
        email="user@example.com",
        token="tok",
        expires_at=_utcnow() + timedelta(days=1),
        created_by=uuid4(),
        target_scope_type="account",
        target_scope_id=existing.scope_id,
        target_role_name="account_admin",
    )
    user = SimpleNamespace(id=existing.user_id, email="user@example.com")

    membership = await accept_invitation(db, invitation, user)

    # account_admin has permissions not in account_member → upgrade
    assert membership.role_name == "account_admin"


@pytest.mark.asyncio
async def test_create_invitation_derives_scope_from_legacy_role():
    """When target_scope_type is not provided, defaults to account scope."""
    db = _InviteCreateSession()
    tenant_id = uuid4()

    invitation = (await create_invitation(
        db=db, tenant_id=tenant_id, email="test@example.com",
        role="admin", created_by=uuid4(),
    ))[0]

    assert invitation.target_scope_type == "account"
    assert invitation.target_scope_id == tenant_id
    assert invitation.target_role_name == "account_admin"


@pytest.mark.asyncio
async def test_create_invitation_respects_explicit_scope():
    """Explicit target_scope_type/id/role_name overrides legacy defaults."""
    db = _InviteCreateSession()
    tenant_id = uuid4()
    space_id = uuid4()

    invitation = (await create_invitation(
        db=db, tenant_id=tenant_id, email="test@example.com",
        role="member", created_by=uuid4(),
        target_scope_type="space",
        target_scope_id=space_id,
        target_role_name="space_admin",
    ))[0]

    assert invitation.target_scope_type == "space"
    assert invitation.target_scope_id == space_id
    assert invitation.target_role_name == "space_admin"


@pytest.mark.asyncio
async def test_create_invitation_token_is_unique():
    """Each invitation gets a unique token."""
    db = _InviteCreateSession()
    tid = uuid4()
    creator = uuid4()

    inv1, tok1 = await create_invitation(db=db, tenant_id=tid, email="a@example.com",
                             role="member", created_by=creator)
    inv2, tok2 = await create_invitation(db=db, tenant_id=tid, email="b@example.com",
                             role="member", created_by=creator)

    assert tok1 != tok2
    assert inv1.token_hash != inv2.token_hash
    assert inv1.token == inv1.token_hash  # DB stores hash, not plaintext


# ── Resend invitation ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_resend_invitation_generates_new_token_and_extends_expiry():
    db = _FakeSession()
    invitation = _invitation(days=1)
    old_token = invitation.token
    old_expiry = invitation.expires_at

    result, raw_token = await resend_invitation(db, invitation, expires_in_days=5)

    assert result is invitation
    assert raw_token  # new raw token returned
    assert invitation.token != old_token  # token replaced
    assert invitation.token_hash == invitation.token  # both columns updated
    assert invitation.expires_at > old_expiry  # expiry extended
    assert db.commits == 1


@pytest.mark.asyncio
async def test_resend_invitation_works_on_expired_invitation():
    db = _FakeSession()
    invitation = _invitation(days=-1)  # already expired
    assert invitation.is_expired

    result, raw_token = await resend_invitation(db, invitation, expires_in_days=3)

    assert not result.is_expired  # no longer expired
    assert raw_token
    assert db.commits == 1


@pytest.mark.asyncio
async def test_resend_invitation_rejects_accepted_invitation():
    db = _FakeSession()
    invitation = _invitation(accepted=True)

    with pytest.raises(ValueError, match="cannot be resent"):
        await resend_invitation(db, invitation)


@pytest.mark.asyncio
async def test_resend_invitation_rejects_revoked_invitation():
    db = _FakeSession()
    invitation = _invitation()
    invitation.revoked_at = _utcnow()

    with pytest.raises(ValueError, match="cannot be resent"):
        await resend_invitation(db, invitation)


@pytest.mark.asyncio
async def test_resend_invitation_invalidates_old_token():
    db = _FakeSession()
    invitation = _invitation()
    old_hash = invitation.token_hash

    _, new_raw = await resend_invitation(db, invitation)

    from app.auth_usermanagement.services.invitation_service import hash_token
    assert invitation.token_hash == hash_token(new_raw)
    assert invitation.token_hash != old_hash

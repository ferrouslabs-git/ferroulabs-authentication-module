"""Unit tests for invitation lifecycle service behavior."""
from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.auth_usermanagement.models.invitation import Invitation
from app.auth_usermanagement.models.membership import Membership
from app.auth_usermanagement.services.invitation_service import accept_invitation, create_invitation


class _FakeQuery:
    def __init__(self, result):
        self._result = result

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._result


class _FakeSession:
    def __init__(self, membership_result=None):
        self.membership_result = membership_result
        self.added = []
        self.commits = 0
        self.refreshed = []

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.commits += 1

    def refresh(self, obj):
        self.refreshed.append(obj)

    def query(self, model):
        if model is Membership:
            return _FakeQuery(self.membership_result)
        return _FakeQuery(None)


def _invitation(email: str = "user@example.com", role: str = "member", days: int = 7, accepted: bool = False):
    inv = Invitation(
        id=uuid4(),
        tenant_id=uuid4(),
        email=email,
        role=role,
        token="tok",
        expires_at=datetime.utcnow() + timedelta(days=days),
        created_by=uuid4(),
    )
    if accepted:
        inv.accepted_at = datetime.utcnow()
    return inv


def test_create_invitation_normalizes_email_and_persists():
    db = _FakeSession()
    tenant_id = uuid4()
    creator = uuid4()

    invitation = create_invitation(
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
    assert invitation.role == "viewer"
    assert invitation.token
    assert db.commits == 1
    assert invitation in db.added


def test_accept_invitation_rejects_expired_token():
    db = _FakeSession()
    invitation = _invitation(days=-1)
    user = SimpleNamespace(id=uuid4(), email="user@example.com")

    with pytest.raises(ValueError, match="expired"):
        accept_invitation(db, invitation, user)


def test_accept_invitation_rejects_email_mismatch():
    db = _FakeSession()
    invitation = _invitation(email="invited@example.com")
    user = SimpleNamespace(id=uuid4(), email="other@example.com")

    with pytest.raises(PermissionError, match="does not match"):
        accept_invitation(db, invitation, user)


def test_accept_invitation_reactivates_existing_membership_without_downgrade():
    existing = Membership(
        user_id=uuid4(),
        tenant_id=uuid4(),
        role="owner",
        status="removed",
    )
    db = _FakeSession(membership_result=existing)

    invitation = Invitation(
        id=uuid4(),
        tenant_id=existing.tenant_id,
        email="user@example.com",
        role="member",
        token="tok",
        expires_at=datetime.utcnow() + timedelta(days=1),
        created_by=uuid4(),
    )
    user = SimpleNamespace(id=existing.user_id, email="user@example.com")

    membership = accept_invitation(db, invitation, user)

    assert membership is existing
    assert membership.role == "owner"
    assert membership.status == "active"
    assert invitation.accepted_at is not None
    assert db.commits == 1


def test_accept_invitation_creates_membership_for_new_user():
    db = _FakeSession(membership_result=None)
    invitation = _invitation(email="new@example.com", role="admin")
    user = SimpleNamespace(id=uuid4(), email="new@example.com")

    membership = accept_invitation(db, invitation, user)

    assert membership.user_id == user.id
    assert membership.tenant_id == invitation.tenant_id
    assert membership.role == "admin"
    assert membership.status == "active"
    assert invitation.accepted_at is not None
    assert db.commits == 1
    assert any(isinstance(obj, Membership) for obj in db.added)

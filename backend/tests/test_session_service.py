"""Unit tests for session lifecycle service."""
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from app.auth_usermanagement.services.session_service import (
    create_user_session,
    revoke_all_user_sessions,
    revoke_user_session,
    rotate_user_session,
    validate_refresh_session,
)
from app.auth_usermanagement.models.session import Session as AuthSession


class _FakeQuery:
    def __init__(self, first_result=None, all_results=None):
        self._first = first_result
        self._all = all_results or []

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._first

    def all(self):
        return self._all


class _FakeSession:
    def __init__(self, first_result=None, all_results=None):
        self._query = _FakeQuery(first_result=first_result, all_results=all_results)
        self.commits = 0
        self.refreshed = []
        self.added = []

    def query(self, _model):
        return self._query

    def commit(self):
        self.commits += 1

    def refresh(self, obj):
        self.refreshed.append(obj)

    def add(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = uuid4()
        self.added.append(obj)


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def test_create_user_session_persists_hashed_refresh_token_and_metadata():
    db = _FakeSession()
    user_id = uuid4()
    expires_at = utc_now() + timedelta(hours=2)

    created = create_user_session(
        db,
        user_id,
        "plain-refresh-token-value",
        user_agent="pytest-agent",
        ip_address="10.0.0.2",
        device_info="test-device",
        expires_at=expires_at,
    )

    assert created.user_id == user_id
    assert created.refresh_token_hash != "plain-refresh-token-value"
    assert created.user_agent == "pytest-agent"
    assert created.ip_address == "10.0.0.2"
    assert created.device_info == "test-device"
    assert created.expires_at == expires_at
    assert db.commits == 1
    assert created in db.refreshed


def test_validate_refresh_session_accepts_active_matching_hash():
    session_obj = SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
        refresh_token_hash=create_user_session.__globals__["_hash_refresh_token"]("token-1234567890"),
        revoked_at=None,
        expires_at=utc_now() + timedelta(minutes=30),
    )
    db = _FakeSession(first_result=session_obj)

    result = validate_refresh_session(db, session_obj.user_id, session_obj.id, "token-1234567890")

    assert result is session_obj


def test_validate_refresh_session_rejects_expired_or_wrong_token():
    session_obj = SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
        refresh_token_hash=create_user_session.__globals__["_hash_refresh_token"]("token-abcdefghij"),
        revoked_at=None,
        expires_at=utc_now() - timedelta(seconds=1),
    )
    db = _FakeSession(first_result=session_obj)

    assert validate_refresh_session(db, session_obj.user_id, session_obj.id, "token-abcdefghij") is None

    session_obj.expires_at = utc_now() + timedelta(minutes=10)
    assert validate_refresh_session(db, session_obj.user_id, session_obj.id, "wrong-token-value") is None


def test_rotate_user_session_revokes_old_and_creates_new():
    old_session = SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
        refresh_token_hash=create_user_session.__globals__["_hash_refresh_token"]("old-token-value-123"),
        revoked_at=None,
        expires_at=utc_now() + timedelta(hours=1),
        user_agent="ua-old",
        ip_address="127.0.0.1",
        device_info="device-old",
    )
    db = _FakeSession(first_result=old_session)

    rotated = rotate_user_session(
        db,
        user_id=old_session.user_id,
        session_id=old_session.id,
        old_refresh_token="old-token-value-123",
        new_refresh_token="new-token-value-456",
    )

    assert old_session.revoked_at is not None
    assert isinstance(rotated, AuthSession)
    assert rotated.user_id == old_session.user_id
    assert rotated.refresh_token_hash != old_session.refresh_token_hash
    assert db.commits == 1


def test_rotate_user_session_returns_none_when_validation_fails():
    db = _FakeSession(first_result=None)

    rotated = rotate_user_session(
        db,
        user_id=uuid4(),
        session_id=uuid4(),
        old_refresh_token="missing-old-token",
        new_refresh_token="new-token-value-456",
    )

    assert rotated is None
    assert db.commits == 0


def test_revoke_user_session_returns_none_when_missing():
    db = _FakeSession(first_result=None)

    result = revoke_user_session(db, uuid4(), uuid4())

    assert result is None
    assert db.commits == 0


def test_revoke_user_session_sets_revoked_at():
    session_obj = SimpleNamespace(id=uuid4(), revoked_at=None)
    db = _FakeSession(first_result=session_obj)

    result = revoke_user_session(db, uuid4(), session_obj.id)

    assert result is session_obj
    assert isinstance(result.revoked_at, datetime)
    assert db.commits == 1
    assert session_obj in db.refreshed


def test_revoke_all_user_sessions_returns_zero_when_empty():
    db = _FakeSession(all_results=[])

    count = revoke_all_user_sessions(db, uuid4())

    assert count == 0
    assert db.commits == 0


def test_revoke_all_user_sessions_revokes_each_active_session():
    s1 = SimpleNamespace(id=uuid4(), revoked_at=None)
    s2 = SimpleNamespace(id=uuid4(), revoked_at=None)
    db = _FakeSession(all_results=[s1, s2])

    count = revoke_all_user_sessions(db, uuid4())

    assert count == 2
    assert isinstance(s1.revoked_at, datetime)
    assert isinstance(s2.revoked_at, datetime)
    assert db.commits == 1

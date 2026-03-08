"""Unit tests for session revocation service."""
from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

from app.auth_usermanagement.services.session_service import (
    revoke_all_user_sessions,
    revoke_user_session,
)


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

    def query(self, _model):
        return self._query

    def commit(self):
        self.commits += 1

    def refresh(self, obj):
        self.refreshed.append(obj)


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

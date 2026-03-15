"""Unit tests for DB-backed refresh token store helpers."""
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.auth_usermanagement.services import cookie_token_service as svc


def _make_db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()
    return engine, db


def test_store_and_get_refresh_token_roundtrip():
    engine, db = _make_db_session()
    try:
        key = svc.store_refresh_token(db, "refresh-1")
        assert key
        assert svc.get_refresh_token(db, key) == "refresh-1"
    finally:
        db.close()
        Base.metadata.drop_all(engine)


def test_rotate_refresh_token_replaces_old_key():
    engine, db = _make_db_session()
    try:
        old_key = svc.store_refresh_token(db, "refresh-old")
        new_key = svc.rotate_refresh_token(db, old_key, "refresh-new")

        assert new_key != old_key
        assert svc.get_refresh_token(db, old_key) is None
        assert svc.get_refresh_token(db, new_key) == "refresh-new"
    finally:
        db.close()
        Base.metadata.drop_all(engine)


def test_revoke_refresh_token_removes_key():
    engine, db = _make_db_session()
    try:
        key = svc.store_refresh_token(db, "refresh-1")
        svc.revoke_refresh_token(db, key)
        assert svc.get_refresh_token(db, key) is None
    finally:
        db.close()
        Base.metadata.drop_all(engine)


def test_get_refresh_token_purges_expired_records(monkeypatch):
    engine, db = _make_db_session()
    try:
        key = svc.store_refresh_token(db, "refresh-expiring")
        future_now = datetime.now(UTC) + timedelta(days=31)
        monkeypatch.setattr(svc, "_utc_now", lambda: future_now)

        assert svc.get_refresh_token(db, key) is None
    finally:
        db.close()
        Base.metadata.drop_all(engine)

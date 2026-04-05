"""Shared async database test utilities.

Provides helpers for tests that need both:
- A **sync** session for easy test-data setup (inserts, reads)
- An **async** session for FastAPI dependency overrides

Both engines share the same in-memory SQLite via shared-cache URI.

Usage with TestClient::

    from tests.async_test_utils import make_test_db, make_async_app

    sync_engine, SyncSession, async_engine, AsyncSessionLocal = make_test_db()
    app = make_async_app(router, async_engine, AsyncSessionLocal, prefix="/auth")
    client = TestClient(app)

    # Seed data with sync session:
    db = SyncSession()
    db.add(User(...))
    db.commit()
    db.close()

    # HTTP tests via client
    resp = client.get("/auth/me")
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import Callable

from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import sessionmaker

from app.database import Base


def make_test_db():
    """Create sync + async engines sharing the same in-memory SQLite.

    Returns (sync_engine, SyncSessionLocal, async_engine, AsyncSessionLocal).
    Tables are created via the sync engine immediately.
    """
    db_name = f"test_{uuid.uuid4().hex[:8]}"
    sync_url = f"sqlite:///file:{db_name}?mode=memory&cache=shared&uri=true"
    async_url = f"sqlite+aiosqlite:///file:{db_name}?mode=memory&cache=shared&uri=true"

    sync_engine = create_engine(
        sync_url, connect_args={"check_same_thread": False},
    )
    async_engine = create_async_engine(
        async_url, connect_args={"check_same_thread": False},
    )

    Base.metadata.create_all(sync_engine)

    SyncSessionLocal = sessionmaker(bind=sync_engine)
    AsyncSessionLocal = async_sessionmaker(
        bind=async_engine, class_=AsyncSession, expire_on_commit=False,
    )

    return sync_engine, SyncSessionLocal, async_engine, AsyncSessionLocal


def make_async_app(
    router,
    async_engine,
    async_session_factory: async_sessionmaker,
    prefix: str = "",
    extra_setup: Callable[[FastAPI], None] | None = None,
) -> FastAPI:
    """Wire a FastAPI test app with async DB session override.

    Parameters
    ----------
    router : APIRouter
        The router under test.
    async_engine : AsyncEngine
        Async engine (for cleanup / lifespan if needed).
    async_session_factory : async_sessionmaker
        Factory returned by ``make_test_db()``.
    prefix : str
        URL prefix for the router.
    extra_setup : callable, optional
        Hook for middleware, extra overrides, etc.
    """
    app = FastAPI()
    if prefix:
        app.include_router(router, prefix=prefix)
    else:
        app.include_router(router)

    from app.auth_usermanagement.database import get_db

    async def override_get_db():
        async with async_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    if extra_setup:
        extra_setup(app)

    return app

"""Test configuration for backend auth/usermanagement tests."""
from pathlib import Path
import sys
import uuid
import pytest
import pytest_asyncio
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import sessionmaker


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


@pytest.fixture
def db_session():
    """Create an in-memory SQLite sync database session for testing.

    Use this for tests that do NOT call async service functions directly.
    For async service tests, use ``async_db_session`` instead.
    """
    from app.database import Base

    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    yield session

    session.close()
    Base.metadata.drop_all(engine)


@pytest_asyncio.fixture
async def async_db_session():
    """Create an in-memory async SQLite database session for testing.

    Use this for tests that call async service functions directly.
    """
    from app.database import Base

    db_name = f"test_{uuid.uuid4().hex[:8]}"
    sync_url = f"sqlite:///file:{db_name}?mode=memory&cache=shared&uri=true"
    async_url = f"sqlite+aiosqlite:///file:{db_name}?mode=memory&cache=shared&uri=true"

    # Create tables with sync engine
    sync_engine = create_engine(sync_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(sync_engine)

    # Async engine for test session
    async_engine = create_async_engine(async_url, connect_args={"check_same_thread": False})
    AsyncSessionLocal = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)

    async with AsyncSessionLocal() as session:
        yield session

    await async_engine.dispose()
    sync_engine.dispose()


@pytest_asyncio.fixture
async def dual_session():
    """Provide both sync and async sessions sharing the same in-memory database.

    Use the sync session for test data setup (add, commit, refresh),
    and the async session for calling async service functions.
    Yields (sync_session, async_session).
    """
    from app.database import Base

    db_name = f"test_{uuid.uuid4().hex[:8]}"
    sync_url = f"sqlite:///file:{db_name}?mode=memory&cache=shared&uri=true"
    async_url = f"sqlite+aiosqlite:///file:{db_name}?mode=memory&cache=shared&uri=true"

    sync_engine = create_engine(sync_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(sync_engine)

    SyncSession = sessionmaker(bind=sync_engine)
    sync_session = SyncSession()

    async_engine = create_async_engine(async_url, connect_args={"check_same_thread": False})
    AsyncSessionLocal = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)

    async with AsyncSessionLocal() as async_session:
        yield sync_session, async_session

    sync_session.close()
    await async_engine.dispose()
    sync_engine.dispose()

"""
Space service — create, list, suspend/unsuspend spaces.
"""
from datetime import datetime, UTC
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.membership import Membership
from ..models.space import Space


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def create_space(
    db: AsyncSession,
    name: str,
    account_id: UUID | None,
    creator_user_id: UUID,
) -> Space:
    """Create a space and grant the creator a space_admin membership."""
    space = Space(name=name, account_id=account_id)
    db.add(space)
    await db.flush()  # populate space.id

    membership = Membership(
        user_id=creator_user_id,
        scope_type="space",
        scope_id=space.id,
        role_name="space_admin",
        status="active",
        granted_by=creator_user_id,
    )
    db.add(membership)
    await db.commit()
    await db.refresh(space)
    return space


async def list_user_spaces(db: AsyncSession, user_id: UUID) -> list[Space]:
    """Return all spaces where the user has an active membership."""
    space_ids_subq = (
        select(Membership.scope_id)
        .where(
            Membership.user_id == user_id,
            Membership.scope_type == "space",
            Membership.status == "active",
        )
        .scalar_subquery()
    )
    result = await db.execute(
        select(Space)
        .where(Space.id.in_(space_ids_subq))
        .order_by(Space.created_at.desc())
    )
    return list(result.scalars().all())


async def list_account_spaces(db: AsyncSession, account_id: UUID) -> list[Space]:
    """Return all spaces belonging to a given account."""
    result = await db.execute(
        select(Space)
        .where(Space.account_id == account_id)
        .order_by(Space.created_at.desc())
    )
    return list(result.scalars().all())


async def suspend_space(db: AsyncSession, space_id: UUID) -> Space:
    """Suspend a space. Raises ValueError if already suspended."""
    result = await db.execute(select(Space).where(Space.id == space_id))
    space = result.scalar_one_or_none()
    if space is None:
        raise ValueError("Space not found")
    if space.status == "suspended":
        raise ValueError("Space is already suspended")
    space.status = "suspended"
    space.suspended_at = _utc_now()
    await db.commit()
    await db.refresh(space)
    return space


async def unsuspend_space(db: AsyncSession, space_id: UUID) -> Space:
    """Unsuspend a space. Raises ValueError if not currently suspended."""
    result = await db.execute(select(Space).where(Space.id == space_id))
    space = result.scalar_one_or_none()
    if space is None:
        raise ValueError("Space not found")
    if space.status != "suspended":
        raise ValueError("Space is not suspended")
    space.status = "active"
    space.suspended_at = None
    await db.commit()
    await db.refresh(space)
    return space


async def get_space_by_id(db: AsyncSession, space_id: UUID) -> Space | None:
    """Get a space by ID."""
    result = await db.execute(select(Space).where(Space.id == space_id))
    return result.scalar_one_or_none()


async def update_space(db: AsyncSession, space_id: UUID, *, name: str | None = None) -> Space:
    """Update mutable space fields."""
    result = await db.execute(select(Space).where(Space.id == space_id))
    space = result.scalar_one_or_none()
    if space is None:
        raise ValueError("Space not found")
    if name is not None:
        space.name = name
    await db.commit()
    await db.refresh(space)
    return space

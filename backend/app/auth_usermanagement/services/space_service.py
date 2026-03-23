"""
Space service — create, list, suspend/unsuspend spaces.
"""
from datetime import datetime, UTC
from uuid import UUID

from sqlalchemy.orm import Session

from ..models.membership import Membership
from ..models.space import Space


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def create_space(
    db: Session,
    name: str,
    account_id: UUID | None,
    creator_user_id: UUID,
) -> Space:
    """Create a space and grant the creator a space_admin membership."""
    space = Space(name=name, account_id=account_id)
    db.add(space)
    db.flush()  # populate space.id

    membership = Membership(
        user_id=creator_user_id,
        scope_type="space",
        scope_id=space.id,
        role_name="space_admin",
        status="active",
        granted_by=creator_user_id,
    )
    db.add(membership)
    db.commit()
    db.refresh(space)
    return space


def list_user_spaces(db: Session, user_id: UUID) -> list[Space]:
    """Return all spaces where the user has an active membership."""
    space_ids = (
        db.query(Membership.scope_id)
        .filter(
            Membership.user_id == user_id,
            Membership.scope_type == "space",
            Membership.status == "active",
        )
        .scalar_subquery()
    )
    return (
        db.query(Space)
        .filter(Space.id.in_(space_ids))
        .order_by(Space.created_at.desc())
        .all()
    )


def list_account_spaces(db: Session, account_id: UUID) -> list[Space]:
    """Return all spaces belonging to a given account."""
    return (
        db.query(Space)
        .filter(Space.account_id == account_id)
        .order_by(Space.created_at.desc())
        .all()
    )


def suspend_space(db: Session, space_id: UUID) -> Space:
    """Suspend a space. Raises ValueError if already suspended."""
    space = db.query(Space).filter(Space.id == space_id).first()
    if space is None:
        raise ValueError("Space not found")
    if space.status == "suspended":
        raise ValueError("Space is already suspended")
    space.status = "suspended"
    space.suspended_at = _utc_now()
    db.commit()
    db.refresh(space)
    return space


def unsuspend_space(db: Session, space_id: UUID) -> Space:
    """Unsuspend a space. Raises ValueError if not currently suspended."""
    space = db.query(Space).filter(Space.id == space_id).first()
    if space is None:
        raise ValueError("Space not found")
    if space.status != "suspended":
        raise ValueError("Space is not suspended")
    space.status = "active"
    space.suspended_at = None
    db.commit()
    db.refresh(space)
    return space

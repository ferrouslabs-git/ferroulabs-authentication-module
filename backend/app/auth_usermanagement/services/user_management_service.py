"""
Service logic for tenant user-management APIs.
"""
from uuid import UUID

from sqlalchemy.orm import Session

from ..models.membership import Membership


def list_tenant_users(db: Session, tenant_id: UUID) -> list[dict]:
    memberships = db.query(Membership).filter(
        Membership.tenant_id == tenant_id,
        Membership.status == "active",
    ).all()

    return [
        {
            "user_id": m.user.id,
            "email": m.user.email,
            "name": m.user.name,
            "role": m.role,
            "status": m.status,
            "is_active": m.user.is_active,
            "joined_at": m.created_at,
        }
        for m in memberships
    ]


def update_user_role(db: Session, tenant_id: UUID, user_id: UUID, new_role: str) -> Membership | None:
    membership = db.query(Membership).filter(
        Membership.tenant_id == tenant_id,
        Membership.user_id == user_id,
        Membership.status == "active",
    ).first()

    if not membership:
        return None

    # Prevent removing the last owner.
    if membership.role == "owner" and new_role != "owner":
        owner_count = db.query(Membership).filter(
            Membership.tenant_id == tenant_id,
            Membership.role == "owner",
            Membership.status == "active",
        ).count()
        if owner_count <= 1:
            raise ValueError("Cannot remove last owner")

    membership.role = new_role
    db.commit()
    db.refresh(membership)
    return membership


def remove_user_from_tenant(db: Session, tenant_id: UUID, user_id: UUID) -> Membership | None:
    membership = db.query(Membership).filter(
        Membership.tenant_id == tenant_id,
        Membership.user_id == user_id,
        Membership.status == "active",
    ).first()

    if not membership:
        return None

    # Prevent removing the last owner.
    if membership.role == "owner":
        owner_count = db.query(Membership).filter(
            Membership.tenant_id == tenant_id,
            Membership.role == "owner",
            Membership.status == "active",
        ).count()
        if owner_count <= 1:
            raise ValueError("Cannot remove last owner")

    membership.status = "removed"
    db.commit()
    db.refresh(membership)
    return membership

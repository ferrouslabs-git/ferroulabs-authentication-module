"""
Service logic for tenant user-management APIs.
"""
from uuid import UUID

from sqlalchemy.orm import Session, selectinload

from ..models.membership import Membership
from ..models.user import User


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


def list_platform_users(db: Session) -> list[dict]:
    users = db.query(User).options(
        selectinload(User.memberships).selectinload(Membership.tenant)
    ).order_by(User.email.asc()).all()

    return [
        {
            "user_id": user.id,
            "email": user.email,
            "name": user.name,
            "is_platform_admin": user.is_platform_admin,
            "is_active": user.is_active,
            "suspended_at": user.suspended_at,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
            "memberships": [
                {
                    "tenant_id": membership.tenant_id,
                    "tenant_name": membership.tenant.name,
                    "role": membership.role,
                    "status": membership.status,
                    "joined_at": membership.created_at,
                }
                for membership in sorted(
                    user.memberships,
                    key=lambda current_membership: (
                        current_membership.tenant.name.lower(),
                        current_membership.created_at,
                    ),
                )
            ],
        }
        for user in users
    ]


def update_user_role(
    db: Session,
    tenant_id: UUID,
    user_id: UUID,
    new_role: str,
    actor_role: str | None,
    actor_is_platform_admin: bool = False,
) -> Membership | None:
    membership = db.query(Membership).filter(
        Membership.tenant_id == tenant_id,
        Membership.user_id == user_id,
        Membership.status == "active",
    ).first()

    if not membership:
        return None

    if not actor_is_platform_admin:
        if actor_role == "admin":
            if membership.role == "owner":
                raise ValueError("Admins cannot modify owner roles")
            if new_role in {"owner", "admin"}:
                raise ValueError("Admins can only assign member or viewer roles")

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

"""
Service logic for tenant user-management APIs.
"""
from uuid import UUID

from sqlalchemy.orm import Session, selectinload

from ..models.membership import Membership
from ..models.user import User


def list_tenant_users(db: Session, tenant_id: UUID) -> list[dict]:
    memberships = db.query(Membership).filter(
        Membership.scope_type == "account",
        Membership.scope_id == tenant_id,
        Membership.status == "active",
    ).all()

    return [
        {
            "user_id": m.user.id,
            "email": m.user.email,
            "name": m.user.name,
            "role": m.role_name,
            "status": m.status,
            "is_active": m.user.is_active,
            "joined_at": m.created_at,
        }
        for m in memberships
    ]


def list_platform_users(db: Session) -> list[dict]:
    users = db.query(User).options(
        selectinload(User.memberships)
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
                    "tenant_id": membership.scope_id if membership.scope_type == "account" else None,
                    "tenant_name": membership.tenant.name if membership.tenant else None,
                    "role": membership.role_name,
                    "scope_type": membership.scope_type,
                    "scope_id": membership.scope_id,
                    "status": membership.status,
                    "joined_at": membership.created_at,
                }
                for membership in sorted(
                    user.memberships,
                    key=lambda m: m.created_at,
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
        Membership.scope_type == "account",
        Membership.scope_id == tenant_id,
        Membership.user_id == user_id,
        Membership.status == "active",
    ).first()

    if not membership:
        return None

    current_role = membership.role_name

    if not actor_is_platform_admin:
        actor_effective = actor_role or ""
        if actor_effective in ("admin", "account_admin"):
            if current_role in ("owner", "account_owner"):
                raise ValueError("Admins cannot modify owner roles")
            if new_role in {"owner", "admin", "account_owner", "account_admin"}:
                raise ValueError("Admins can only assign member or viewer roles")

    # Prevent removing the last owner / account_owner.
    if current_role in ("owner", "account_owner") and new_role not in ("owner", "account_owner"):
        owner_count = db.query(Membership).filter(
            Membership.scope_type == "account",
            Membership.scope_id == tenant_id,
            Membership.status == "active",
            Membership.role_name.in_(["account_owner", "owner"]),
        ).count()
        if owner_count <= 1:
            raise ValueError("Cannot remove last owner")

    membership.role_name = new_role
    db.commit()
    db.refresh(membership)
    return membership


def remove_user_from_tenant(db: Session, tenant_id: UUID, user_id: UUID) -> Membership | None:
    membership = db.query(Membership).filter(
        Membership.scope_type == "account",
        Membership.scope_id == tenant_id,
        Membership.user_id == user_id,
        Membership.status == "active",
    ).first()

    if not membership:
        return None

    current_role = membership.role_name

    # Prevent removing the last owner / account_owner.
    if current_role in ("owner", "account_owner"):
        owner_count = db.query(Membership).filter(
            Membership.scope_type == "account",
            Membership.scope_id == tenant_id,
            Membership.status == "active",
            Membership.role_name.in_(["account_owner", "owner"]),
        ).count()
        if owner_count <= 1:
            raise ValueError("Cannot remove last owner")

    membership.status = "removed"
    db.commit()
    db.refresh(membership)
    return membership

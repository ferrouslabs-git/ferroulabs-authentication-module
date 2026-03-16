"""
Tenant service - handles tenant creation and management
"""
from sqlalchemy.orm import Session, selectinload
from typing import List, Optional
from uuid import UUID

from ..models.tenant import Tenant
from ..models.membership import Membership
from ..models.user import User


def create_tenant(
    name: str,
    user: User,
    db: Session,
    plan: str = "free"
) -> Tenant:
    """
    Create a new tenant and assign creator as owner.
    
    Args:
        name: Tenant organization name
        user: Current user (will be made owner)
        db: Database session
        plan: Pricing plan (default: free)
    
    Returns:
        Tenant: Created tenant object
    """
    # Create tenant
    tenant = Tenant(
        name=name,
        plan=plan,
        status="active"
    )
    db.add(tenant)
    db.flush()  # Get the tenant ID without committing
    
    # Create owner membership for the creator
    membership = Membership(
        user_id=user.id,
        tenant_id=tenant.id,
        role="owner",
        status="active"
    )
    db.add(membership)
    db.commit()
    db.refresh(tenant)
    
    return tenant


def get_tenant_by_id(tenant_id: UUID, db: Session) -> Optional[Tenant]:
    """
    Get tenant by ID.
    
    Args:
        tenant_id: Tenant UUID
        db: Database session
    
    Returns:
        Tenant if found, None otherwise
    """
    return db.query(Tenant).filter(Tenant.id == tenant_id).first()


def get_user_tenants(user_id: UUID, db: Session) -> List[dict]:
    """
    Get all tenants that a user belongs to with their role.
    
    Args:
        user_id: User UUID
        db: Database session
    
    Returns:
        List of tenant dict with user's role
    """
    memberships = db.query(Membership).filter(
        Membership.user_id == user_id,
        Membership.status == "active"
    ).all()
    
    result = []
    for membership in memberships:
        tenant_data = {
            "id": membership.tenant.id,
            "name": membership.tenant.name,
            "plan": membership.tenant.plan,
            "status": membership.tenant.status,
            "role": membership.role,
            "created_at": membership.tenant.created_at
        }
        result.append(tenant_data)
    
    return result


def get_user_tenant_role(
    user_id: UUID,
    tenant_id: UUID,
    db: Session
) -> Optional[str]:
    """
    Get user's role in a specific tenant.
    
    Args:
        user_id: User UUID
        tenant_id: Tenant UUID
        db: Database session
    
    Returns:
        Role string (owner, admin, member, viewer) or None if not a member
    """
    membership = db.query(Membership).filter(
        Membership.user_id == user_id,
        Membership.tenant_id == tenant_id,
        Membership.status == "active"
    ).first()
    
    return membership.role if membership else None


def list_platform_tenants(db: Session) -> List[dict]:
    tenants = db.query(Tenant).options(selectinload(Tenant.memberships)).order_by(Tenant.name.asc()).all()

    return [
        {
            "tenant_id": tenant.id,
            "name": tenant.name,
            "plan": tenant.plan,
            "status": tenant.status,
            "created_at": tenant.created_at,
            "member_count": sum(1 for membership in tenant.memberships if membership.status == "active"),
            "owner_count": sum(
                1
                for membership in tenant.memberships
                if membership.status == "active" and membership.role == "owner"
            ),
        }
        for tenant in tenants
    ]


def verify_user_tenant_access(
    user_id: UUID,
    tenant_id: UUID,
    db: Session
) -> bool:
    """
    Verify if user has access to a tenant.
    
    Args:
        user_id: User UUID
        tenant_id: Tenant UUID
        db: Database session
    
    Returns:
        True if user has active membership, False otherwise
    """
    membership = db.query(Membership).filter(
        Membership.user_id == user_id,
        Membership.tenant_id == tenant_id,
        Membership.status == "active"
    ).first()
    
    return membership is not None


def suspend_tenant(tenant_id: UUID, db: Session) -> Tenant:
    """Suspend a tenant to block organization-level operations."""
    tenant = get_tenant_by_id(tenant_id, db)
    if not tenant:
        raise ValueError(f"Tenant not found: {tenant_id}")

    tenant.status = "suspended"
    db.commit()
    db.refresh(tenant)
    return tenant


def unsuspend_tenant(tenant_id: UUID, db: Session) -> Tenant:
    """Restore a suspended tenant back to active status."""
    tenant = get_tenant_by_id(tenant_id, db)
    if not tenant:
        raise ValueError(f"Tenant not found: {tenant_id}")

    tenant.status = "active"
    db.commit()
    db.refresh(tenant)
    return tenant

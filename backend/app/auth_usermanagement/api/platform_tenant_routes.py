from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db

from ..models.user import User
from ..schemas.tenant import PlatformTenantResponse, TenantStatusResponse
from ..security import get_current_user
from ..services.audit_service import log_audit_event
from ..services.tenant_service import list_platform_tenants, suspend_tenant, unsuspend_tenant
from .route_helpers import ensure_platform_admin

router = APIRouter()


@router.get("/platform/tenants", response_model=list[PlatformTenantResponse])
async def get_platform_tenants(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all tenants across the platform (super admin only)."""
    ensure_platform_admin(current_user, "view tenants")
    return list_platform_tenants(db)


@router.patch("/platform/tenants/{tenant_id}/suspend", response_model=TenantStatusResponse)
async def suspend_tenant_account(
    tenant_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Suspend a tenant (super admin only)."""
    ensure_platform_admin(current_user, "suspend tenant")

    try:
        tenant = suspend_tenant(tenant_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    log_audit_event(
        "tenant_suspended",
        actor_user_id=str(current_user.id),
        db=db,
        tenant_id=str(tenant.id),
        tenant_name=tenant.name,
    )

    return TenantStatusResponse(
        tenant_id=tenant.id,
        status=tenant.status,
        message="Tenant suspended successfully",
    )


@router.patch("/platform/tenants/{tenant_id}/unsuspend", response_model=TenantStatusResponse)
async def unsuspend_tenant_account(
    tenant_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Unsuspend a tenant (super admin only)."""
    ensure_platform_admin(current_user, "unsuspend tenant")

    try:
        tenant = unsuspend_tenant(tenant_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    log_audit_event(
        "tenant_unsuspended",
        actor_user_id=str(current_user.id),
        db=db,
        tenant_id=str(tenant.id),
        tenant_name=tenant.name,
    )

    return TenantStatusResponse(
        tenant_id=tenant.id,
        status=tenant.status,
        message="Tenant unsuspended successfully",
    )

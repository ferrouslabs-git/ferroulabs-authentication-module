from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db

from ..models.user import User
from ..schemas.tenant import TenantCreateRequest, TenantCreateResponse, TenantListResponse
from ..security import TenantContext, get_current_user, get_tenant_context
from ..services.audit_service import log_audit_event
from ..services.tenant_service import create_tenant, get_user_tenants

router = APIRouter()


@router.post("/tenants", response_model=TenantCreateResponse)
async def create_new_tenant(
    tenant_data: TenantCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new tenant (organization).
    Requires authentication.
    Creator will be assigned 'owner' role automatically.
    """
    tenant = create_tenant(
        name=tenant_data.name,
        user=current_user,
        db=db,
        plan=tenant_data.plan,
    )

    log_audit_event(
        "tenant_created",
        actor_user_id=str(current_user.id),
        tenant_id=str(tenant.id),
        tenant_name=tenant.name,
        plan=tenant.plan,
    )

    return TenantCreateResponse(
        tenant_id=tenant.id,
        name=tenant.name,
        plan=tenant.plan,
        role="owner",
        message="Tenant created successfully",
    )


@router.get("/tenants/my", response_model=List[TenantListResponse])
async def get_my_tenants(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all tenants that the current user belongs to."""
    return get_user_tenants(current_user.id, db)


@router.get("/tenant-context")
async def get_tenant_context_info(ctx: TenantContext = Depends(get_tenant_context)):
    """Test endpoint for tenant-context middleware and role resolution."""
    return {
        "user_id": str(ctx.user_id),
        "tenant_id": str(ctx.tenant_id),
        "role": ctx.role,
        "is_platform_admin": ctx.is_platform_admin,
        "is_owner": ctx.is_owner(),
        "is_admin_or_owner": ctx.is_admin_or_owner(),
        "message": "Tenant context validated successfully",
    }
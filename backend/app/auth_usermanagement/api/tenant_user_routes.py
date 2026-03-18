from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db

from ..schemas.user_management import (
    RemoveUserResponse,
    TenantUserResponse,
    UpdateUserRoleRequest,
    UpdateUserRoleResponse,
)
from ..security import TenantContext, require_admin, require_member
from ..services.audit_service import log_audit_event
from ..services.user_management_service import list_tenant_users, remove_user_from_tenant, update_user_role
from .route_helpers import ensure_tenant_access

router = APIRouter()


@router.get("/tenants/{tenant_id}/users", response_model=List[TenantUserResponse])
async def get_tenant_users(
    tenant_id: UUID,
    ctx: TenantContext = Depends(require_member),
    db: Session = Depends(get_db),
):
    """List active users in tenant (member+)."""
    ensure_tenant_access(tenant_id, ctx)
    return list_tenant_users(db, tenant_id)


@router.patch("/tenants/{tenant_id}/users/{user_id}/role", response_model=UpdateUserRoleResponse)
async def patch_tenant_user_role(
    tenant_id: UUID,
    user_id: UUID,
    payload: UpdateUserRoleRequest,
    ctx: TenantContext = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update user's tenant role (admin+)."""
    ensure_tenant_access(tenant_id, ctx)
    try:
        membership = update_user_role(
            db,
            tenant_id,
            user_id,
            payload.role,
            actor_role=ctx.role,
            actor_is_platform_admin=ctx.is_platform_admin,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found in tenant")

    log_audit_event(
        "tenant_user_role_updated",
        actor_user_id=str(ctx.user_id),
        db=db,
        tenant_id=str(tenant_id),
        target_user_id=str(user_id),
        new_role=payload.role,
    )

    return UpdateUserRoleResponse(
        user_id=membership.user_id,
        tenant_id=membership.tenant_id,
        role=membership.role,
        message="User role updated successfully",
    )


@router.delete("/tenants/{tenant_id}/users/{user_id}", response_model=RemoveUserResponse)
async def delete_tenant_user(
    tenant_id: UUID,
    user_id: UUID,
    ctx: TenantContext = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Soft-remove user from tenant (admin+)."""
    ensure_tenant_access(tenant_id, ctx)
    try:
        membership = remove_user_from_tenant(db, tenant_id, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found in tenant")

    log_audit_event(
        "tenant_user_removed",
        actor_user_id=str(ctx.user_id),
        db=db,
        tenant_id=str(tenant_id),
        target_user_id=str(user_id),
        resulting_status=membership.status,
    )

    return RemoveUserResponse(
        user_id=membership.user_id,
        tenant_id=membership.tenant_id,
        status=membership.status,
        message="User removed from tenant",
    )
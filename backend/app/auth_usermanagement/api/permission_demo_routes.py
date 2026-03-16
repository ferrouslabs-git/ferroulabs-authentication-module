from fastapi import APIRouter, Depends

from ..security import (
    TenantContext,
    check_permission,
    get_tenant_context,
    require_admin,
    require_member,
    require_owner,
    require_viewer,
)

router = APIRouter()


@router.get("/admin/settings")
async def get_admin_settings(ctx: TenantContext = Depends(require_admin)):
    """Admin-only endpoint - requires owner or admin role."""
    return {
        "tenant_id": str(ctx.tenant_id),
        "accessed_by": str(ctx.user_id),
        "role": ctx.role,
        "message": "Admin settings accessed successfully",
        "settings": {
            "max_users": 50,
            "api_enabled": True,
            "webhooks_configured": False,
        },
    }


@router.get("/owner/danger-zone")
async def get_owner_settings(ctx: TenantContext = Depends(require_owner)):
    """Owner-only endpoint - requires owner role."""
    return {
        "tenant_id": str(ctx.tenant_id),
        "accessed_by": str(ctx.user_id),
        "role": ctx.role,
        "message": "Owner-only danger zone accessed",
        "available_actions": [
            "delete_tenant",
            "transfer_ownership",
            "view_billing",
            "cancel_subscription",
        ],
    }


@router.get("/member/dashboard")
async def get_member_dashboard(ctx: TenantContext = Depends(require_member)):
    """Member-level endpoint - requires member, admin, or owner."""
    return {
        "tenant_id": str(ctx.tenant_id),
        "accessed_by": str(ctx.user_id),
        "role": ctx.role,
        "message": "Member dashboard accessed",
        "can_create": True,
        "can_edit": True,
        "can_delete": ctx.role in ("owner", "admin"),
        "recent_activity": [],
    }


@router.get("/viewer/reports")
async def get_viewer_reports(ctx: TenantContext = Depends(require_viewer)):
    """Viewer-level endpoint - any tenant member can access."""
    return {
        "tenant_id": str(ctx.tenant_id),
        "accessed_by": str(ctx.user_id),
        "role": ctx.role,
        "message": "Reports accessed (read-only)",
        "reports": [
            {"id": 1, "name": "Monthly Summary", "type": "summary"},
            {"id": 2, "name": "User Activity", "type": "analytics"},
        ],
    }


@router.get("/permissions/check")
async def check_user_permissions(ctx: TenantContext = Depends(get_tenant_context)):
    """Check what permissions the current user has in this tenant."""
    permissions_to_check = [
        "tenant:delete",
        "tenant:edit",
        "users:create",
        "users:edit",
        "users:delete",
        "settings:edit",
        "data:create",
        "data:edit",
        "data:delete",
        "data:read",
    ]

    user_permissions = {
        permission: check_permission(ctx, permission)
        for permission in permissions_to_check
    }

    return {
        "tenant_id": str(ctx.tenant_id),
        "user_id": str(ctx.user_id),
        "role": ctx.role,
        "is_platform_admin": ctx.is_platform_admin,
        "permissions": user_permissions,
        "message": "Permission check complete",
    }
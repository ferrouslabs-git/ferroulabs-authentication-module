"""
Role-based authorization guards for tenant access control

Guards are FastAPI dependencies that enforce role-based permissions.
Use them to protect endpoints requiring specific tenant roles.

Example Usage:
    @router.delete("/users/{user_id}")
    async def remove_user(
        user_id: UUID,
        ctx: TenantContext = Depends(require_admin),  # Only owner/admin
        db: Session = Depends(get_db)
    ):
        # Only owners and admins can remove users
        ...

Role Hierarchy:
    owner > admin > member > viewer
    
    - owner: Full control, can delete tenant, manage all users
    - admin: Can manage users, change settings, but can't delete tenant
    - member: Can access data, create/edit within tenant
    - viewer: Read-only access to tenant data
"""
from fastapi import Depends, HTTPException, status
from typing import List, Callable

from .tenant_context import TenantContext
from .dependencies import get_tenant_context


# Role hierarchy for comparison
ROLE_HIERARCHY = {
    "owner": 4,
    "admin": 3,
    "member": 2,
    "viewer": 1,
}


def require_role(*allowed_roles: str) -> Callable:
    """
    Create a dependency that requires one of the specified roles.
    
    Platform admins automatically bypass role checks.
    
    Args:
        *allowed_roles: One or more role names (owner, admin, member, viewer)
    
    Returns:
        Dependency function that validates tenant context has required role
    
    Raises:
        HTTPException 403: If user doesn't have required role
    
    Example:
        # Require owner OR admin
        @router.post("/settings")
        async def update_settings(ctx: TenantContext = Depends(require_role("owner", "admin"))):
            ...
    """
    def role_checker(ctx: TenantContext = Depends(get_tenant_context)) -> TenantContext:
        # Platform admins bypass all role checks
        if ctx.is_platform_admin:
            return ctx
        
        # Check if user has one of the allowed roles
        if ctx.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {' or '.join(allowed_roles)}. Your role: {ctx.role}"
            )
        
        return ctx
    
    return role_checker


def require_min_role(min_role: str) -> Callable:
    """
    Require a minimum role level in the hierarchy.
    
    For example, require_min_role("admin") allows owner and admin but blocks member and viewer.
    
    Args:
        min_role: Minimum required role (owner, admin, member, viewer)
    
    Returns:
        Dependency function that validates role hierarchy
    
    Raises:
        HTTPException 403: If user's role is below minimum
    
    Example:
        @router.patch("/users/{user_id}/role")
        async def change_user_role(ctx: TenantContext = Depends(require_min_role("admin"))):
            # Admins and owners can change roles
            ...
    """
    if min_role not in ROLE_HIERARCHY:
        raise ValueError(f"Invalid role: {min_role}. Must be one of: {', '.join(ROLE_HIERARCHY.keys())}")
    
    min_level = ROLE_HIERARCHY[min_role]
    
    def role_checker(ctx: TenantContext = Depends(get_tenant_context)) -> TenantContext:
        # Platform admins bypass all checks
        if ctx.is_platform_admin:
            return ctx
        
        # Check role hierarchy
        user_level = ROLE_HIERARCHY.get(ctx.role, 0)
        
        if user_level < min_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required minimum role: {min_role}. Your role: {ctx.role}"
            )
        
        return ctx
    
    return role_checker


# Convenience guards for common role requirements
require_owner = require_role("owner")
"""Require tenant owner role. Only owners can access."""

require_admin = require_role("owner", "admin")
"""Require admin or owner role. For management operations."""

require_member = require_role("owner", "admin", "member")
"""Require member, admin, or owner. Basic tenant access."""

require_viewer = require_role("owner", "admin", "member", "viewer")
"""Require any valid tenant membership. Read operations."""


def check_permission(ctx: TenantContext, permission: str) -> bool:
    """
    Check if tenant context has a specific permission.
    
    Permission format: "resource:action" (e.g., "users:delete", "settings:edit")
    
    This is a placeholder for fine-grained permission checking.
    In the future, this could check against a permissions table.
    
    For now, it uses role-based mapping:
    - owner: all permissions
    - admin: all except tenant:delete
    - member: read/write, no user management
    - viewer: read-only
    
    Args:
        ctx: Tenant context with user's role
        permission: Permission string to check
    
    Returns:
        True if user has permission, False otherwise
    
    Example:
        if check_permission(ctx, "users:delete"):
            # User can delete users
            ...
    """
    # Platform admins have all permissions
    if ctx.is_platform_admin:
        return True
    
    # Permission mapping by role
    role_permissions = {
        "owner": [
            "tenant:delete", "tenant:edit",
            "users:create", "users:edit", "users:delete",
            "settings:edit",
            "data:create", "data:edit", "data:delete", "data:read",
        ],
        "admin": [
            "tenant:edit",  # Can't delete tenant
            "users:create", "users:edit", "users:delete",
            "settings:edit",
            "data:create", "data:edit", "data:delete", "data:read",
        ],
        "member": [
            "data:create", "data:edit", "data:delete", "data:read",
            "settings:read",
        ],
        "viewer": [
            "data:read",
            "settings:read",
        ],
    }
    
    allowed_permissions = role_permissions.get(ctx.role, [])
    
    # Check exact permission
    if permission in allowed_permissions:
        return True
    
    # Check wildcard permission (e.g., "data:*" grants all data permissions)
    resource = permission.split(":")[0] if ":" in permission else permission
    wildcard = f"{resource}:*"
    
    return wildcard in allowed_permissions


def require_permission(permission: str) -> Callable:
    """
    Create a dependency that requires a specific permission.
    
    Args:
        permission: Permission string (e.g., "users:delete")
    
    Returns:
        Dependency function that checks permission
    
    Raises:
        HTTPException 403: If user lacks permission
    
    Example:
        @router.delete("/tenant")
        async def delete_tenant(ctx: TenantContext = Depends(require_permission("tenant:delete"))):
            # Only owners can delete tenant
            ...
    """
    def permission_checker(ctx: TenantContext = Depends(get_tenant_context)) -> TenantContext:
        if not check_permission(ctx, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required permission: {permission}"
            )
        
        return ctx
    
    return permission_checker

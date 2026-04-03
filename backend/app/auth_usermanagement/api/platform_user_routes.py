from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..database import get_db

from ..models.user import User
from ..schemas.user_management import PlatformUserResponse
from ..security import get_current_user
from ..services.audit_service import log_audit_event
from ..services.user_service import (
    delete_user_async,
    demote_from_platform_admin,
    get_user_by_id,
    promote_to_platform_admin,
    suspend_user_async,
    unsuspend_user,
)
from ..services.cognito_admin_service import (
    admin_disable_user_async,
    admin_enable_user_async,
    admin_get_user_async,
    admin_reset_user_password_async,
)
from ..services.user_management_service import list_platform_users
from .route_helpers import build_user_status_response, ensure_not_self_target, ensure_platform_admin

router = APIRouter()


@router.get("/platform/users", response_model=list[PlatformUserResponse])
async def get_platform_users(
    role: str | None = Query(None, description="Filter by role name (e.g. account_owner)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all users across the platform. Supports ?role= filter (platform admin only)."""
    if not current_user.is_platform_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only platform administrators can view all users",
        )
    return list_platform_users(db, role=role)


@router.get("/platform/users/{user_id}", response_model=PlatformUserResponse)
async def get_platform_user_detail(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get details for a single user including memberships (platform admin only)."""
    ensure_platform_admin(current_user, "view user details for")

    user = get_user_by_id(user_id, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    memberships = [
        {
            "tenant_id": m.scope_id if m.scope_type == "account" else None,
            "tenant_name": m.tenant.name if m.tenant and m.scope_type == "account" else None,
            "role": m.role_name,
            "status": m.status,
            "joined_at": m.created_at,
            "scope_type": m.scope_type,
            "scope_id": m.scope_id,
        }
        for m in user.memberships
    ]

    return PlatformUserResponse(
        user_id=user.id,
        email=user.email,
        name=user.name,
        is_platform_admin=user.is_platform_admin,
        is_active=user.is_active,
        suspended_at=user.suspended_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
        memberships=memberships,
    )


@router.patch("/users/{user_id}/suspend")
async def suspend_user_account(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Suspend a user account (platform admin only)."""
    ensure_platform_admin(current_user, "suspend")
    ensure_not_self_target(user_id, current_user)

    try:
        suspended_user = await suspend_user_async(user_id, db)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    log_audit_event(
        "user_suspended",
        actor_user_id=str(current_user.id),
        db=db,
        target_user_id=str(user_id),
        target_email=suspended_user.email,
    )

    return build_user_status_response(
        suspended_user,
        "User account suspended successfully",
        suspended_user.suspended_at.isoformat() if suspended_user.suspended_at else None,
    )


@router.patch("/users/{user_id}/unsuspend")
async def unsuspend_user_account(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Unsuspend a user account (platform admin only)."""
    ensure_platform_admin(current_user, "unsuspend")

    try:
        unsuspended_user = unsuspend_user(user_id, db)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    log_audit_event(
        "user_unsuspended",
        actor_user_id=str(current_user.id),
        db=db,
        target_user_id=str(user_id),
        target_email=unsuspended_user.email,
    )

    return build_user_status_response(
        unsuspended_user,
        "User account unsuspended successfully",
        None,
    )


@router.patch("/platform/users/{user_id}/promote")
async def promote_platform_admin_account(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Grant platform admin access to another user (platform admin only)."""
    ensure_platform_admin(current_user, "promote")

    try:
        promoted_user = promote_to_platform_admin(user_id, db)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    log_audit_event(
        "user_promoted_to_platform_admin",
        actor_user_id=str(current_user.id),
        db=db,
        target_user_id=str(user_id),
        target_email=promoted_user.email,
    )

    return build_user_status_response(
        promoted_user,
        "Super admin access granted successfully",
        promoted_user.suspended_at.isoformat() if promoted_user.suspended_at else None,
    )


@router.patch("/platform/users/{user_id}/demote")
async def demote_platform_admin_account(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove platform admin access from another user (platform admin only)."""
    ensure_platform_admin(current_user, "demote")
    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot revoke your own super admin access",
        )

    try:
        demoted_user = demote_from_platform_admin(user_id, db)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST if "last platform administrator" in str(exc) else status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    log_audit_event(
        "user_demoted_from_platform_admin",
        actor_user_id=str(current_user.id),
        db=db,
        target_user_id=str(user_id),
        target_email=demoted_user.email,
    )

    return build_user_status_response(
        demoted_user,
        "Super admin access removed successfully",
        demoted_user.suspended_at.isoformat() if demoted_user.suspended_at else None,
    )


# ── User deletion ───────────────────────────────────────────────


@router.delete("/platform/users/{user_id}")
async def delete_platform_user(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Permanently delete a user from Cognito and the database (platform admin only).

    Removes the user from Cognito, revokes all sessions, deletes memberships,
    anonymizes invitations, and deletes the local User record. Irreversible.
    """
    ensure_platform_admin(current_user, "delete")
    ensure_not_self_target(user_id, current_user)

    try:
        result = await delete_user_async(user_id, db)
    except ValueError as exc:
        detail = str(exc)
        code = status.HTTP_404_NOT_FOUND
        if "platform admin" in detail or "last owner" in detail or "Cognito" in detail:
            code = status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=detail) from exc

    log_audit_event(
        "user_permanently_deleted",
        actor_user_id=str(current_user.id),
        db=db,
        target_user_id=str(user_id),
        target_email=result["email"],
    )

    return {
        "user_id": result["user_id"],
        "email": result["email"],
        "message": "User permanently deleted from Cognito and database",
    }


# ── Cognito admin operations ────────────────────────────────────


@router.post("/platform/users/{user_id}/cognito/disable")
async def disable_cognito_user(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Disable a user in Cognito — blocks sign-in but preserves the account (platform admin only)."""
    ensure_platform_admin(current_user, "disable Cognito account for")

    user = get_user_by_id(user_id, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    result = await admin_disable_user_async(user.email)
    if "error" in result:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"])

    log_audit_event(
        "cognito_user_disabled",
        actor_user_id=str(current_user.id),
        db=db,
        target_user_id=str(user_id),
        target_email=user.email,
    )

    return {"user_id": str(user_id), "email": user.email, "message": "Cognito account disabled"}


@router.post("/platform/users/{user_id}/cognito/enable")
async def enable_cognito_user(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Re-enable a disabled Cognito user (platform admin only)."""
    ensure_platform_admin(current_user, "enable Cognito account for")

    user = get_user_by_id(user_id, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    result = await admin_enable_user_async(user.email)
    if "error" in result:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"])

    log_audit_event(
        "cognito_user_enabled",
        actor_user_id=str(current_user.id),
        db=db,
        target_user_id=str(user_id),
        target_email=user.email,
    )

    return {"user_id": str(user_id), "email": user.email, "message": "Cognito account enabled"}


@router.get("/platform/users/{user_id}/cognito")
async def get_cognito_user_status(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Look up a user's status in Cognito (platform admin only)."""
    ensure_platform_admin(current_user, "view Cognito status for")

    user = get_user_by_id(user_id, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    result = await admin_get_user_async(user.email)
    if "error" in result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result["error"])

    return {
        "user_id": str(user_id),
        "email": user.email,
        "cognito_status": result.get("status"),
        "cognito_enabled": result.get("enabled"),
        "cognito_created_at": str(result.get("created_at")) if result.get("created_at") else None,
    }


@router.post("/platform/users/{user_id}/cognito/reset-password")
async def reset_cognito_user_password(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Force a password reset for a user — Cognito sends them a reset code (platform admin only)."""
    ensure_platform_admin(current_user, "reset password for")

    user = get_user_by_id(user_id, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    result = await admin_reset_user_password_async(user.email)
    if "error" in result:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"])

    log_audit_event(
        "cognito_password_reset_forced",
        actor_user_id=str(current_user.id),
        db=db,
        target_user_id=str(user_id),
        target_email=user.email,
    )

    return {"user_id": str(user_id), "email": user.email, "message": "Password reset initiated — user will receive a reset code via email"}
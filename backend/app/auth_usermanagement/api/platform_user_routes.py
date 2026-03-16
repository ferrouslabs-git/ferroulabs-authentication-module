from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db

from ..models.user import User
from ..schemas.user_management import PlatformUserResponse
from ..security import get_current_user
from ..services.audit_service import log_audit_event
from ..services.user_service import demote_from_platform_admin, promote_to_platform_admin, suspend_user, unsuspend_user
from ..services.user_management_service import list_platform_users
from .route_helpers import build_user_status_response, ensure_not_self_target, ensure_platform_admin

router = APIRouter()


@router.get("/platform/users", response_model=list[PlatformUserResponse])
async def get_platform_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all users across the platform with tenant memberships (platform admin only)."""
    if not current_user.is_platform_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only platform administrators can view all users",
        )
    return list_platform_users(db)


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
        suspended_user = suspend_user(user_id, db)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    log_audit_event(
        "user_suspended",
        actor_user_id=str(current_user.id),
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
        target_user_id=str(user_id),
        target_email=demoted_user.email,
    )

    return build_user_status_response(
        demoted_user,
        "Super admin access removed successfully",
        demoted_user.suspended_at.isoformat() if demoted_user.suspended_at else None,
    )
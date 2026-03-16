from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db

from ..models.user import User
from ..security import get_current_user
from ..services.audit_service import log_audit_event
from ..services.user_service import suspend_user, unsuspend_user
from .route_helpers import build_user_status_response, ensure_not_self_target, ensure_platform_admin

router = APIRouter()


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
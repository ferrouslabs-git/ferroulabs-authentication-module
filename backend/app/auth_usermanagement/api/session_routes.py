from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db

from ..models.user import User
from ..schemas.session import SessionRegisterRequest, SessionRotateRequest
from ..security import get_current_user
from ..services.audit_service import log_audit_event
from ..services.session_service import (
    create_user_session,
    revoke_all_user_sessions,
    revoke_user_session,
    rotate_user_session,
)

router = APIRouter()


@router.delete("/sessions/all")
async def revoke_all_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_current_session_id: Optional[str] = Header(None),
):
    """Revoke all active sessions for current user."""
    keep_session_id: UUID | None = None
    if x_current_session_id:
        try:
            keep_session_id = UUID(x_current_session_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid X-Current-Session-ID format",
            ) from exc

    revoked_count = revoke_all_user_sessions(
        db=db,
        user_id=current_user.id,
        except_session_id=keep_session_id,
    )

    log_audit_event(
        "all_sessions_revoked",
        actor_user_id=str(current_user.id),
        revoked_count=revoked_count,
        kept_session_id=str(keep_session_id) if keep_session_id else None,
    )

    return {
        "user_id": str(current_user.id),
        "revoked_count": revoked_count,
        "kept_session_id": str(keep_session_id) if keep_session_id else None,
        "message": "Session revocation completed",
    }


@router.post("/sessions/register")
async def register_session(
    payload: SessionRegisterRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a refresh-token-backed session for current user."""
    created = create_user_session(
        db=db,
        user_id=current_user.id,
        refresh_token=payload.refresh_token,
        user_agent=payload.user_agent,
        ip_address=payload.ip_address,
        device_info=payload.device_info,
        expires_at=payload.expires_at,
    )

    log_audit_event(
        "session_registered",
        actor_user_id=str(current_user.id),
        session_id=str(created.id),
    )

    return {
        "session_id": str(created.id),
        "user_id": str(current_user.id),
        "revoked_at": None,
        "message": "Session registered successfully",
    }


@router.post("/sessions/{session_id}/rotate")
async def rotate_session(
    session_id: UUID,
    payload: SessionRotateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Rotate refresh token by revoking current session and issuing replacement."""
    rotated = rotate_user_session(
        db=db,
        user_id=current_user.id,
        session_id=session_id,
        old_refresh_token=payload.old_refresh_token,
        new_refresh_token=payload.new_refresh_token,
        user_agent=payload.user_agent,
        ip_address=payload.ip_address,
        device_info=payload.device_info,
        expires_at=payload.expires_at,
    )

    if not rotated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    log_audit_event(
        "session_rotated",
        actor_user_id=str(current_user.id),
        previous_session_id=str(session_id),
        new_session_id=str(rotated.id),
    )

    return {
        "session_id": str(rotated.id),
        "user_id": str(current_user.id),
        "revoked_at": None,
        "message": "Session rotated successfully",
    }


@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke one active session that belongs to the current user."""
    revoked = revoke_user_session(db, current_user.id, session_id)
    if not revoked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    log_audit_event(
        "session_revoked",
        actor_user_id=str(current_user.id),
        session_id=str(session_id),
    )

    return {
        "session_id": str(revoked.id),
        "user_id": str(current_user.id),
        "revoked_at": revoked.revoked_at.isoformat() if revoked.revoked_at else None,
        "message": "Session revoked successfully",
    }
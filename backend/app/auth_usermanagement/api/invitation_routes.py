from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db

from ..models.user import User
from ..schemas.invitation import (
    InvitationAcceptRequest,
    InvitationAcceptResponse,
    InvitationCreateRequest,
    InvitationCreateResponse,
    InvitationPreviewResponse,
    InvitationRevokeResponse,
)
from ..security import TenantContext, get_current_user, require_admin
from ..services.audit_service import log_audit_event
from ..services.invitation_service import (
    accept_invitation,
    get_invitation_by_token,
    get_tenant_invitation_by_token,
    revoke_invitation,
)
from .route_helpers import create_invitation_response, ensure_tenant_access

router = APIRouter()


@router.post("/invite", response_model=InvitationCreateResponse)
async def invite_user_to_tenant(
    invite_data: InvitationCreateRequest,
    ctx: TenantContext = Depends(require_admin),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create an invitation for a user to join the current tenant."""
    return await create_invitation_response(db, ctx.tenant_id, invite_data, current_user)


@router.post("/tenants/{tenant_id}/invite", response_model=InvitationCreateResponse)
async def invite_user_to_explicit_tenant(
    tenant_id: UUID,
    invite_data: InvitationCreateRequest,
    ctx: TenantContext = Depends(require_admin),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create an invitation using explicit tenant path parameter."""
    ensure_tenant_access(tenant_id, ctx)
    return await create_invitation_response(db, tenant_id, invite_data, current_user)


@router.get("/invites/{token}", response_model=InvitationPreviewResponse)
async def preview_invitation(token: str, db: Session = Depends(get_db)):
    """Get invitation details by token for pre-accept preview."""
    invitation = get_invitation_by_token(db, token)
    if not invitation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")

    return InvitationPreviewResponse(
        token=invitation.token,
        tenant_id=invitation.tenant_id,
        tenant_name=invitation.tenant.name,
        email=invitation.email,
        role=invitation.role,
        expires_at=invitation.expires_at,
        status=invitation.status,
        is_expired=invitation.is_expired,
        is_accepted=invitation.is_accepted,
    )


@router.delete("/tenants/{tenant_id}/invites/{token}", response_model=InvitationRevokeResponse)
async def revoke_tenant_invitation(
    tenant_id: UUID,
    token: str,
    ctx: TenantContext = Depends(require_admin),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke a pending invitation token for a tenant (admin+)."""
    ensure_tenant_access(tenant_id, ctx)
    invitation = get_tenant_invitation_by_token(db, tenant_id, token)
    if not invitation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")

    try:
        invitation = revoke_invitation(db, invitation)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    log_audit_event(
        "invitation_revoked",
        actor_user_id=str(current_user.id),
        tenant_id=str(tenant_id),
        invitation_id=str(invitation.id),
        invited_email=invitation.email,
    )

    return InvitationRevokeResponse(
        invitation_id=invitation.id,
        tenant_id=invitation.tenant_id,
        status="revoked",
        message="Invitation revoked successfully",
    )


@router.post("/invites/accept", response_model=InvitationAcceptResponse)
async def accept_invitation_token(
    payload: InvitationAcceptRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Accept an invitation token for the authenticated user."""
    invitation = get_invitation_by_token(db, payload.token)
    if not invitation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")

    try:
        membership = accept_invitation(db, invitation, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    log_audit_event(
        "invitation_accepted",
        actor_user_id=str(current_user.id),
        tenant_id=str(membership.tenant_id),
        invitation_id=str(invitation.id),
        role=membership.role,
    )

    return InvitationAcceptResponse(
        tenant_id=membership.tenant_id,
        role=membership.role,
        message="Invitation accepted successfully",
    )
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models.user import User
from ..schemas.invitation import InvitationCreateRequest, InvitationCreateResponse
from ..security import TenantContext
from ..services.audit_service import log_audit_event
from ..services.email_service import send_invitation_email
from ..services.invitation_service import create_invitation


def ensure_tenant_access(tenant_id: UUID, ctx: TenantContext) -> None:
    if tenant_id != ctx.tenant_id and not ctx.is_platform_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant mismatch")


def ensure_platform_admin(current_user: User, action: str) -> None:
    if not current_user.is_platform_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Only platform administrators can {action} user accounts",
        )


def ensure_not_self_target(target_user_id: UUID, current_user: User) -> None:
    if current_user.id == target_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot suspend your own account",
        )


def build_user_status_response(user: User, message: str, suspended_at: str | None):
    return {
        "user_id": str(user.id),
        "email": user.email,
        "is_platform_admin": user.is_platform_admin,
        "is_active": user.is_active,
        "suspended_at": suspended_at,
        "message": message,
    }


async def create_invitation_response(
    db: Session,
    tenant_id: UUID,
    invite_data: InvitationCreateRequest,
    current_user: User,
) -> InvitationCreateResponse:
    invitation = create_invitation(
        db=db,
        tenant_id=tenant_id,
        email=invite_data.email,
        role=invite_data.role,
        created_by=current_user.id,
    )

    settings = get_settings()
    invite_url = f"{settings.frontend_url}/invite/{invitation.token}"
    email_result = await send_invitation_email(
        to_email=invitation.email,
        invite_url=invite_url,
        tenant_name=invitation.tenant.name,
    )

    log_audit_event(
        "invitation_created",
        actor_user_id=str(current_user.id),
        tenant_id=str(tenant_id),
        invited_email=invite_data.email,
        invited_role=invite_data.role,
        invitation_id=str(invitation.id),
        email_sent=email_result.sent,
        email_provider=email_result.provider,
    )

    message = "Invitation created successfully"
    if not email_result.sent:
        message = f"Invitation created; email not sent ({email_result.detail})"

    return InvitationCreateResponse(
        invitation_id=invitation.id,
        tenant_id=invitation.tenant_id,
        email=invitation.email,
        role=invitation.role,
        token=invitation.token,
        expires_at=invitation.expires_at,
        message=message,
        status=invitation.status,
        email_sent=email_result.sent,
        email_detail=email_result.detail,
    )
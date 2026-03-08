"""
Invitation service - token-based invitations and acceptance workflow
"""
from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from uuid import UUID

from sqlalchemy.orm import Session

from ..models.invitation import Invitation
from ..models.membership import Membership
from ..models.user import User


ROLE_LEVELS = {
    "owner": 4,
    "admin": 3,
    "member": 2,
    "viewer": 1,
}


def utc_now() -> datetime:
    """Return naive UTC datetime compatible with existing DB DateTime columns."""
    return datetime.now(UTC).replace(tzinfo=None)


def create_invitation(
    db: Session,
    tenant_id: UUID,
    email: str,
    role: str,
    created_by: UUID,
    expires_in_days: int = 7,
) -> Invitation:
    """Create a new invitation token for a user email within a tenant."""
    invitation = Invitation(
        tenant_id=tenant_id,
        email=email.lower().strip(),
        role=role,
        token=token_urlsafe(32),
        expires_at=utc_now() + timedelta(days=expires_in_days),
        created_by=created_by,
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)
    return invitation


def get_invitation_by_token(db: Session, token: str) -> Invitation | None:
    """Return invitation by token, or None if missing."""
    return db.query(Invitation).filter(Invitation.token == token).first()


def accept_invitation(db: Session, invitation: Invitation, user: User) -> Membership:
    """
    Accept an invitation for the authenticated user.

    Rules:
    - Invitation must not be expired
    - Invitation must not already be accepted
    - Invitation email must match current user's email
    - Membership is created or re-activated for the invitation tenant
    """
    if invitation.is_expired:
        raise ValueError("Invitation has expired")

    if invitation.is_accepted:
        raise ValueError("Invitation has already been accepted")

    if invitation.email.lower().strip() != (user.email or "").lower().strip():
        raise PermissionError("Invitation email does not match authenticated user")

    membership = db.query(Membership).filter(
        Membership.user_id == user.id,
        Membership.tenant_id == invitation.tenant_id,
    ).first()

    if membership:
        # Never downgrade an existing role through invitation acceptance.
        existing_level = ROLE_LEVELS.get(membership.role, 0)
        invited_level = ROLE_LEVELS.get(invitation.role, 0)
        if existing_level < invited_level:
            membership.role = invitation.role
        membership.status = "active"
    else:
        membership = Membership(
            user_id=user.id,
            tenant_id=invitation.tenant_id,
            role=invitation.role,
            status="active",
        )
        db.add(membership)

    invitation.accepted_at = utc_now()

    db.commit()
    db.refresh(membership)
    return membership

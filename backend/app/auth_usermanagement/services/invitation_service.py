"""
Invitation service - token-based invitations and acceptance workflow
"""
from datetime import UTC, datetime, timedelta
from hashlib import sha256
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


def hash_token(token: str) -> str:
    """Return SHA256 hex digest of a token for secure storage."""
    return sha256(token.encode()).hexdigest()


def create_invitation(
    db: Session,
    tenant_id: UUID,
    email: str,
    role: str,
    created_by: UUID,
    expires_in_days: int = 2,
) -> Invitation:
    """Create a new invitation token for a user email within a tenant.

    If a pending invitation already exists for the same email+tenant, revoke the
    older one so only the latest token remains active.
    
    Args:
        expires_in_days: Days until invitation expires (default 2 days = 48 hours)
    """
    normalized_email = email.lower().strip()
    now = utc_now()

    existing_pending = db.query(Invitation).filter(
        Invitation.tenant_id == tenant_id,
        Invitation.email == normalized_email,
        Invitation.accepted_at.is_(None),
        Invitation.revoked_at.is_(None),
        Invitation.expires_at > now,
    ).all()

    for pending in existing_pending:
        # Revoke previous pending invites so only one active token remains.
        pending.revoked_at = now
        pending.expires_at = now

    raw_token = token_urlsafe(32)
    invitation = Invitation(
        tenant_id=tenant_id,
        email=normalized_email,
        role=role,
        token=raw_token,
        token_hash=hash_token(raw_token),
        expires_at=now + timedelta(days=expires_in_days),
        created_by=created_by,
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)
    return invitation


def get_invitation_by_token(db: Session, token: str) -> Invitation | None:
    """Return invitation by token hash, or None if missing."""
    token_hash = hash_token(token)
    return db.query(Invitation).filter(Invitation.token_hash == token_hash).first()


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

    if invitation.is_revoked:
        raise ValueError("Invitation has been revoked")

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


def get_tenant_invitation_by_token(db: Session, tenant_id: UUID, token: str) -> Invitation | None:
    """Return invitation by token hash scoped to a tenant."""
    token_hash = hash_token(token)
    return db.query(Invitation).filter(
        Invitation.token_hash == token_hash,
        Invitation.tenant_id == tenant_id,
    ).first()


def revoke_invitation(db: Session, invitation: Invitation) -> Invitation:
    """Mark a pending invitation as revoked."""
    if invitation.is_accepted:
        raise ValueError("Accepted invitations cannot be revoked")
    if invitation.is_revoked:
        raise ValueError("Invitation is already revoked")

    now = utc_now()
    invitation.revoked_at = now
    if invitation.expires_at > now:
        invitation.expires_at = now

    db.commit()
    db.refresh(invitation)
    return invitation

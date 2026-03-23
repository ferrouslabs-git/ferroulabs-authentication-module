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
from .auth_config_loader import get_auth_config


# Legacy role → v3 role name mapping (used to derive target_role_name from
# the legacy 'role' API field when callers haven't migrated yet).
_LEGACY_TO_V3 = {
    "owner": "account_owner",
    "admin": "account_admin",
    "member": "account_member",
    "viewer": "account_member",
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
    target_scope_type: str | None = None,
    target_scope_id: UUID | None = None,
    target_role_name: str | None = None,
) -> tuple["Invitation", str]:
    """Create a new invitation token for a user email within a tenant/scope.

    Returns:
        Tuple of (invitation, raw_token). The raw_token is NOT stored in the
        database — only its SHA-256 hash is persisted. The caller must use the
        returned raw_token for email URLs and API responses.

    If a pending invitation already exists for the same email+tenant, revoke the
    older one so only the latest token remains active.
    
    Args:
        expires_in_days: Days until invitation expires (default 2 days = 48 hours)
        role: Legacy role string (used to derive target_role_name if not provided)
        target_scope_type: 'account' or 'space'. Defaults to 'account'.
        target_scope_id: UUID of scope. Defaults to tenant_id.
        target_role_name: v3 role name. Derived from 'role' if not provided.
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
        pending.revoked_at = now
        pending.expires_at = now

    raw_token = token_urlsafe(32)
    hashed = hash_token(raw_token)
    resolved_scope_type = target_scope_type or "account"
    resolved_scope_id = target_scope_id or tenant_id
    resolved_role_name = target_role_name or _LEGACY_TO_V3.get(role, role)
    invitation = Invitation(
        tenant_id=tenant_id,
        email=normalized_email,
        token=hashed,
        token_hash=hashed,
        expires_at=now + timedelta(days=expires_in_days),
        created_by=created_by,
        target_scope_type=resolved_scope_type,
        target_scope_id=resolved_scope_id,
        target_role_name=resolved_role_name,
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)
    return invitation, raw_token


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
    - Membership is created or re-activated for the invitation scope
    """
    if invitation.is_expired:
        raise ValueError("Invitation has expired")

    if invitation.is_revoked:
        raise ValueError("Invitation has been revoked")

    if invitation.is_accepted:
        raise ValueError("Invitation has already been accepted")

    if invitation.email.lower().strip() != (user.email or "").lower().strip():
        raise PermissionError("Invitation email does not match authenticated user")

    # Look for existing membership in the target scope
    membership = db.query(Membership).filter(
        Membership.user_id == user.id,
        Membership.scope_type == invitation.target_scope_type,
        Membership.scope_id == invitation.target_scope_id,
    ).first()

    role_name = invitation.target_role_name
    scope_type = invitation.target_scope_type
    scope_id = invitation.target_scope_id

    if membership:
        # Compare permission sets: never downgrade through invitation.
        config = get_auth_config()
        existing_role = membership.role_name
        existing_perms = config.permissions_for_role(existing_role)
        invited_perms = config.permissions_for_role(role_name)

        if not invited_perms.issubset(existing_perms):
            membership.role_name = role_name
            membership.scope_type = scope_type
            membership.scope_id = scope_id
        membership.status = "active"
    else:
        membership = Membership(
            user_id=user.id,
            scope_type=scope_type,
            scope_id=scope_id,
            role_name=role_name,
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

"""
User service - handles user sync and lookup operations
"""
import logging

import boto3
from botocore.exceptions import ClientError
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID
from datetime import datetime, UTC

from ..config import get_settings
from ..models.user import User
from ..models.membership import Membership
from ..models.session import Session as AuthSession
from ..models.invitation import Invitation
from ..schemas.token import TokenPayload

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    """Return current UTC datetime without timezone info (for SQLAlchemy)."""
    return datetime.now(UTC).replace(tzinfo=None)


def sync_user_from_cognito(token_payload: TokenPayload, db: Session) -> User:
    """
    Sync Cognito user to database.
    Creates new user if doesn't exist, updates if exists.
    Idempotent - safe to call multiple times.
    
    Handles edge case where Cognito user was deleted/recreated with same email
    but different cognito_sub by updating the existing DB user's cognito_sub.
    
    Args:
        token_payload: JWT token payload from Cognito
        db: Database session
    
    Returns:
        User: Created or existing user
    """
    if not token_payload.email:
        raise ValueError("Token missing email claim for user provisioning")
    
    # Check if user already exists by cognito_sub
    user = get_user_by_cognito_sub(token_payload.sub, db)
    
    if user:
        # Update existing user (in case email or name changed in Cognito)
        if token_payload.email:
            user.email = token_payload.email
        if token_payload.name:
            user.name = token_payload.name
        db.commit()
        db.refresh(user)
    else:
        # Check if user exists by email (handles Cognito user recreation)
        user = get_user_by_email(token_payload.email, db)
        
        if user:
            # Update cognito_sub for existing email-matched user
            user.cognito_sub = token_payload.sub
            if token_payload.name:
                user.name = token_payload.name
            db.commit()
            db.refresh(user)
        else:
            # Create new user
            user = User(
                cognito_sub=token_payload.sub,
                email=token_payload.email,
                name=token_payload.name if token_payload.name else None
            )
            db.add(user)
            db.commit()
            db.refresh(user)
    
    return user


def get_user_by_cognito_sub(cognito_sub: str, db: Session) -> Optional[User]:
    """
    Get user by Cognito sub (unique identifier).
    
    Args:
        cognito_sub: Cognito user identifier from JWT
        db: Database session
    
    Returns:
        User if found, None otherwise
    """
    return db.query(User).filter(User.cognito_sub == cognito_sub).first()


def get_user_by_id(user_id: UUID, db: Session) -> Optional[User]:
    """
    Get user by internal UUID.
    
    Args:
        user_id: Internal user UUID
        db: Database session
    
    Returns:
        User if found, None otherwise
    """
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_email(email: str, db: Session) -> Optional[User]:
    """
    Get user by email address.
    
    Args:
        email: User email address
        db: Database session
    
    Returns:
        User if found, None otherwise
    """
    return db.query(User).filter(User.email == email).first()


def suspend_user(user_id: UUID, db: Session) -> User:
    """
    Suspend a user account.

    Also calls Cognito ``AdminUserGlobalSignOut`` to invalidate all
    outstanding refresh tokens so the user cannot silently re-acquire
    new access tokens after suspension.
    
    Args:
        user_id: User ID to suspend
        db: Database session
    
    Returns:
        Updated user
    
    Raises:
        ValueError: If user not found
    """
    user = get_user_by_id(user_id, db)
    if not user:
        raise ValueError(f"User {user_id} not found")
    
    user.is_active = False
    user.suspended_at = utc_now()
    db.commit()
    db.refresh(user)

    _cognito_global_sign_out(user.cognito_sub)

    return user


def _cognito_global_sign_out(cognito_sub: str) -> None:
    """Best-effort Cognito global sign-out. Never raises."""
    settings = get_settings()
    if not settings.cognito_user_pool_id:
        logger.debug("Cognito user pool not configured; skipping global sign-out")
        return

    try:
        client = boto3.client("cognito-idp", region_name=settings.cognito_region)
        client.admin_user_global_sign_out(
            UserPoolId=settings.cognito_user_pool_id,
            Username=cognito_sub,
        )
        logger.info("Cognito global sign-out succeeded for %s", cognito_sub)
    except ClientError as exc:
        logger.warning(
            "Cognito global sign-out failed for %s: %s",
            cognito_sub,
            exc.response["Error"]["Message"],
        )
    except Exception:
        logger.exception("Unexpected error during Cognito global sign-out")


def unsuspend_user(user_id: UUID, db: Session) -> User:
    """
    Unsuspend a user account.
    
    Args:
        user_id: User ID to unsuspend
        db: Database session
    
    Returns:
        Updated user
    
    Raises:
        ValueError: If user not found
    """
    user = get_user_by_id(user_id, db)
    if not user:
        raise ValueError(f"User {user_id} not found")
    
    user.is_active = True
    user.suspended_at = None
    db.commit()
    db.refresh(user)
    return user


def promote_to_platform_admin(user_id: UUID, db: Session) -> User:
    """Grant platform admin access to a user."""
    user = get_user_by_id(user_id, db)
    if not user:
        raise ValueError(f"User {user_id} not found")

    user.is_platform_admin = True
    db.commit()
    db.refresh(user)
    return user


def demote_from_platform_admin(user_id: UUID, db: Session) -> User:
    """Remove platform admin access from a user while preserving at least one admin."""
    user = get_user_by_id(user_id, db)
    if not user:
        raise ValueError(f"User {user_id} not found")

    if user.is_platform_admin:
        admin_count = db.query(User).filter(User.is_platform_admin.is_(True)).count()
        if admin_count <= 1:
            raise ValueError("Cannot remove the last platform administrator")

    user.is_platform_admin = False
    db.commit()
    db.refresh(user)
    return user


def delete_user(user_id: UUID, db: Session) -> dict:
    """Permanently delete a user from Cognito and the local database.

    Performs full cleanup in order:
    1. Delete user from Cognito user pool
    2. Revoke all local sessions
    3. Remove all memberships
    4. Anonymize invitations created by this user
    5. Delete the User record

    Raises ValueError if the user is a platform admin (must be demoted first)
    or the last owner of any tenant.
    """
    from .cognito_admin_service import admin_delete_user as cognito_delete

    user = get_user_by_id(user_id, db)
    if not user:
        raise ValueError(f"User {user_id} not found")

    if user.is_platform_admin:
        raise ValueError("Cannot delete a platform admin. Demote them first.")

    # Check that the user is not the last owner of any tenant
    owner_memberships = (
        db.query(Membership)
        .filter(
            Membership.user_id == user_id,
            Membership.status == "active",
            Membership.scope_type == "account",
            Membership.role_name.in_(["owner", "account_owner"]),
        )
        .all()
    )
    for m in owner_memberships:
        owner_count = (
            db.query(Membership)
            .filter(
                Membership.scope_type == "account",
                Membership.scope_id == m.scope_id,
                Membership.status == "active",
                Membership.role_name.in_(["owner", "account_owner"]),
            )
            .count()
        )
        if owner_count <= 1:
            raise ValueError(
                f"User is the last owner of tenant {m.scope_id}. Transfer ownership first."
            )

    # 1. Delete from Cognito
    cognito_result = cognito_delete(user.email)
    if "error" in cognito_result:
        raise ValueError(f"Cognito deletion failed: {cognito_result['error']}")

    # 2. Revoke all sessions
    db.query(AuthSession).filter(AuthSession.user_id == user_id).delete()

    # 3. Remove all memberships
    db.query(Membership).filter(Membership.user_id == user_id).delete()

    # 4. Nullify invitations created by this user (preserve audit trail)
    db.query(Invitation).filter(Invitation.created_by == user_id).update(
        {"created_by": None}
    )

    # 5. Delete the user record
    db.delete(user)
    db.commit()

    logger.info("Permanently deleted user", extra={"user_id": str(user_id), "email": user.email})

    return {
        "deleted": True,
        "user_id": str(user_id),
        "email": user.email,
        "cognito_deleted": cognito_result.get("deleted", False),
    }

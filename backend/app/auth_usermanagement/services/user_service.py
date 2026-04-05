"""
User service - handles user sync and lookup operations
"""
import asyncio
import logging

import boto3
from botocore.exceptions import ClientError
from sqlalchemy import select, func, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
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


async def sync_user_from_cognito(token_payload: TokenPayload, db: AsyncSession) -> User:
    """
    Sync Cognito user to database.
    Creates new user if doesn't exist, updates if exists.
    Idempotent - safe to call multiple times.
    
    Handles edge case where Cognito user was deleted/recreated with same email
    but different cognito_sub by updating the existing DB user's cognito_sub.
    """
    if not token_payload.email:
        raise ValueError("Token missing email claim for user provisioning")
    
    user = await get_user_by_cognito_sub(token_payload.sub, db)
    
    if user:
        if token_payload.email:
            user.email = token_payload.email
        if token_payload.name:
            user.name = token_payload.name
        await db.commit()
        await db.refresh(user)
    else:
        user = await get_user_by_email(token_payload.email, db)
        
        if user:
            user.cognito_sub = token_payload.sub
            if token_payload.name:
                user.name = token_payload.name
            await db.commit()
            await db.refresh(user)
        else:
            user = User(
                cognito_sub=token_payload.sub,
                email=token_payload.email,
                name=token_payload.name if token_payload.name else None
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
    
    return user


async def get_user_by_cognito_sub(cognito_sub: str, db: AsyncSession) -> Optional[User]:
    """Get user by Cognito sub (unique identifier)."""
    result = await db.execute(select(User).where(User.cognito_sub == cognito_sub))
    return result.scalar_one_or_none()


async def get_user_by_id(user_id: UUID, db: AsyncSession) -> Optional[User]:
    """Get user by internal UUID."""
    result = await db.execute(
        select(User)
        .options(
            selectinload(User.memberships).selectinload(Membership.tenant)
        )
        .where(User.id == user_id)
    )
    return result.scalar_one_or_none()


async def get_user_by_email(email: str, db: AsyncSession) -> Optional[User]:
    """Get user by email address."""
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def suspend_user(user_id: UUID, db: AsyncSession) -> User:
    """
    Suspend a user account.

    Also calls Cognito AdminUserGlobalSignOut to invalidate all
    outstanding refresh tokens so the user cannot silently re-acquire
    new access tokens after suspension.
    """
    user = await get_user_by_id(user_id, db)
    if not user:
        raise ValueError(f"User {user_id} not found")
    
    user.is_active = False
    user.suspended_at = utc_now()
    await db.commit()
    await db.refresh(user)

    await asyncio.to_thread(_cognito_global_sign_out, user.cognito_sub)

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


async def unsuspend_user(user_id: UUID, db: AsyncSession) -> User:
    """Unsuspend a user account."""
    user = await get_user_by_id(user_id, db)
    if not user:
        raise ValueError(f"User {user_id} not found")
    
    user.is_active = True
    user.suspended_at = None
    await db.commit()
    await db.refresh(user)
    return user


async def promote_to_platform_admin(user_id: UUID, db: AsyncSession) -> User:
    """Grant platform admin access to a user."""
    user = await get_user_by_id(user_id, db)
    if not user:
        raise ValueError(f"User {user_id} not found")

    user.is_platform_admin = True
    await db.commit()
    await db.refresh(user)
    return user


async def demote_from_platform_admin(user_id: UUID, db: AsyncSession) -> User:
    """Remove platform admin access from a user while preserving at least one admin."""
    user = await get_user_by_id(user_id, db)
    if not user:
        raise ValueError(f"User {user_id} not found")

    if user.is_platform_admin:
        result = await db.execute(
            select(func.count()).select_from(User).where(User.is_platform_admin.is_(True))
        )
        admin_count = result.scalar()
        if admin_count <= 1:
            raise ValueError("Cannot remove the last platform administrator")

    user.is_platform_admin = False
    await db.commit()
    await db.refresh(user)
    return user


async def delete_user(user_id: UUID, db: AsyncSession) -> dict:
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

    user = await get_user_by_id(user_id, db)
    if not user:
        raise ValueError(f"User {user_id} not found")

    if user.is_platform_admin:
        raise ValueError("Cannot delete a platform admin. Demote them first.")

    # Check that the user is not the last owner of any tenant
    result = await db.execute(
        select(Membership).where(
            Membership.user_id == user_id,
            Membership.status == "active",
            Membership.scope_type == "account",
            Membership.role_name.in_(["owner", "account_owner"]),
        )
    )
    owner_memberships = result.scalars().all()

    for m in owner_memberships:
        count_result = await db.execute(
            select(func.count()).select_from(Membership).where(
                Membership.scope_type == "account",
                Membership.scope_id == m.scope_id,
                Membership.status == "active",
                Membership.role_name.in_(["owner", "account_owner"]),
            )
        )
        owner_count = count_result.scalar()
        if owner_count <= 1:
            raise ValueError(
                f"User is the last owner of tenant {m.scope_id}. Transfer ownership first."
            )

    # 1. Delete from Cognito (blocking boto3, offload to thread)
    cognito_result = await asyncio.to_thread(cognito_delete, user.email)
    if "error" in cognito_result:
        raise ValueError(f"Cognito deletion failed: {cognito_result['error']}")

    # 2. Revoke all sessions
    await db.execute(delete(AuthSession).where(AuthSession.user_id == user_id))

    # 3. Remove all memberships
    await db.execute(delete(Membership).where(Membership.user_id == user_id))

    # 4. Nullify invitations created by this user (preserve audit trail)
    await db.execute(
        update(Invitation).where(Invitation.created_by == user_id).values(created_by=None)
    )

    # 5. Delete the user record
    await db.delete(user)
    await db.commit()

    logger.info("Permanently deleted user", extra={"user_id": str(user_id), "email": user.email})

    return {
        "deleted": True,
        "user_id": str(user_id),
        "email": user.email,
        "cognito_deleted": cognito_result.get("deleted", False),
    }

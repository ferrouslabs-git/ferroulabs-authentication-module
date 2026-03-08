"""
User service - handles user sync and lookup operations
"""
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID
from datetime import datetime, UTC

from ..models.user import User
from ..schemas.token import TokenPayload


def utc_now() -> datetime:
    """Return current UTC datetime without timezone info (for SQLAlchemy)."""
    return datetime.now(UTC).replace(tzinfo=None)


def sync_user_from_cognito(token_payload: TokenPayload, db: Session) -> User:
    """
    Sync Cognito user to database.
    Creates new user if doesn't exist, updates if exists.
    Idempotent - safe to call multiple times.
    
    Args:
        token_payload: JWT token payload from Cognito
        db: Database session
    
    Returns:
        User: Created or existing user
    """
    # Check if user already exists
    user = get_user_by_cognito_sub(token_payload.sub, db)
    
    if user:
        # Update existing user (in case email or name changed in Cognito)
        user.email = token_payload.email
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
    return user


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

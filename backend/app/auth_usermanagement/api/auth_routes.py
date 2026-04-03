from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db

from ..models.membership import Membership
from ..models.tenant import Tenant
from ..models.user import User
from ..schemas.user_management import MembershipListResponse
from ..security import InvalidTokenError, get_current_user, verify_token_async
from ..services.user_service import sync_user_from_cognito

router = APIRouter()


@router.get("/debug-token")
async def debug_token(authorization: Optional[str] = Header(None)):
    """
    Debug endpoint to test JWT token verification.

    Phase 1 Test Checkpoint:
    1. Get token from Cognito Hosted UI
    2. Call: curl -H "Authorization: Bearer <token>" http://localhost:8000/auth/debug-token
    3. Expected: User claims returned

    Returns:
        TokenPayload: Decoded and verified JWT claims
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication scheme. Use 'Bearer <token>'",
            )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Use 'Bearer <token>'",
        )

    try:
        payload = await verify_token_async(token)
        claims = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
        return {
            "status": "valid",
            "message": "Token verified successfully",
            "claims": claims,
        }
    except InvalidTokenError as exc:
        raise exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token verification failed: {str(exc)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/sync")
async def sync_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Sync Cognito user to database.
    Called after successful Cognito login.

    Phase 3 Test Checkpoint:
    1. Login via Cognito Hosted UI
    2. Get id_token or access_token
    3. Call: curl -X POST -H "Authorization: Bearer <token>" http://localhost:8000/auth/sync
    4. Expected: User created in database

    This endpoint is idempotent - safe to call multiple times.
    Updates email/name if changed in Cognito.

    Returns:
        User details: user_id, email, name
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication scheme. Use 'Bearer <token>'",
            )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Use 'Bearer <token>'",
        )

    try:
        token_payload = await verify_token_async(token, allowed_token_uses=("access", "id"))
    except InvalidTokenError as exc:
        raise exc

    try:
        user = sync_user_from_cognito(token_payload, db)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return {
        "user_id": str(user.id),
        "email": user.email,
        "name": user.name,
        "cognito_sub": user.cognito_sub,
        "is_platform_admin": user.is_platform_admin,
        "created_at": user.created_at.isoformat(),
        "message": "User synced successfully",
    }


@router.get("/me")
async def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """Get authenticated user profile."""
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "name": current_user.name,
        "cognito_sub": current_user.cognito_sub,
        "is_platform_admin": current_user.is_platform_admin,
        "created_at": current_user.created_at.isoformat(),
        "updated_at": current_user.updated_at.isoformat(),
    }


@router.get("/me/memberships", response_model=list[MembershipListResponse])
async def get_my_memberships(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all memberships for the authenticated user."""
    memberships = (
        db.query(Membership)
        .filter(Membership.user_id == current_user.id, Membership.status == "active")
        .all()
    )
    results = []
    for m in memberships:
        tenant_name = None
        if m.scope_type == "account":
            tenant = db.query(Tenant).filter(Tenant.id == m.scope_id).first()
            if tenant:
                tenant_name = tenant.name
        results.append(
            MembershipListResponse(
                scope_type=m.scope_type,
                scope_id=m.scope_id,
                role=m.role_name,
                status=m.status,
                tenant_id=m.scope_id if m.scope_type == "account" else None,
                tenant_name=tenant_name,
                joined_at=m.created_at,
            )
        )
    return results
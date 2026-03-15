"""
Authentication dependencies for FastAPI endpoints
"""
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import text
from sqlalchemy.orm import Session
from uuid import UUID

from app.database import get_db
from ..security.jwt_verifier import verify_token
from ..security.tenant_context import TenantContext
from ..services.user_service import get_user_by_cognito_sub
from ..models.membership import Membership
from ..models.user import User


# OAuth2 bearer token scheme (extracts token from Authorization header)
# auto_error=False lets optional auth dependencies handle missing headers safely.
oauth2_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Verify JWT token and return current authenticated user.
    
    This dependency:
    1. Extracts token from Authorization header
    2. Verifies JWT signature and claims
    3. Loads user from database
    4. Returns User object for use in endpoints
    
    Usage:
        @router.get("/me")
        async def get_profile(current_user: User = Depends(get_current_user)):
            return {"email": current_user.email}
    
    Args:
        credentials: HTTP bearer token from Authorization header
        db: Database session
    
    Returns:
        User: Authenticated user from database
    
    Raises:
        HTTPException 401: If token is invalid or expired
        HTTPException 404: If user not found in database
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract token from credentials
    token = credentials.credentials
    
    # Verify JWT and get payload (raises 401 if invalid)
    token_payload = verify_token(token)
    
    # Load user from database
    user = get_user_by_cognito_sub(token_payload.sub, db)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found. Please sync your account first by calling POST /auth/sync"
        )
    
    # Check if user account is suspended
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account suspended. Please contact your administrator.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User | None:
    """
    Optional authentication - returns User if token valid, None if missing/invalid.
    Useful for endpoints that support both authenticated and anonymous access.
    
    Args:
        credentials: HTTP bearer token from Authorization header (optional)
        db: Database session
    
    Returns:
        User if authenticated, None otherwise
    """
    if not credentials:
        return None
    
    try:
        token = credentials.credentials
        token_payload = verify_token(token)
        return get_user_by_cognito_sub(token_payload.sub, db)
    except HTTPException:
        return None


def get_tenant_context(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TenantContext:
    """
    Get current request's tenant context.
    
    This dependency validates tenant membership using the same request-scoped
    DB session used by endpoint handlers.
    
    Usage:
        @router.get("/data")
        async def get_data(ctx: TenantContext = Depends(get_tenant_context)):
            # ctx.tenant_id → current tenant UUID
            # ctx.user_id → authenticated user UUID
            # ctx.role → user's role in this tenant
            # ctx.is_platform_admin → platform admin flag
            
            # Query data scoped to ctx.tenant_id
            return db.query(Data).filter(Data.tenant_id == ctx.tenant_id).all()
    
    Args:
        request: FastAPI request object (auto-injected)
    
    Returns:
        TenantContext: Current tenant context with user/tenant/role info
    
    Raises:
        HTTPException 400: Missing or invalid X-Tenant-ID header
        HTTPException 403: User not authorized for requested tenant
    """
    if hasattr(request.state, "tenant_context"):
        return request.state.tenant_context

    tenant_id_str = request.headers.get("X-Tenant-ID")
    if not tenant_id_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Tenant-ID header required",
        )

    try:
        tenant_id = UUID(tenant_id_str)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid X-Tenant-ID format. Must be a valid UUID",
        ) from exc

    membership = db.query(Membership).filter(
        Membership.user_id == current_user.id,
        Membership.tenant_id == tenant_id,
        Membership.status == "active",
    ).first()

    if not membership and not current_user.is_platform_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You are not a member of this tenant",
        )

    role = membership.role if membership else "platform_admin"
    ctx = TenantContext(
        user_id=current_user.id,
        tenant_id=tenant_id,
        role=role,
        is_platform_admin=current_user.is_platform_admin,
    )

    request.state.tenant_context = ctx

    # Apply RLS session variables only for PostgreSQL-backed sessions.
    bind = db.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        db.execute(
            text("SET LOCAL app.current_tenant_id = :tenant_id"),
            {"tenant_id": str(tenant_id)},
        )
        db.execute(
            text("SET LOCAL app.is_platform_admin = :is_admin"),
            {"is_admin": "true" if current_user.is_platform_admin else "false"},
        )

    return ctx

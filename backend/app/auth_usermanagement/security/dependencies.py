"""
Authentication dependencies for FastAPI endpoints
"""
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from ..database import get_db
from ..security.jwt_verifier import verify_token
from ..security.tenant_context import TenantContext
from ..services.user_service import get_user_by_cognito_sub
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


def get_tenant_context(request: Request) -> TenantContext:
    """
    Get current request's tenant context.
    
    This dependency extracts the TenantContext populated by TenantContextMiddleware.
    Use this in endpoints that need tenant-scoped operations.
    
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
        HTTPException 500: If middleware didn't populate context (config error)
    """
    if not hasattr(request.state, "tenant_context"):
        raise HTTPException(
            status_code=500,
            detail="Tenant context not available. Ensure TenantContextMiddleware is registered."
        )
    
    return request.state.tenant_context

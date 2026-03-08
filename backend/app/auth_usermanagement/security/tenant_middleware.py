"""
Tenant Context Middleware - enforces multi-tenant isolation

This middleware:
1. Extracts X-Tenant-ID header from request
2. Validates user has active membership in that tenant
3. Populates request.state.tenant_context for downstream handlers
4. Blocks unauthorized cross-tenant access
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from sqlalchemy.orm import Session
from sqlalchemy import text
from uuid import UUID

from ..database import SessionLocal
from ..security.jwt_verifier import verify_token, InvalidTokenError
from ..security.tenant_context import TenantContext
from ..models.user import User
from ..models.membership import Membership


class TenantContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce tenant isolation and populate tenant context.
    
    Routes that require tenant context:
    - All /auth/* routes EXCEPT /auth/sync, /auth/debug-token, /auth/me, /auth/tenants
    
    Public routes (skip middleware):
    - /health
    - /auth/sync (initial user sync, no tenant yet)
    - /auth/debug-token (phase 1 test endpoint)
    - /auth/me (user profile, no tenant context needed)
    - /auth/tenants (tenant creation/listing, no specific tenant context)
    - POST /auth/tenants (tenant creation)
    - GET /auth/tenants/my (list user's tenants)
    
    For protected routes:
    - Requires X-Tenant-ID header
    - Validates user membership in that tenant
    - Populates request.state.tenant_context
    """
    
    # Routes that don't require tenant context
    SKIP_ROUTES = {
        "/health",
        "/auth/sync",
        "/auth/debug-token",
        "/auth/me",
        "/auth/tenants",
        "/auth/tenants/my",
    }
    
    async def dispatch(self, request: Request, call_next):
        """Process request and validate tenant access."""
        
        # Skip middleware for public/tenant-agnostic routes
        if self._should_skip_middleware(request):
            return await call_next(request)
        
        # Get tenant ID from header
        tenant_id_str = request.headers.get("X-Tenant-ID")
        
        if not tenant_id_str:
            return JSONResponse(
                status_code=400,
                content={
                    "detail": "X-Tenant-ID header required",
                    "hint": "Pass tenant UUID in X-Tenant-ID header"
                }
            )
        
        # Validate UUID format
        try:
            tenant_id = UUID(tenant_id_str)
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid X-Tenant-ID format. Must be a valid UUID"}
            )
        
        # Get and verify JWT token
        auth_header = request.headers.get("Authorization", "")
        
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Authorization header missing or invalid"}
            )
        
        token = auth_header.replace("Bearer ", "")
        
        # Verify token
        try:
            token_payload = verify_token(token)
        except InvalidTokenError as e:
            return JSONResponse(
                status_code=401,
                content={"detail": str(e)}
            )
        
        # Load user and verify tenant membership
        db: Session = SessionLocal()
        try:
            # Get user by cognito_sub
            user = db.query(User).filter(User.cognito_sub == token_payload.sub).first()
            
            if not user:
                return JSONResponse(
                    status_code=404,
                    content={
                        "detail": "User not found in database",
                        "hint": "Call POST /auth/sync first to create user record"
                    }
                )
            
            # Check membership in requested tenant
            membership = db.query(Membership).filter(
                Membership.user_id == user.id,
                Membership.tenant_id == tenant_id,
                Membership.status == "active"
            ).first()
            
            # Platform admins can access any tenant
            if not membership and not user.is_platform_admin:
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": "Access denied: You are not a member of this tenant",
                        "tenant_id": str(tenant_id)
                    }
                )
            
            # Create tenant context
            role = membership.role if membership else "platform_admin"
            
            request.state.tenant_context = TenantContext(
                user_id=user.id,
                tenant_id=tenant_id,
                role=role,
                is_platform_admin=user.is_platform_admin
            )
            
            # Set PostgreSQL session variables for Row-Level Security
            db.execute(
                text("SET LOCAL app.current_tenant_id = :tenant_id"),
                {"tenant_id": str(tenant_id)}
            )
            db.execute(
                text("SET LOCAL app.is_platform_admin = :is_admin"),
                {"is_admin": "true" if user.is_platform_admin else "false"}
            )
            db.commit()
            
            # Continue to endpoint
            response = await call_next(request)
            return response
            
        finally:
            db.close()
    
    def _should_skip_middleware(self, request: Request) -> bool:
        """
        Check if request should skip tenant context validation.
        
        Skips for:
        - Public routes (health check)
        - Auth initialization routes (sync, tenant creation)
        - Exact path matches in SKIP_ROUTES
        """
        path = request.url.path

        # Apply tenant validation only to auth routes.
        if not path.startswith("/auth"):
            return True
        
        # Exact match
        if path in self.SKIP_ROUTES:
            return True
        
        # Allow POST /auth/tenants (tenant creation)
        if path == "/auth/tenants" and request.method == "POST":
            return True
        
        # Allow GET /auth/tenants/my (list user's tenants)
        if path == "/auth/tenants/my" and request.method == "GET":
            return True

        # Allow invitation token routes (do not require tenant header)
        if path.startswith("/auth/invites/"):
            return True

        # Session revocation routes are user-scoped, not tenant-scoped.
        if path.startswith("/auth/sessions"):
            return True
        
        return False

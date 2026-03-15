"""Tenant Context Middleware request prechecks for protected auth routes.

This middleware:
1. Enforces presence and format of X-Tenant-ID on protected routes
2. Enforces Bearer Authorization header presence
3. Stores requested tenant ID on request.state

Tenant membership validation and tenant context creation are intentionally
handled in dependency flow using the same request-scoped DB session as handlers.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from uuid import UUID

class TenantContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce tenant request prechecks.
    
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
    - Validates header UUID format
    - Requires Bearer Authorization header
    - Stores request.state.requested_tenant_id for downstream use
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
        
        # Ensure auth header is present and has Bearer scheme.
        auth_header = request.headers.get("Authorization", "")
        
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Authorization header missing or invalid"}
            )

        # Middleware intentionally does not create DB sessions.
        # Tenant membership validation and context creation happen in dependencies
        # using the same request-scoped DB session as endpoint handlers.
        request.state.requested_tenant_id = tenant_id

        return await call_next(request)
    
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

        # Cookie management and token refresh are user-scoped, not tenant-scoped.
        if path.startswith("/auth/cookie/") or path == "/auth/token/refresh":
            return True
        
        return False

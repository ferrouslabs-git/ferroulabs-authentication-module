"""
Security utilities for auth module

Includes:
- JWT verification from Cognito
- TenantContext middleware (critical for multi-tenancy)
- Role-based authorization guards
- Permission checking utilities
"""
from .jwt_verifier import verify_token, verify_token_optional, InvalidTokenError
from .dependencies import get_current_user, get_current_user_optional, oauth2_scheme, get_tenant_context
from .tenant_context import TenantContext
from .tenant_middleware import TenantContextMiddleware
from .security_headers_middleware import SecurityHeadersMiddleware
from .rate_limit_middleware import RateLimitMiddleware
from .guards import (
    require_role,
    require_min_role,
    require_owner,
    require_admin,
    require_member,
    require_viewer,
    check_permission,
    require_permission,
)

__all__ = [
    "verify_token",
    "verify_token_optional",
    "InvalidTokenError",
    "get_current_user",
    "get_current_user_optional",
    "oauth2_scheme",
    "get_tenant_context",
    "TenantContext",
    "TenantContextMiddleware",
    "SecurityHeadersMiddleware",
    "RateLimitMiddleware",
    "require_role",
    "require_min_role",
    "require_owner",
    "require_admin",
    "require_member",
    "require_viewer",
    "check_permission",
    "require_permission",
]

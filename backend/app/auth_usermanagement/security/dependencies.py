"""
Authentication dependencies for FastAPI endpoints
"""
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import text
from sqlalchemy.orm import Session
from uuid import UUID

from ..database import get_db
from ..security.jwt_verifier import verify_token, verify_token_async
from ..security.tenant_context import TenantContext
from ..security.scope_context import ScopeContext
from ..services.user_service import get_user_by_cognito_sub
from ..services.auth_config_loader import get_auth_config
from ..models.membership import Membership
from ..models.space import Space
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
    token_payload = await verify_token_async(token)
    
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
        token_payload = await verify_token_async(token)
        return get_user_by_cognito_sub(token_payload.sub, db)
    except HTTPException:
        return None


# ── Role mapping helpers ─────────────────────────────────────────

_V3_TO_LEGACY_ROLE: dict[str, str] = {
    "account_owner": "owner",
    "account_admin": "admin",
    "account_member": "member",
    "space_admin": "admin",
    "space_member": "member",
    "space_viewer": "viewer",
}

# Inheritance: account role → inherited space role
_ACCOUNT_SPACE_INHERITANCE: dict[str, str] = {
    "account_owner": "space_admin",
    "account_admin": "space_member",
}


# ── get_scope_context (v3.0) ─────────────────────────────────────

def get_scope_context(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ScopeContext:
    """
    Resolve the current request's scope context (v3.0).

    Header precedence:
      1. X-Scope-Type + X-Scope-ID (v3.0)
      2. X-Tenant-ID fallback → scope_type=account (backward compat)

    Returns:
        ScopeContext with resolved roles and permissions.

    Raises:
        HTTPException 400: Missing/invalid scope headers.
        HTTPException 403: No active membership in requested scope.
    """
    if hasattr(request.state, "scope_context"):
        return request.state.scope_context

    scope_type, scope_id = _parse_scope_headers(request)

    # Platform admin bypass
    if current_user.is_platform_admin:
        ctx = ScopeContext(
            user_id=current_user.id,
            scope_type=scope_type,
            scope_id=scope_id,
            active_roles=[],
            resolved_permissions=set(),
            is_super_admin=True,
        )
        request.state.scope_context = ctx
        _set_rls_vars(db, scope_type, scope_id, is_super_admin=True)
        return ctx

    # Resolve memberships → roles → permissions
    active_roles = _resolve_active_roles(db, current_user, scope_type, scope_id)

    if not active_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: no active membership in this {scope_type}",
        )

    config = get_auth_config()
    resolved: set[str] = set()
    for role in active_roles:
        resolved |= config.permissions_for_role(role)

    ctx = ScopeContext(
        user_id=current_user.id,
        scope_type=scope_type,
        scope_id=scope_id,
        active_roles=active_roles,
        resolved_permissions=resolved,
        is_super_admin=False,
    )
    request.state.scope_context = ctx
    _set_rls_vars(db, scope_type, scope_id, is_super_admin=False)
    return ctx


def _parse_scope_headers(request: Request) -> tuple[str, UUID]:
    """Extract and validate scope type/id from request headers."""
    scope_type = request.headers.get("X-Scope-Type")
    scope_id_str = request.headers.get("X-Scope-ID")

    # Fallback: X-Tenant-ID → account scope
    if not scope_type:
        tenant_id_str = request.headers.get("X-Tenant-ID")
        if tenant_id_str:
            scope_type = "account"
            scope_id_str = tenant_id_str

    if not scope_type or not scope_id_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scope headers required: X-Scope-Type + X-Scope-ID, or X-Tenant-ID",
        )

    if scope_type not in ("account", "space"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid X-Scope-Type: '{scope_type}'. Must be 'account' or 'space'.",
        )

    try:
        scope_id = UUID(scope_id_str)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid scope ID format. Must be a valid UUID.",
        ) from exc

    return scope_type, scope_id


def _resolve_active_roles(
    db: Session,
    current_user: User,
    scope_type: str,
    scope_id: UUID,
) -> list[str]:
    """Query memberships and resolve active role names for the requested scope."""
    # New-style scope columns
    memberships = db.query(Membership).filter(
        Membership.user_id == current_user.id,
        Membership.scope_type == scope_type,
        Membership.scope_id == scope_id,
        Membership.status == "active",
    ).all()

    active_roles: list[str] = []
    for m in memberships:
        active_roles.append(m.role_name)

    # Space-scope inheritance from parent account
    if scope_type == "space":
        inherited = _resolve_space_inheritance(db, current_user, scope_id)
        active_roles.extend(inherited)

    return active_roles


def _resolve_space_inheritance(
    db: Session,
    current_user: User,
    space_id: UUID,
) -> list[str]:
    """Check parent account memberships for inherited space roles."""
    space = db.query(Space).filter(Space.id == space_id).first()
    if not space or not space.account_id:
        return []

    # New-style account memberships
    account_memberships = db.query(Membership).filter(
        Membership.user_id == current_user.id,
        Membership.scope_type == "account",
        Membership.scope_id == space.account_id,
        Membership.status == "active",
    ).all()

    config = get_auth_config()
    member_access = config.inheritance_config.get("account_member_space_access", "none")

    inherited: list[str] = []
    for m in account_memberships:
        role = m.role_name
        if not role:
            continue
        if role in _ACCOUNT_SPACE_INHERITANCE:
            inherited.append(_ACCOUNT_SPACE_INHERITANCE[role])
        elif role == "account_member" and member_access != "none":
            inherited.append(member_access)

    return inherited


def _set_rls_vars(
    db: Session,
    scope_type: str,
    scope_id: UUID,
    is_super_admin: bool,
) -> None:
    """Set PostgreSQL RLS session variables for row-level security."""
    bind = db.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        return

    db.execute(text("SET LOCAL app.current_scope_type = :st"), {"st": scope_type})
    db.execute(text("SET LOCAL app.current_scope_id = :sid"), {"sid": str(scope_id)})
    db.execute(text("SET LOCAL app.is_super_admin = :sa"),
               {"sa": "true" if is_super_admin else "false"})
    # Backward compat: existing RLS policies use these variables
    db.execute(text("SET LOCAL app.current_tenant_id = :tid"), {"tid": str(scope_id)})
    db.execute(text("SET LOCAL app.is_platform_admin = :ia"),
               {"ia": "true" if is_super_admin else "false"})


# ──────────────────────────────────────────────────────────────────
# DEPRECATED — thin wrapper around get_scope_context.
# TODO: Remove after 2026-05-20 (60 days from v3.0 release).
# ──────────────────────────────────────────────────────────────────

def get_tenant_context(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TenantContext:
    """DEPRECATED: Use get_scope_context instead. Remove after 2026-05-20."""
    if hasattr(request.state, "tenant_context"):
        return request.state.tenant_context

    scope_ctx = get_scope_context(request, current_user, db)

    role = None
    if scope_ctx.active_roles:
        role = _V3_TO_LEGACY_ROLE.get(scope_ctx.active_roles[0])

    ctx = TenantContext(
        user_id=scope_ctx.user_id,
        tenant_id=scope_ctx.scope_id,
        role=role,
        is_platform_admin=scope_ctx.is_super_admin,
    )
    request.state.tenant_context = ctx
    return ctx

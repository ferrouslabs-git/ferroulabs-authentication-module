"""
Authentication API endpoints

Phases:
- Phase 1: JWT verification and debug endpoint (GET /debug-token)
- Phase 3: User sync endpoint (POST /sync)
- Phase 4: Authentication dependency (GET /me)
- Phase 4: Tenant creation (POST /tenants, GET /tenants/my)
- Phase 6: Tenant Context established before these handlers
- Phase 7: Role-based guards applied to handlers
- Phase 8: Invitation system (POST /invite, GET /invites/{token}, POST /invites/accept)
- Phase 9: User management (GET /users, PATCH /users/{id}/role, DELETE /users/{id})
"""

from fastapi import APIRouter, Header, HTTPException, Request, Response, status, Depends
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session
from uuid import UUID

from ..security import (
    verify_token,
    InvalidTokenError,
    get_current_user,
    get_tenant_context,
    TenantContext,
    require_owner,
    require_admin,
    require_member,
    require_viewer,
    check_permission,
)
from ..schemas import TokenPayload
from ..schemas.tenant import (
    TenantCreateRequest,
    TenantCreateResponse,
    TenantListResponse,
    TenantResponse
)
from ..schemas.invitation import (
    InvitationCreateRequest,
    InvitationCreateResponse,
    InvitationPreviewResponse,
    InvitationAcceptRequest,
    InvitationAcceptResponse,
)
from ..schemas.user_management import (
    TenantUserResponse,
    UpdateUserRoleRequest,
    UpdateUserRoleResponse,
    RemoveUserResponse,
)
from ..schemas.session import (
    SessionRegisterRequest,
    SessionRotateRequest,
)
from app.database import get_db
from ..services.user_service import sync_user_from_cognito
from ..services.tenant_service import create_tenant, get_user_tenants
from ..services.invitation_service import (
    create_invitation,
    get_invitation_by_token,
    accept_invitation,
)
from ..services.email_service import send_invitation_email
from ..services.user_management_service import (
    list_tenant_users,
    update_user_role,
    remove_user_from_tenant,
)
from ..services.audit_service import log_audit_event
from ..services.session_service import (
    create_user_session,
    rotate_user_session,
    revoke_user_session,
    revoke_all_user_sessions,
)
from ..services.cookie_token_service import (
    set_refresh_cookie,
    clear_refresh_cookie,
    call_cognito_refresh,
    COOKIE_NAME,
    store_refresh_token,
    get_refresh_token,
    rotate_refresh_token,
    revoke_refresh_token,
)
from ..services.user_service import suspend_user, unsuspend_user
from ..models.user import User
from ..config import get_settings

# Initialize router - will be populated in subsequent phases
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
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Extract token from "Bearer <token>" format
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication scheme. Use 'Bearer <token>'"
            )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Use 'Bearer <token>'"
        )
    
    # Verify token and return claims
    try:
        payload = verify_token(token)
        claims = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
        return {
            "status": "valid",
            "message": "Token verified successfully",
            "claims": claims
        }
    except InvalidTokenError as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token verification failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"}
        )


@router.post("/sync")
async def sync_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
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
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    # Extract token from "Bearer <token>" format
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication scheme. Use 'Bearer <token>'"
            )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Use 'Bearer <token>'"
        )
    
    # Verify token and get payload
    try:
        token_payload = verify_token(token, allowed_token_uses=("access", "id"))
    except InvalidTokenError as e:
        raise e
    
    # Sync user to database
    try:
        user = sync_user_from_cognito(token_payload, db)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    return {
        "user_id": str(user.id),
        "email": user.email,
        "name": user.name,
        "cognito_sub": user.cognito_sub,
        "is_platform_admin": user.is_platform_admin,
        "created_at": user.created_at.isoformat(),
        "message": "User synced successfully"
    }


@router.get("/me")
async def get_current_user_profile(
    current_user: User = Depends(get_current_user)
):
    """
    Get authenticated user profile.
    Requires valid JWT token.
    
    Phase 3 Test Checkpoint:
    1. Call: curl -H "Authorization: Bearer <token>" http://localhost:8000/auth/me
    2. Expected: User profile returned
    
    Returns:
        User profile: id, email, name, admin status
    """
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "name": current_user.name,
        "cognito_sub": current_user.cognito_sub,
        "is_platform_admin": current_user.is_platform_admin,
        "created_at": current_user.created_at.isoformat(),
        "updated_at": current_user.updated_at.isoformat()
    }


@router.post("/tenants", response_model=TenantCreateResponse)
async def create_new_tenant(
    tenant_data: TenantCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new tenant (organization).
    Requires authentication.
    Creator will be assigned 'owner' role automatically.
    
    Phase 4 Test Checkpoint:
    1. Call: curl -X POST http://localhost:8000/auth/tenants \\
             -H "Authorization: Bearer <token>" \\
             -H "Content-Type: application/json" \\
             -d '{"name": "My Company", "plan": "pro"}'
    2. Expected: Tenant created, user assigned as owner
    
    Args:
        tenant_data: Tenant creation details (name, plan)
        current_user: Authenticated user
        db: Database session
    
    Returns:
        TenantCreateResponse: Tenant ID, name, plan, user's role
    """
    # Create tenant and assign user as owner
    tenant = create_tenant(
        name=tenant_data.name,
        user=current_user,
        db=db,
        plan=tenant_data.plan
    )

    log_audit_event(
        "tenant_created",
        actor_user_id=str(current_user.id),
        tenant_id=str(tenant.id),
        tenant_name=tenant.name,
        plan=tenant.plan,
    )
    
    return TenantCreateResponse(
        tenant_id=tenant.id,
        name=tenant.name,
        plan=tenant.plan,
        role="owner",
        message="Tenant created successfully"
    )


@router.get("/tenants/my", response_model=List[TenantListResponse])
async def get_my_tenants(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all tenants that the current user belongs to.
    Returns user's role in each tenant.
    
    Phase 4 Test Checkpoint:
    1. Call: curl http://localhost:8000/auth/tenants/my \\
             -H "Authorization: Bearer <token>"
    2. Expected: List of tenants with user's role in each
    
    Args:
        current_user: Authenticated user
        db: Database session
    
    Returns:
        List[TenantListResponse]: Tenants with user's role
    """
    tenants = get_user_tenants(current_user.id, db)
    return tenants


@router.get("/tenant-context")
async def get_tenant_context_info(
    ctx: TenantContext = Depends(get_tenant_context)
):
    """
    Test endpoint for Phase 6 - Tenant Context Middleware.
    
    Requires X-Tenant-ID header and validates user membership.
    Returns the populated tenant context information.
    
    Phase 6 Test Checkpoint:
    1. Call with valid tenant:
       curl -H "Authorization: Bearer <token>" \\
            -H "X-Tenant-ID: <valid_tenant_uuid>" \\
            http://localhost:8000/auth/tenant-context
    2. Expected: Tenant context with user's role returned
    
    3. Call with invalid tenant:
       curl -H "Authorization: Bearer <token>" \\
            -H "X-Tenant-ID: <wrong_tenant_uuid>" \\
            http://localhost:8000/auth/tenant-context
    4. Expected: 403 Forbidden
    
    Args:
        ctx: Tenant context (auto-injected by middleware)
    
    Returns:
        Tenant context information including user role
    """
    return {
        "user_id": str(ctx.user_id),
        "tenant_id": str(ctx.tenant_id),
        "role": ctx.role,
        "is_platform_admin": ctx.is_platform_admin,
        "is_owner": ctx.is_owner(),
        "is_admin_or_owner": ctx.is_admin_or_owner(),
        "message": "Tenant context validated successfully"
    }


# Phase 7: Role-Based Authorization Guards Demo Endpoints

@router.get("/admin/settings")
async def get_admin_settings(ctx: TenantContext = Depends(require_admin)):
    """
    Admin-only endpoint - requires owner or admin role.
    
    Phase 7 Test Checkpoint:
    - Owner: Should succeed
    - Admin: Should succeed
    - Member: Should fail with 403
    - Viewer: Should fail with 403
    
    This demonstrates role-based access control using require_admin guard.
    
    Args:
        ctx: Tenant context (must be owner or admin)
    
    Returns:
        Admin settings (demo data)
    """
    return {
        "tenant_id": str(ctx.tenant_id),
        "accessed_by": str(ctx.user_id),
        "role": ctx.role,
        "message": "Admin settings accessed successfully",
        "settings": {
            "max_users": 50,
            "api_enabled": True,
            "webhooks_configured": False
        }
    }


@router.get("/owner/danger-zone")
async def get_owner_settings(ctx: TenantContext = Depends(require_owner)):
    """
    Owner-only endpoint - requires owner role.
    
    Phase 7 Test Checkpoint:
    - Owner: Should succeed
    - Admin: Should fail with 403
    - Member: Should fail with 403
    - Viewer: Should fail with 403
    
    This demonstrates the highest permission level.
    
    Args:
        ctx: Tenant context (must be owner)
    
    Returns:
        Sensitive owner-only operations (demo)
    """
    return {
        "tenant_id": str(ctx.tenant_id),
        "accessed_by": str(ctx.user_id),
        "role": ctx.role,
        "message": "Owner-only danger zone accessed",
        "available_actions": [
            "delete_tenant",
            "transfer_ownership",
            "view_billing",
            "cancel_subscription"
        ]
    }


@router.get("/member/dashboard")
async def get_member_dashboard(ctx: TenantContext = Depends(require_member)):
    """
    Member-level endpoint - requires member, admin, or owner.
    
    Phase 7 Test Checkpoint:
    - Owner: Should succeed
    - Admin: Should succeed
    - Member: Should succeed
    - Viewer: Should fail with 403
    
    This demonstrates inclusive permission (member and above).
    
    Args:
        ctx: Tenant context (must be at least member)
    
    Returns:
        Dashboard data accessible to members
    """
    return {
        "tenant_id": str(ctx.tenant_id),
        "accessed_by": str(ctx.user_id),
        "role": ctx.role,
        "message": "Member dashboard accessed",
        "can_create": True,
        "can_edit": True,
        "can_delete": ctx.role in ("owner", "admin"),
        "recent_activity": []
    }


@router.get("/viewer/reports")
async def get_viewer_reports(ctx: TenantContext = Depends(require_viewer)):
    """
    Viewer-level endpoint - any tenant member can access.
    
    Phase 7 Test Checkpoint:
    - Owner: Should succeed
    - Admin: Should succeed
    - Member: Should succeed
    - Viewer: Should succeed
    
    This demonstrates the lowest permission level (any membership).
    
    Args:
        ctx: Tenant context (any valid member)
    
    Returns:
        Read-only report data
    """
    return {
        "tenant_id": str(ctx.tenant_id),
        "accessed_by": str(ctx.user_id),
        "role": ctx.role,
        "message": "Reports accessed (read-only)",
        "reports": [
            {"id": 1, "name": "Monthly Summary", "type": "summary"},
            {"id": 2, "name": "User Activity", "type": "analytics"}
        ]
    }


@router.get("/permissions/check")
async def check_user_permissions(ctx: TenantContext = Depends(get_tenant_context)):
    """
    Check what permissions the current user has in this tenant.
    
    Phase 7 Test Checkpoint:
    - Tests the permission checking system
    - Returns list of permissions based on role
    
    Args:
        ctx: Tenant context
    
    Returns:
        List of permissions user has in the current tenant
    """
    # Check common permissions
    permissions_to_check = [
        "tenant:delete",
        "tenant:edit",
        "users:create",
        "users:edit",
        "users:delete",
        "settings:edit",
        "data:create",
        "data:edit",
        "data:delete",
        "data:read",
    ]
    
    user_permissions = {
        perm: check_permission(ctx, perm)
        for perm in permissions_to_check
    }
    
    return {
        "tenant_id": str(ctx.tenant_id),
        "user_id": str(ctx.user_id),
        "role": ctx.role,
        "is_platform_admin": ctx.is_platform_admin,
        "permissions": user_permissions,
        "message": "Permission check complete"
    }


@router.post("/invite", response_model=InvitationCreateResponse)
async def invite_user_to_tenant(
    invite_data: InvitationCreateRequest,
    ctx: TenantContext = Depends(require_admin),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create an invitation for a user to join the current tenant.

    Requires admin or owner role in the tenant context.
    """
    invitation = create_invitation(
        db=db,
        tenant_id=ctx.tenant_id,
        email=invite_data.email,
        role=invite_data.role,
        created_by=current_user.id,
    )

    settings = get_settings()
    invite_url = f"{settings.frontend_url}/invite/{invitation.token}"
    email_result = await send_invitation_email(
        to_email=invitation.email,
        invite_url=invite_url,
        tenant_name=invitation.tenant.name,
    )

    log_audit_event(
        "invitation_created",
        actor_user_id=str(current_user.id),
        tenant_id=str(ctx.tenant_id),
        invited_email=invite_data.email,
        invited_role=invite_data.role,
        invitation_id=str(invitation.id),
        email_sent=email_result.sent,
        email_provider=email_result.provider,
    )

    message = "Invitation created successfully"
    if not email_result.sent:
        message = f"Invitation created; email not sent ({email_result.detail})"

    return InvitationCreateResponse(
        invitation_id=invitation.id,
        tenant_id=invitation.tenant_id,
        email=invitation.email,
        role=invitation.role,
        token=invitation.token,
        expires_at=invitation.expires_at,
        message=message,
    )


@router.post("/tenants/{tenant_id}/invite", response_model=InvitationCreateResponse)
async def invite_user_to_explicit_tenant(
    tenant_id: UUID,
    invite_data: InvitationCreateRequest,
    ctx: TenantContext = Depends(require_admin),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create an invitation using explicit tenant path parameter (plan-compatible route)."""
    if tenant_id != ctx.tenant_id and not ctx.is_platform_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant mismatch")

    invitation = create_invitation(
        db=db,
        tenant_id=tenant_id,
        email=invite_data.email,
        role=invite_data.role,
        created_by=current_user.id,
    )

    settings = get_settings()
    invite_url = f"{settings.frontend_url}/invite/{invitation.token}"
    email_result = await send_invitation_email(
        to_email=invitation.email,
        invite_url=invite_url,
        tenant_name=invitation.tenant.name,
    )

    log_audit_event(
        "invitation_created",
        actor_user_id=str(current_user.id),
        tenant_id=str(tenant_id),
        invited_email=invite_data.email,
        invited_role=invite_data.role,
        invitation_id=str(invitation.id),
        email_sent=email_result.sent,
        email_provider=email_result.provider,
    )

    message = "Invitation created successfully"
    if not email_result.sent:
        message = f"Invitation created; email not sent ({email_result.detail})"

    return InvitationCreateResponse(
        invitation_id=invitation.id,
        tenant_id=invitation.tenant_id,
        email=invitation.email,
        role=invitation.role,
        token=invitation.token,
        expires_at=invitation.expires_at,
        message=message,
    )


@router.get("/invites/{token}", response_model=InvitationPreviewResponse)
async def preview_invitation(token: str, db: Session = Depends(get_db)):
    """Get invitation details by token for pre-accept preview."""
    invitation = get_invitation_by_token(db, token)
    if not invitation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")

    return InvitationPreviewResponse(
        token=invitation.token,
        tenant_id=invitation.tenant_id,
        tenant_name=invitation.tenant.name,
        email=invitation.email,
        role=invitation.role,
        expires_at=invitation.expires_at,
        is_expired=invitation.is_expired,
        is_accepted=invitation.is_accepted,
    )


@router.post("/invites/accept", response_model=InvitationAcceptResponse)
async def accept_invitation_token(
    payload: InvitationAcceptRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Accept an invitation token for the authenticated user."""
    invitation = get_invitation_by_token(db, payload.token)
    if not invitation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")

    try:
        membership = accept_invitation(db, invitation, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    log_audit_event(
        "invitation_accepted",
        actor_user_id=str(current_user.id),
        tenant_id=str(membership.tenant_id),
        invitation_id=str(invitation.id),
        role=membership.role,
    )

    return InvitationAcceptResponse(
        tenant_id=membership.tenant_id,
        role=membership.role,
        message="Invitation accepted successfully",
    )


@router.get("/tenants/{tenant_id}/users", response_model=List[TenantUserResponse])
async def get_tenant_users(
    tenant_id: UUID,
    ctx: TenantContext = Depends(require_member),
    db: Session = Depends(get_db),
):
    """List active users in tenant (member+)."""
    if tenant_id != ctx.tenant_id and not ctx.is_platform_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant mismatch")

    return list_tenant_users(db, tenant_id)


@router.patch("/tenants/{tenant_id}/users/{user_id}/role", response_model=UpdateUserRoleResponse)
async def patch_tenant_user_role(
    tenant_id: UUID,
    user_id: UUID,
    payload: UpdateUserRoleRequest,
    ctx: TenantContext = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update user's tenant role (admin+)."""
    if tenant_id != ctx.tenant_id and not ctx.is_platform_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant mismatch")

    try:
        membership = update_user_role(db, tenant_id, user_id, payload.role)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found in tenant")

    log_audit_event(
        "tenant_user_role_updated",
        actor_user_id=str(ctx.user_id),
        tenant_id=str(tenant_id),
        target_user_id=str(user_id),
        new_role=payload.role,
    )

    return UpdateUserRoleResponse(
        user_id=membership.user_id,
        tenant_id=membership.tenant_id,
        role=membership.role,
        message="User role updated successfully",
    )


@router.delete("/tenants/{tenant_id}/users/{user_id}", response_model=RemoveUserResponse)
async def delete_tenant_user(
    tenant_id: UUID,
    user_id: UUID,
    ctx: TenantContext = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Soft-remove user from tenant (admin+)."""
    if tenant_id != ctx.tenant_id and not ctx.is_platform_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant mismatch")

    try:
        membership = remove_user_from_tenant(db, tenant_id, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found in tenant")

    log_audit_event(
        "tenant_user_removed",
        actor_user_id=str(ctx.user_id),
        tenant_id=str(tenant_id),
        target_user_id=str(user_id),
        resulting_status=membership.status,
    )

    return RemoveUserResponse(
        user_id=membership.user_id,
        tenant_id=membership.tenant_id,
        status=membership.status,
        message="User removed from tenant",
    )


@router.delete("/sessions/all")
async def revoke_all_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_current_session_id: Optional[str] = Header(None),
):
    """Revoke all active sessions for current user.

    Optional header `X-Current-Session-ID` can keep one active session.
    """
    keep_session_id: UUID | None = None
    if x_current_session_id:
        try:
            keep_session_id = UUID(x_current_session_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid X-Current-Session-ID format",
            ) from exc

    revoked_count = revoke_all_user_sessions(
        db=db,
        user_id=current_user.id,
        except_session_id=keep_session_id,
    )

    log_audit_event(
        "all_sessions_revoked",
        actor_user_id=str(current_user.id),
        revoked_count=revoked_count,
        kept_session_id=str(keep_session_id) if keep_session_id else None,
    )

    return {
        "user_id": str(current_user.id),
        "revoked_count": revoked_count,
        "kept_session_id": str(keep_session_id) if keep_session_id else None,
        "message": "Session revocation completed",
    }


@router.post("/sessions/register")
async def register_session(
    payload: SessionRegisterRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a refresh-token-backed session for current user."""
    created = create_user_session(
        db=db,
        user_id=current_user.id,
        refresh_token=payload.refresh_token,
        user_agent=payload.user_agent,
        ip_address=payload.ip_address,
        device_info=payload.device_info,
        expires_at=payload.expires_at,
    )

    log_audit_event(
        "session_registered",
        actor_user_id=str(current_user.id),
        session_id=str(created.id),
    )

    return {
        "session_id": str(created.id),
        "user_id": str(current_user.id),
        "revoked_at": None,
        "message": "Session registered successfully",
    }


@router.post("/sessions/{session_id}/rotate")
async def rotate_session(
    session_id: UUID,
    payload: SessionRotateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Rotate refresh token by revoking current session and issuing replacement."""
    rotated = rotate_user_session(
        db=db,
        user_id=current_user.id,
        session_id=session_id,
        old_refresh_token=payload.old_refresh_token,
        new_refresh_token=payload.new_refresh_token,
        user_agent=payload.user_agent,
        ip_address=payload.ip_address,
        device_info=payload.device_info,
        expires_at=payload.expires_at,
    )

    if not rotated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    log_audit_event(
        "session_rotated",
        actor_user_id=str(current_user.id),
        previous_session_id=str(session_id),
        new_session_id=str(rotated.id),
    )

    return {
        "session_id": str(rotated.id),
        "user_id": str(current_user.id),
        "revoked_at": None,
        "message": "Session rotated successfully",
    }


@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke one active session that belongs to the current user."""
    revoked = revoke_user_session(db, current_user.id, session_id)
    if not revoked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    log_audit_event(
        "session_revoked",
        actor_user_id=str(current_user.id),
        session_id=str(session_id),
    )

    return {
        "session_id": str(revoked.id),
        "user_id": str(current_user.id),
        "revoked_at": revoked.revoked_at.isoformat() if revoked.revoked_at else None,
        "message": "Session revoked successfully",
    }


@router.patch("/users/{user_id}/suspend")
async def suspend_user_account(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Suspend a user account (platform admin only).
    
    Suspended users cannot authenticate and all active sessions become invalid.
    
    Args:
        user_id: User ID to suspend
        current_user: Authenticated admin user
        db: Database session
    
    Returns:
        Suspension confirmation
    
    Raises:
        403: If current user is not platform admin
        404: If target user not found
    """
    # Only platform admins can suspend users
    if not current_user.is_platform_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only platform administrators can suspend user accounts"
        )
    
    # Cannot suspend yourself
    if current_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot suspend your own account"
        )
    
    try:
        suspended_user = suspend_user(user_id, db)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    
    # Log audit event
    log_audit_event(
        "user_suspended",
        actor_user_id=str(current_user.id),
        target_user_id=str(user_id),
        target_email=suspended_user.email,
    )
    
    return {
        "user_id": str(suspended_user.id),
        "email": suspended_user.email,
        "is_active": suspended_user.is_active,
        "suspended_at": suspended_user.suspended_at.isoformat() if suspended_user.suspended_at else None,
        "message": "User account suspended successfully"
    }


@router.patch("/users/{user_id}/unsuspend")
async def unsuspend_user_account(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Unsuspend a user account (platform admin only).
    
    Restores user's ability to authenticate.
    
    Args:
        user_id: User ID to unsuspend
        current_user: Authenticated admin user
        db: Database session
    
    Returns:
        Unsuspension confirmation
    
    Raises:
        403: If current user is not platform admin
        404: If target user not found
    """
    # Only platform admins can unsuspend users
    if not current_user.is_platform_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only platform administrators can unsuspend user accounts"
        )
    
    try:
        unsuspended_user = unsuspend_user(user_id, db)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    
    # Log audit event
    log_audit_event(
        "user_unsuspended",
        actor_user_id=str(current_user.id),
        target_user_id=str(user_id),
        target_email=unsuspended_user.email,
    )
    
    return {
        "user_id": str(unsuspended_user.id),
        "email": unsuspended_user.email,
        "is_active": unsuspended_user.is_active,
        "suspended_at": None,
        "message": "User account unsuspended successfully"
    }


# Placeholder routes will be added as each phase is completed
# This ensures the router is properly registered from the start


class _StoreRefreshPayload(BaseModel):
    refresh_token: str


@router.post("/cookie/store-refresh")
async def store_refresh_cookie(
    payload: _StoreRefreshPayload,
    response: Response,
    current_user: User = Depends(get_current_user),
):
    """Store Cognito refresh token in an HttpOnly cookie after login.

    Called once by the frontend immediately after exchanging the PKCE auth code.
    Moves the refresh token from JS-accessible memory into an HttpOnly, SameSite=Strict
    cookie scoped to the /auth/token path.
    """
    settings = get_settings()
    cookie_key = store_refresh_token(payload.refresh_token)
    set_refresh_cookie(response, cookie_key, secure=settings.cookie_secure)
    log_audit_event("refresh_cookie_stored", actor_user_id=str(current_user.id))
    return {"message": "Refresh token stored"}


@router.post("/token/refresh")
async def token_refresh(
    request: Request,
    response: Response,
    x_requested_with: Optional[str] = Header(None),
):
    """Exchange the HttpOnly refresh cookie for a new access token.

    - Reads the refresh token from the HttpOnly cookie (never from request body).
    - Requires X-Requested-With: XMLHttpRequest header as CSRF defence-in-depth
      (cookie is SameSite=Strict so cross-site requests are already blocked).
    - Proxies grant to Cognito and returns {access_token, id_token, expires_in}.
    - If Cognito returns a rotated refresh_token, the cookie is updated in-place.
    """
    if not x_requested_with or x_requested_with.lower() != "xmlhttprequest":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="X-Requested-With: XMLHttpRequest header required",
        )

    cookie_key = request.cookies.get(COOKIE_NAME)
    if not cookie_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token cookie present",
        )

    refresh_token = get_refresh_token(cookie_key)
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token cookie present",
        )

    settings = get_settings()
    if not settings.cognito_domain or not settings.cognito_client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cognito is not configured on this server",
        )

    try:
        tokens = call_cognito_refresh(
            refresh_token=refresh_token,
            cognito_domain=settings.cognito_domain,
            client_id=settings.cognito_client_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    # Rotate cookie if Cognito issues a new refresh token
    if tokens.get("refresh_token"):
        new_cookie_key = rotate_refresh_token(cookie_key, tokens["refresh_token"])
        set_refresh_cookie(response, new_cookie_key, secure=settings.cookie_secure)

    return {
        "access_token": tokens.get("access_token"),
        "id_token": tokens.get("id_token"),
        "expires_in": tokens.get("expires_in", 3600),
    }


@router.post("/cookie/clear-refresh")
async def clear_refresh(
    request: Request,
    response: Response,
):
    """Expire the HttpOnly refresh-token cookie.

    Called on logout. No authentication required — the access token may already
    be gone when this is called.
    """
    settings = get_settings()
    revoke_refresh_token(request.cookies.get(COOKIE_NAME, ""))
    clear_refresh_cookie(response, secure=settings.cookie_secure)
    return {"message": "Refresh cookie cleared"}

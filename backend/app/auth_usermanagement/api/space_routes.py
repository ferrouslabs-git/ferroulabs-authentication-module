"""Space API routes — create, list, invite, suspend/unsuspend."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db

from ..models.user import User
from ..schemas.invitation import InvitationCreateRequest, InvitationCreateResponse
from ..schemas.space import SpaceCreateRequest, SpaceResponse, SpaceSuspendResponse, SpaceUpdateRequest
from ..security import ScopeContext, get_current_user, require_permission
from ..services.space_service import (
    create_space,
    get_space_by_id,
    list_account_spaces,
    list_user_spaces,
    suspend_space,
    unsuspend_space,
    update_space,
)
from .route_helpers import create_invitation_response

router = APIRouter()


@router.post("/spaces", response_model=SpaceResponse, status_code=status.HTTP_201_CREATED)
async def create_new_space(
    body: SpaceCreateRequest,
    ctx: ScopeContext = Depends(require_permission("spaces:create")),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new space. account_id defaults to the current scope."""
    account_id = body.account_id or ctx.scope_id
    space = create_space(db, body.name, account_id, current_user.id)
    return space


@router.get("/spaces/my", response_model=list[SpaceResponse])
async def list_my_spaces(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all spaces where the current user has an active membership."""
    return list_user_spaces(db, current_user.id)


@router.get("/accounts/{account_id}/spaces", response_model=list[SpaceResponse])
async def list_spaces_in_account(
    account_id: UUID,
    ctx: ScopeContext = Depends(require_permission("account:read")),
    db: Session = Depends(get_db),
):
    """List spaces belonging to an account."""
    if account_id != ctx.scope_id and not ctx.is_super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Scope mismatch")
    return list_account_spaces(db, account_id)


@router.post("/spaces/{space_id}/invite", response_model=InvitationCreateResponse)
async def invite_to_space(
    space_id: UUID,
    invite_data: InvitationCreateRequest,
    ctx: ScopeContext = Depends(require_permission("members:invite")),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Invite a user to a space with a space-layer role."""
    # Override scope fields to target this specific space
    invite_data.target_scope_type = "space"
    invite_data.target_scope_id = space_id
    # Default role_name to space_member if not specified
    if not invite_data.target_role_name:
        invite_data.target_role_name = "space_member"

    # tenant_id comes from context (the parent account)
    tenant_id = ctx.scope_id
    return await create_invitation_response(db, tenant_id, invite_data, current_user, ctx)


@router.get("/spaces/{space_id}", response_model=SpaceResponse)
async def get_space_detail(
    space_id: UUID,
    ctx: ScopeContext = Depends(require_permission("account:read")),
    db: Session = Depends(get_db),
):
    """Get details for a single space."""
    space = get_space_by_id(db, space_id)
    if not space:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Space not found")
    return space


@router.patch("/spaces/{space_id}", response_model=SpaceResponse)
async def update_space_detail(
    space_id: UUID,
    payload: SpaceUpdateRequest,
    ctx: ScopeContext = Depends(require_permission("spaces:create")),
    db: Session = Depends(get_db),
):
    """Update space name. Requires spaces:create permission."""
    if payload.name is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one field (name) must be provided")
    try:
        space = update_space(db, space_id, name=payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return space


@router.post("/spaces/{space_id}/suspend", response_model=SpaceSuspendResponse)
async def suspend_space_endpoint(
    space_id: UUID,
    ctx: ScopeContext = Depends(require_permission("space:delete")),
    db: Session = Depends(get_db),
):
    """Suspend a space (admin+)."""
    try:
        space = suspend_space(db, space_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return SpaceSuspendResponse(
        id=space.id, status=space.status, suspended_at=space.suspended_at, message="Space suspended"
    )


@router.post("/spaces/{space_id}/unsuspend", response_model=SpaceSuspendResponse)
async def unsuspend_space_endpoint(
    space_id: UUID,
    ctx: ScopeContext = Depends(require_permission("space:delete")),
    db: Session = Depends(get_db),
):
    """Unsuspend a space (admin+)."""
    try:
        space = unsuspend_space(db, space_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return SpaceSuspendResponse(
        id=space.id, status=space.status, suspended_at=space.suspended_at, message="Space unsuspended"
    )

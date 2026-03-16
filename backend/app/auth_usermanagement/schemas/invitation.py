"""
Invitation schemas for API request/response validation
"""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class InvitationCreateRequest(BaseModel):
    """Request schema for creating a tenant invitation."""
    email: EmailStr = Field(..., description="Email address to invite")
    role: Literal["admin", "member", "viewer"] = Field(
        default="member",
        description="Role to assign when invitation is accepted"
    )


class InvitationCreateResponse(BaseModel):
    """Response schema for created invitation."""
    invitation_id: UUID
    tenant_id: UUID
    email: EmailStr
    role: str
    token: str
    expires_at: datetime
    message: str
    status: Literal["pending", "accepted", "expired", "revoked"]
    email_sent: bool
    email_detail: str | None = None


class InvitationPreviewResponse(BaseModel):
    """Response schema for invitation lookup by token."""
    token: str
    tenant_id: UUID
    tenant_name: str
    email: EmailStr
    role: str
    expires_at: datetime
    status: Literal["pending", "accepted", "expired", "revoked"]
    is_expired: bool
    is_accepted: bool


class InvitationRevokeResponse(BaseModel):
    invitation_id: UUID
    tenant_id: UUID
    status: Literal["revoked"]
    message: str


class InvitationAcceptRequest(BaseModel):
    """Request schema for accepting an invitation."""
    token: str = Field(..., min_length=20, description="Invitation token")


class InvitationAcceptResponse(BaseModel):
    """Response schema for accepted invitation."""
    tenant_id: UUID
    role: str
    message: str

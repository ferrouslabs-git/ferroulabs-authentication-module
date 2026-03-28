"""
Tenant schemas for API request/response validation
"""
from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import datetime


class TenantCreateRequest(BaseModel):
    """Schema for creating a new tenant"""
    name: str = Field(..., min_length=1, max_length=255, description="Tenant/organization name")
    plan: Optional[str] = Field("free", description="Pricing plan: free, pro, enterprise")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Acme Corporation",
                "plan": "pro"
            }
        }


class TenantResponse(BaseModel):
    """Schema for tenant response"""
    id: UUID
    name: str
    plan: str
    status: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "Acme Corporation",
                "plan": "pro",
                "status": "active",
                "created_at": "2026-03-08T02:00:18.602279",
                "updated_at": "2026-03-08T02:00:18.602279"
            }
        }


class TenantCreateResponse(BaseModel):
    """Schema for tenant creation response with additional context"""
    tenant_id: UUID
    name: str
    plan: str
    role: str = "owner"
    message: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "Acme Corporation",
                "plan": "pro",
                "role": "owner",
                "message": "Tenant created successfully"
            }
        }


class TenantListResponse(BaseModel):
    """Schema for listing user's tenants with membership info"""
    id: UUID
    name: str
    plan: str
    status: str
    role: str
    created_at: datetime
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "Acme Corporation",
                "plan": "pro",
                "status": "active",
                "role": "owner",
                "created_at": "2026-03-08T02:00:18.602279"
            }
        }


class TenantStatusResponse(BaseModel):
    tenant_id: UUID
    status: str
    message: str


class TenantUpdateRequest(BaseModel):
    """Schema for updating tenant fields. At least one field must be provided."""
    name: str | None = Field(None, min_length=1, max_length=255, description="New tenant name")
    plan: str | None = Field(None, description="New pricing plan")


class TenantDetailResponse(BaseModel):
    """Schema for single tenant detail with membership stats."""
    id: UUID
    name: str
    plan: str
    status: str
    created_at: datetime
    updated_at: datetime
    member_count: int
    owner_count: int

    class Config:
        from_attributes = True


class TenantInvitationListResponse(BaseModel):
    """Schema for listing invitations within a tenant."""
    invitation_id: UUID
    tenant_id: UUID
    email: str
    role: str
    status: str
    target_scope_type: str | None = None
    target_scope_id: UUID | None = None
    created_at: datetime
    expires_at: datetime
    accepted_at: datetime | None = None
    revoked_at: datetime | None = None


class PlatformTenantResponse(BaseModel):
    tenant_id: UUID
    name: str
    plan: str
    status: str
    created_at: datetime
    member_count: int
    owner_count: int

"""
Schemas for tenant user-management endpoints.
"""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr


class TenantUserResponse(BaseModel):
    user_id: UUID
    email: EmailStr
    name: str | None
    role: str
    status: str
    is_active: bool
    joined_at: datetime


class UpdateUserRoleRequest(BaseModel):
    role: Literal["owner", "admin", "member", "viewer"]


class UpdateUserRoleResponse(BaseModel):
    user_id: UUID
    tenant_id: UUID
    role: str
    message: str


class RemoveUserResponse(BaseModel):
    user_id: UUID
    tenant_id: UUID
    status: str
    message: str

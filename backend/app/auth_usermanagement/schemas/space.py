"""Space schemas for API request/response validation."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SpaceCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Space name")
    account_id: UUID | None = Field(
        default=None,
        description="Account (tenant) this space belongs to. Defaults to current scope.",
    )


class SpaceResponse(BaseModel):
    id: UUID
    name: str
    account_id: UUID | None = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class SpaceSuspendResponse(BaseModel):
    id: UUID
    status: str
    suspended_at: datetime | None = None
    message: str

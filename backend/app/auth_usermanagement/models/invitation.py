"""
Invitation model - token-based user invitations to tenants
"""
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import UTC, datetime
from uuid import uuid4

from ..database import Base


def utc_now() -> datetime:
    """Return naive UTC datetime compatible with existing DB DateTime columns."""
    return datetime.now(UTC).replace(tzinfo=None)


class Invitation(Base):
    """
    Invitation model - secure token-based invites
    Allows tenant members to invite new users
    """
    __tablename__ = "invitations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String(255), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # admin, member, viewer
    token = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    accepted_at = Column(DateTime)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    
    created_at = Column(DateTime, default=utc_now, nullable=False)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="invitations")
    creator = relationship("User", back_populates="created_invitations", foreign_keys=[created_by])
    
    def __repr__(self):
        return f"<Invitation(email='{self.email}', tenant_id={self.tenant_id}, role='{self.role}')>"
    
    @property
    def is_expired(self):
        """Check if invitation has expired"""
        return utc_now() > self.expires_at
    
    @property
    def is_accepted(self):
        """Check if invitation has been accepted"""
        return self.accepted_at is not None

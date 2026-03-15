"""
Membership model - bridge between Users and Tenants
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
from uuid import uuid4

from app.database import Base


class Membership(Base):
    """
    Membership model - links Users to Tenants with roles
    Enables users to belong to multiple organizations
    """
    __tablename__ = "memberships"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # owner, admin, member, viewer
    status = Column(String(20), default="active")  # active, suspended
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="memberships")
    tenant = relationship("Tenant", back_populates="memberships")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('user_id', 'tenant_id', name='unique_user_tenant'),
    )
    
    def __repr__(self):
        return f"<Membership(user_id={self.user_id}, tenant_id={self.tenant_id}, role='{self.role}')>"

"""
Tenant model for multi-tenancy
Each tenant represents a client/organization
"""
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
from uuid import uuid4

from ..database import Base


class Tenant(Base):
    """
    Tenant/Client/Organization model
    The primary isolation boundary for multi-tenant SaaS
    """
    __tablename__ = "tenants"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)
    plan = Column(String(50), default="free")  # free, pro, enterprise
    status = Column(String(20), default="active")  # active, suspended
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    memberships = relationship(
        "Membership",
        primaryjoin="and_(Membership.scope_id == Tenant.id, Membership.scope_type == 'account')",
        foreign_keys="[Membership.scope_id]",
        viewonly=True,
    )
    invitations = relationship("Invitation", back_populates="tenant", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Tenant(id={self.id}, name='{self.name}', plan='{self.plan}')>"

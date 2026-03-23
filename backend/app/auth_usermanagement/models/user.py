"""
User model - represents individuals authenticated via Cognito
"""
from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
from uuid import uuid4

from app.database import Base


class User(Base):
    """
    User model - linked to AWS Cognito identity
    Users can belong to multiple tenants via Membership
    """
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    cognito_sub = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255))
    is_platform_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True, nullable=False)
    suspended_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    memberships = relationship("Membership", back_populates="user", cascade="all, delete-orphan",
                               foreign_keys="Membership.user_id")
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    created_invitations = relationship("Invitation", back_populates="creator", foreign_keys="Invitation.created_by")
    
    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', cognito_sub='{self.cognito_sub}')>"

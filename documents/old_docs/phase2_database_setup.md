# Phase 2: Database Layer Setup - Step-by-Step Guide

> Complete walkthrough of setting up SQLAlchemy models and Alembic migrations for multi-tenant authentication

---

## Overview

Phase 2 creates the PostgreSQL database schema for multi-tenant SaaS authentication, including Users, Tenants, Memberships, Invitations, and Sessions.

**Prerequisites:**
- Phase 1 complete (Cognito + JWT verification working)
- PostgreSQL running (via `setup-postgres.ps1`)
- `DATABASE_URL` in `.env` file

**Outcome:**
- 5 SQLAlchemy models created
- Database tables deployed via Alembic migrations
- Type-safe ORM ready for Phase 3

---

## Step 1: Add Database Dependencies to requirements.txt

**What:** Add SQLAlchemy, Alembic, and PostgreSQL driver

**Why:** These packages enable ORM functionality and database migrations

**File:** `backend/requirements.txt`

```txt
fastapi>=0.110
uvicorn[standard]>=0.27
pydantic>=2.7,<3
pydantic-settings>=2.2
python-multipart>=0.0.9
python-jose[cryptography]==3.3.0
requests>=2.32
python-dotenv>=1.0.1

# Database
sqlalchemy>=2.0.25
alembic>=1.13.0
psycopg2-binary>=2.9.9
```

**Install:**
```bash
cd backend
pip install -r requirements.txt
```

---

## Step 2: Create Database Session Management

**What:** Configure SQLAlchemy engine and create `get_db()` FastAPI dependency

**Why:** Centralized database connection management with proper session lifecycle

**File:** `backend/app/auth_usermanagement/database.py`

```python
"""
Database configuration and session management
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from app.config import get_settings

# Get database URL from settings
settings = get_settings()
DATABASE_URL = settings.database_url

# Create SQLAlchemy engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Verify connections before using
    echo=False  # Set to True for SQL query logging during development
)

# Create SessionLocal class
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Create Base class for models
Base = declarative_base()


def get_db() -> Session:
    """
    FastAPI dependency for database sessions
    
    Usage:
        @app.get("/users")
        def get_users(db: Session = Depends(get_db)):
            return db.query(User).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

**Key Points:**
- `pool_pre_ping=True` prevents stale connection errors
- `get_db()` uses dependency injection pattern (FastAPI best practice)
- `Base` is the parent class all models inherit from

---

## Step 3: Create Tenant Model

**What:** Define Tenant/Organization model for multi-tenancy

**Why:** Primary isolation boundary - all data belongs to a tenant

**File:** `backend/app/auth_usermanagement/models/tenant.py`

```python
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
    memberships = relationship("Membership", back_populates="tenant", cascade="all, delete-orphan")
    invitations = relationship("Invitation", back_populates="tenant", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Tenant(id={self.id}, name='{self.name}', plan='{self.plan}')>"
```

---

## Step 4: Create User Model

**What:** Define User model linked to Cognito identity

**Why:** Store user profile data and link Cognito `sub` to internal user ID

**File:** `backend/app/auth_usermanagement/models/user.py`

```python
"""
User model - represents individuals authenticated via Cognito
"""
from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
from uuid import uuid4

from ..database import Base


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
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    memberships = relationship("Membership", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    created_invitations = relationship("Invitation", back_populates="creator", foreign_keys="Invitation.created_by")
    
    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', cognito_sub='{self.cognito_sub}')>"
```

**Key Points:**
- `cognito_sub` is the unique Cognito user identifier (never changes, even if email changes)
- Indexed on both `cognito_sub` and `email` for fast lookups
- `is_platform_admin` for super-admin users who can access all tenants

---

## Step 5: Create Membership Model

**What:** Define Membership model linking Users to Tenants with roles

**Why:** Enables users to belong to multiple organizations with different permissions

**File:** `backend/app/auth_usermanagement/models/membership.py`

```python
"""
Membership model - bridge between Users and Tenants
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
from uuid import uuid4

from ..database import Base


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
```

**Key Points:**
- `UniqueConstraint` prevents duplicate user-tenant pairs
- `CASCADE` delete ensures orphaned memberships are cleaned up
- `status` allows suspending access without deleting the membership

---

## Step 6: Create Invitation Model

**What:** Define Invitation model for token-based user invites

**Why:** Secure onboarding flow - users can't join tenants without a valid invite

**File:** `backend/app/auth_usermanagement/models/invitation.py`

```python
"""
Invitation model - token-based user invitations to tenants
"""
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
from uuid import uuid4

from ..database import Base


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
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="invitations")
    creator = relationship("User", back_populates="created_invitations", foreign_keys=[created_by])
    
    def __repr__(self):
        return f"<Invitation(email='{self.email}', tenant_id={self.tenant_id}, role='{self.role}')>"
    
    @property
    def is_expired(self):
        """Check if invitation has expired"""
        return datetime.utcnow() > self.expires_at
    
    @property
    def is_accepted(self):
        """Check if invitation has been accepted"""
        return self.accepted_at is not None
```

**Key Points:**
- `token` is unique and indexed for fast validation
- `expires_at` ensures invites don't live forever
- `accepted_at` tracks when invite was used
- Helper properties make business logic cleaner

---

## Step 7: Create Session Model

**What:** Define Session model for refresh token tracking

**Why:** Enables logout, device management, and token revocation

**File:** `backend/app/auth_usermanagement/models/session.py`

```python
"""
Session model - tracks user refresh tokens for logout and revocation
"""
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
from uuid import uuid4

from ..database import Base


class Session(Base):
    """
    Session model - tracks refresh tokens
    Enables logout, device tracking, and token revocation
    """
    __tablename__ = "sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    refresh_token_hash = Column(String(255), nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    revoked_at = Column(DateTime)
    
    # Relationships
    user = relationship("User", back_populates="sessions")
    
    def __repr__(self):
        return f"<Session(id={self.id}, user_id={self.user_id}, revoked={self.is_revoked})>"
    
    @property
    def is_revoked(self):
        """Check if session has been revoked"""
        return self.revoked_at is not None
    
    def revoke(self):
        """Revoke this session"""
        self.revoked_at = datetime.utcnow()
```

**Key Points:**
- Stores hashed refresh tokens (never store tokens in plain text)
- `revoked_at` implements soft delete (audit trail)
- Helper method `revoke()` for clean API

---

## Step 8: Update Models __init__.py

**What:** Export all models from the models package

**Why:** Allows importing with `from app.auth_usermanagement.models import User, Tenant`

**File:** `backend/app/auth_usermanagement/models/__init__.py`

```python
"""
SQLAlchemy ORM models for auth module

Phases:
- Phase 2: User, Tenant, Membership, Invitation, Session models
"""
from .tenant import Tenant
from .user import User
from .membership import Membership
from .invitation import Invitation
from .session import Session

__all__ = [
    "Tenant",
    "User",
    "Membership",
    "Invitation",
    "Session",
]
```

---

## Step 9: Initialize Alembic

**What:** Setup Alembic migration tool

**Why:** Version control for database schema (like Git for your database)

**Command:**
```bash
cd backend
alembic init alembic
```

**Output:**
- Creates `alembic/` folder
- Creates `alembic.ini` config file
- Creates `alembic/env.py` migration environment
- Creates `alembic/versions/` for migration scripts

---

## Step 10: Configure Alembic Database URL

**What:** Comment out hardcoded URL in `alembic.ini`

**Why:** We'll load the URL programmatically from `.env` via `app.config`

**File:** `backend/alembic.ini`

```ini
# Line 89 - Comment this out:
# sqlalchemy.url = driver://user:pass@localhost/dbname
# NOTE: Database URL is configured programmatically in env.py from app.config
```

---

## Step 11: Configure Alembic to Import Models

**What:** Update `alembic/env.py` to auto-discover our models

**Why:** Enables `alembic revision --autogenerate` to detect schema changes

**File:** `backend/alembic/env.py`

**Replace the imports and config section:**
```python
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Import our application config and models
import sys
from pathlib import Path

# Add parent directory to path so we can import app
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.auth_usermanagement.database import Base
# Import all models so Alembic can detect them
from app.auth_usermanagement.models import (
    Tenant,
    User,
    Membership,
    Invitation,
    Session,
)

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Set database URL from our application settings
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata
```

**Key Changes:**
1. Import our `get_settings()` to load `DATABASE_URL` from `.env`
2. Import `Base` metadata from `database.py`
3. Import all 5 models (Alembic scans these to detect schema)
4. Set `target_metadata = Base.metadata` instead of `None`

---

## Step 12: Generate Initial Migration

**What:** Auto-generate migration script from models

**Why:** Alembic compares models to database state and creates SQL

**Command:**
```bash
alembic revision --autogenerate -m "Create auth tables"
```

**Output:**
```
INFO  [alembic.autogenerate.compare.tables] Detected added table 'tenants'
INFO  [alembic.autogenerate.compare.tables] Detected added table 'users'
INFO  [alembic.autogenerate.compare.constraints] Detected added index 'ix_users_cognito_sub' on '('cognito_sub',)'
INFO  [alembic.autogenerate.compare.constraints] Detected added index 'ix_users_email' on '('email',)'
INFO  [alembic.autogenerate.compare.tables] Detected added table 'invitations'
INFO  [alembic.autogenerate.compare.tables] Detected added table 'memberships'
INFO  [alembic.autogenerate.compare.tables] Detected added table 'sessions'
Generating backend/alembic/versions/d3494139f54d_create_auth_tables.py ... done
```

**What Happened:**
- Alembic detected 5 new tables
- Detected all indexes (cognito_sub, email, tenant_id, etc.)
- Detected unique constraint on memberships (user_id, tenant_id)
- Generated migration file with upgrade/downgrade functions

---

## Step 13: Run Migration

**What:** Apply migration to create tables in PostgreSQL

**Why:** Executes the generated SQL to build the schema

**Command:**
```bash
alembic upgrade head
```

**Output:**
```
INFO  [alembic.runtime.migration] Running upgrade  -> d3494139f54d, Create auth tables
```

**What Happened:**
- Alembic connected to PostgreSQL (`DATABASE_URL` from `.env`)
- Created `alembic_version` tracking table
- Created all 5 tables with proper columns, types, constraints, indexes

---

## Step 14: Verify Tables Created

**What:** Check PostgreSQL to confirm tables exist

**Why:** Visual confirmation that migration succeeded

**Command:**
```bash
docker exec -it trustos-postgres psql -U postgres -d trustos_dev -c "\dt"
```

**Output:**
```
 Schema |      Name       | Type  |  Owner
--------+-----------------+-------+----------
 public | alembic_version | table | postgres
 public | invitations     | table | postgres
 public | memberships     | table | postgres
 public | sessions        | table | postgres
 public | tenants         | table | postgres
 public | users           | table | postgres
(6 rows)
```

---

## Step 15: Inspect Table Schema (Optional)

**What:** View detailed schema of a specific table

**Why:** Verify columns, types, constraints match the model

**Command:**
```bash
docker exec -it trustos-postgres psql -U postgres -d trustos_dev -c "\d users"
```

**Output Shows:**
- UUID primary key
- `cognito_sub` (varchar, unique, indexed)
- `email` (varchar, unique, indexed)
- `name`, `is_platform_admin`, timestamps
- Foreign key constraints
- Indexes on cognito_sub and email

---

## Summary: What We Built

**Files Created:**
1. `database.py` - SQLAlchemy engine and session management
2. `models/tenant.py` - Tenant/Organization model
3. `models/user.py` - User model (Cognito-linked)
4. `models/membership.py` - User-Tenant bridge with roles
5. `models/invitation.py` - Invite tokens
6. `models/session.py` - Refresh token tracking

**Alembic Setup:**
- Initialized Alembic
- Configured `env.py` to import models
- Generated initial migration
- Applied migration to PostgreSQL

**Database State:**
- 5 tables created with proper relationships
- Indexes on frequently queried columns
- Unique constraints where appropriate
- CASCADE deletes for data integrity
- UUID primary keys throughout

---

## Key Patterns Used

**Multi-Tenancy:**
- Every piece of data belongs to a Tenant
- Users access Tenants via Membership
- Tenant ID will be required for all future queries

**Cognito Integration:**
- `cognito_sub` is the source of truth for user identity
- Email stored for convenience, but can change in Cognito
- No password storage (Cognito handles authentication)

**Soft Deletes:**
- Sessions use `revoked_at` instead of hard delete
- Maintains audit trail

**Type Safety:**
- UUID for all IDs (not integers)
- Enums as strings for flexibility (not hardcoded enums)
- Nullable vs non-nullable explicitly defined

---

## Next Steps

**Phase 3: User Sync Service**
- Create service to sync Cognito users to database
- Add endpoint: `POST /auth/sync-user` (called after Cognito signup)
- Automatically create User record on first login

**Phase 4: Tenant Creation**
- Add endpoint: `POST /tenants`
- Create first tenant for new users
- Assign "owner" membership

**Phase 5: Middleware**
- Extract JWT from headers
- Load User and Memberships
- Validate tenant access
- Inject into request context

---

## Useful Commands Reference

**Alembic:**
```bash
# Generate new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View current version
alembic current

# View migration history
alembic history
```

**PostgreSQL:**
```bash
# List tables
docker exec -it trustos-postgres psql -U postgres -d trustos_dev -c "\dt"

# Describe table
docker exec -it trustos-postgres psql -U postgres -d trustos_dev -c "\d users"

# Connect to database shell
docker exec -it trustos-postgres psql -U postgres -d trustos_dev

# Drop all tables (careful!)
docker exec -it trustos-postgres psql -U postgres -d trustos_dev -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
```

**Docker:**
```bash
# Stop PostgreSQL
docker stop trustos-postgres

# Start PostgreSQL
docker start trustos-postgres

# Remove container (deletes data!)
docker rm -f trustos-postgres

# Run setup script again
.\setup-postgres.ps1
```

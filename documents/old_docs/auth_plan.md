# TrustOS Authentication & User Management Plan

## Stack Overview

- **Backend:** FastAPI + SQLAlchemy
- **Frontend:** React 18
- **Authentication:** Amazon Cognito (OAuth2/JWT)
- **Database:** PostgreSQL (RDS)
- **Cloud:** AWS (Cognito, SES, RDS)

## Architecture Principles

🔒 **Authentication:** Handled by Amazon Cognito (no passwords stored locally)  
🔐 **Authorization:** Backend verifies JWT and controls access  
🏢 **Multi-Tenancy:** Tenant Context Middleware enforces isolation  
📧 **Invitations:** SES email-based team collaboration  
🔧 **Feature Module Pattern:** Encapsulated, reusable, headless components (see section below)  

---

## Feature Module Pattern (Agency-Grade Reusability)

### Core Idea

This auth module is designed as a **Feature Module** — a self-contained package that can be dropped into any SaaS app without refactoring. It handles all authentication and user management logic internally while exposing hooks, services, and headless components that consuming apps can style and customize.

### Principles

**Encapsulation** — Module manages all auth/tenant logic internally  
**Headless Components** — UI is layout-agnostic; apps control styling and placement  
**Pluggable** — Integrate via root-level AuthProvider; works in any React app  
**Testable in Isolation** — Can be tested independently before app integration  
**Configurable** — Props, feature flags, and config objects allow per-app customization  

### Module Exports

**Hooks** (state & logic, reusable everywhere):
- `useAuth()` → `{ user, login, logout, isLoading }`
- `useTenant()` → `{ tenant, changeTenant }`
- `useCurrentUser()` → `{ user, isAdmin }`
- `useRole()` → `{ role, can(action) }` for fine-grained permissions

**Services** (API clients, framework-agnostic):
- `cognitoClient` → Cognito auth flows
- `authApi` → Backend API calls + JWT management

**Components** (headless, fully configurable):
- `LoginForm` → layout-agnostic, accepts className and renderHeader prop
- `SignupForm` → customizable UI, handles Cognito sync
- `InviteUserModal` → flexible invite workflow
- `UserList` → table component with role selection

**Context** (global state):
- `AuthProvider` → wraps app, manages auth state
- `TenantSwitcher` → let users switch between tenants

### Why This Matters for Agencies

When you build SaaS App #2, #3, etc., you don't rewrite auth. You:

1. Copy `frontend/src/features/auth_usermanagement/` to new app
2. Copy `backend/app/features/auth_usermanagement/` to new app
3. Wrap your app with `<AuthProvider>` (one line)
4. Style components per your client's brand (props + CSS)
5. Done — auth works identically across all apps

Fixes in the shared module propagate to all apps automatically.

---

## Request Flow Architecture

```
┌──────────────────────────────┐
│    React Frontend App         │
│ pages/LoginPage, SignupPage  │
│ (App controls layout)        │
└──────────────┬───────────────┘
               │ Uses
               ▼
┌──────────────────────────────┐
│  Auth Feature Module          │
│  Hooks: useAuth(), useTenant()│
│  Component: LoginForm (headless)
│  Service: authApi             │
└──────────────┬───────────────┘
               │ JWT + X-Tenant-ID
               ▼
┌──────────────────────────────┐
│    Amazon Cognito             │
│    (Authentication provider)  │
└──────────────┬───────────────┘
               │ JWT Token
               ▼
┌──────────────────────────────┐
│    FastAPI Backend            │
│  Middleware: TenantContext    │
│    - Verify JWT               │
│    - Load User + Membership   │
│    - Validate Tenant Access   │
└──────────────┬───────────────┘
               │ Tenant-Scoped Query
               ▼
┌──────────────────────────────┐
│  PostgreSQL / RDS             │
│  Tables: tenants, users,      │
│  memberships, sessions, etc.  │
│  Optional: Row-Level Security │
└──────────────────────────────┘
```

---

## Phase 0: Hard Project Boundaries

**Goal:** Prevent architecture drift and establish strict constraints.

### Human Tasks

- [ done] Create repository structure (Feature Module ready):
  ```
  backend/
    app/
      main.py
      config.py
      features/
        auth_usermanagement/       # Reusable across apps
          api/
          models/
          services/
          security/
          schemas/
  frontend/
    src/
      features/
        auth_usermanagement/       # Reusable across apps
          components/
          hooks/
          services/
          context/
      ui/                          # Shared UI primitives
      pages/                       # App-specific layouts
  infra/
  docs/
  ```

- [ done] Create `.env.example`:
  ```bash
  # AWS Cognito
  COGNITO_REGION=eu-west-1
  COGNITO_USER_POOL_ID=
  COGNITO_CLIENT_ID=
  
  # Database
  DATABASE_URL=postgresql://user:pass@localhost:5432/trustos
  
  # Environment
  APP_ENV=local
  ```

- [done ] Create `docs/auth_rules.md` with strict rules:
  ```markdown
  # Authentication Rules (Non-Negotiable)
  
  1. Authentication is handled by Amazon Cognito
  2. Backend ONLY verifies JWT tokens
  3. Backend controls all authorization logic
  4. NO passwords stored in local database
  5. User identity is Cognito `sub` claim
  6. All queries MUST be tenant-scoped
  ```

### AI Agent Tasks

- [ done] Create module skeleton:
  ```
  backend/app/auth_usermanagement/
    __init__.py
    api/
      __init__.py
    models/
      __init__.py
    services/
      __init__.py
    security/
      __init__.py
    schemas/
      __init__.py
  ```

- [ done] Register router in `backend/app/main.py`:
  ```python
  from auth_usermanagement.api import router as auth_router
  app.include_router(auth_router, prefix="/auth", tags=["auth"])
  ```

### Constraints for AI

❌ Agent must NOT:
- Create AWS resources
- Create login endpoints
- Implement password authentication
- Replace or bypass Cognito

✅ Agent MUST:
- Use Cognito for authentication
- Only verify tokens
- Follow tenant isolation patterns

### Test Checkpoint

```bash
# Start FastAPI
uvicorn app.main:app --reload

# Test health endpoint
curl http://localhost:8000/health
```

**Expected:** `{"status": "ok"}`

---

## Phase 1: Cognito Infrastructure Setup

**Goal:** Configure identity provider before implementing backend logic.

### Human Tasks

- [x] Create AWS Cognito User Pool:
  - **Sign-in options:** Email
  - **Email verification:** Required
  - **MFA:** Optional (recommended for production)
  - **Password policy:** AWS default (strong)

- [x] Create Cognito App Client:
  - **Authentication flows:** 
    - Authorization code grant
    - Refresh token
  - **Client secret:** None (public client)
  - **Refresh token expiration:** 30 days
  - **Access token expiration:** 1 hour
  - **ID token expiration:** 1 hour

- [x] Configure Callback URLs:
  ```
  http://localhost:3000/callback
  http://localhost:3000
  ```

- [x] Configure Sign-out URLs:
  ```
  http://localhost:3000
  ```

- [x] Copy environment values to `.env`:
  ```bash
  COGNITO_REGION=eu-west-1
  COGNITO_USER_POOL_ID=eu-west-1_ynis0WItp
  COGNITO_CLIENT_ID=79pef2au4irn8s7hcic9ik9d4p
  ```

### AI Agent Tasks

- [x] Create `security/jwt_verifier.py`:
  - Download JWKS from Cognito
  - Validate JWT signature
  - Verify token expiration
  - Extract claims (`sub`, `email`, `cognito:username`)
  
- [x] Implement function signature:
  ```python
  def verify_token(token: str) -> TokenPayload:
      """
      Verify Cognito JWT and return payload.
      
      Raises:
          InvalidTokenError: If token is invalid/expired
      """
  ```

- [x] Create `schemas/token.py`:
  ```python
  class TokenPayload(BaseModel):
      sub: str  # Cognito user ID
      email: str
      username: str
      exp: int
      iat: int
  ```

### Constraints

✅ Agent MUST:
- Only verify tokens (never issue them)
- Download JWKS from Cognito endpoint
- Validate token signature cryptographically

❌ Agent must NOT:
- Implement login logic
- Store tokens in database
- Create custom authentication

### Test Checkpoint

**Manual Flow:**
1. Go to Cognito Hosted UI: `https://<your-domain>.auth.eu-west-1.amazoncognito.com/login`
2. Sign up with email
3. Verify email
4. Login and copy `access_token` from URL
5. Test endpoint:

```bash
curl -H "Authorization: Bearer <access_token>" \
  http://localhost:8000/auth/debug-token
```

**Expected:** User claims returned

### Phase 1.1: Explicit `cognito:username` Mapping (Recommended)

**Goal:** Ensure Cognito username is exposed consistently in typed token payloads.

### Why this matters

Cognito may send username as `cognito:username` (with a colon). If schema only defines `username`, `token_payload.username` can be empty even when the token contains `cognito:username`.

### AI Agent Tasks

- [ ] Update `schemas/token.py` to map `cognito:username` into a typed field.
- [ ] Keep backward compatibility with existing `username` usage.
- [ ] Keep allowing additional Cognito claims.

### Suggested Implementation (Pydantic v2)

```python
from pydantic import BaseModel, Field, AliasChoices, ConfigDict
from typing import Optional

class TokenPayload(BaseModel):
    sub: str
    email: str
    username: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("cognito:username", "username")
    )
    exp: int
    iat: int

    model_config = ConfigDict(extra="allow")
```

### Validation Checkpoint

1. Obtain a Cognito token that includes `cognito:username`.
2. Call:
   ```bash
   curl -H "Authorization: Bearer <access_token>" \
     http://localhost:8000/auth/debug-token
   ```
3. Confirm backend processing can read username predictably via `token_payload.username`.

### Constraints

✅ Agent MUST:
- Preserve JWT verification behavior (signature, issuer, audience, expiration).
- Keep compatibility with tokens that only include `username`.

❌ Agent must NOT:
- Add login/password authentication logic.
- Replace Cognito as authentication source.

---

## Phase 2: Database Layer (Multi-Tenant Schema)

**Goal:** Create PostgreSQL schema for SaaS multi-tenancy.

### Human Tasks

- [x] Setup local PostgreSQL:
  ```bash
  # Option 1: Docker
  docker run -d \
    --name trustos-postgres \
    -e POSTGRES_PASSWORD=postgres \
    -e POSTGRES_DB=trustos \
    -p 5432:5432 \
    postgres:15
  
  # Option 2: Install locally or use RDS
  ```

- [x] Configure `DATABASE_URL` in `.env`

- [x] Initialize Alembic:
  ```bash
  cd backend
  alembic init alembic
  ```

### AI Agent Tasks

- [x] Create SQLAlchemy models in `models/`:

**`models/tenant.py`:**
```python
class Tenant(Base):
    __tablename__ = "tenants"
    
    id = Column(UUID, primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)
    plan = Column(String(50), default="free")  # free, pro, enterprise
    status = Column(String(20), default="active")  # active, suspended
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

**`models/user.py`:**
```python
class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID, primary_key=True, default=uuid4)
    cognito_sub = Column(String(255), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(255))
    is_platform_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

**`models/membership.py`:**
```python
class Membership(Base):
    __tablename__ = "memberships"
    
    id = Column(UUID, primary_key=True, default=uuid4)
    user_id = Column(UUID, ForeignKey("users.id"), nullable=False)
    tenant_id = Column(UUID, ForeignKey("tenants.id"), nullable=False)
    role = Column(String(20), nullable=False)  # owner, admin, member, viewer
    status = Column(String(20), default="active")  # active, suspended
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (UniqueConstraint('user_id', 'tenant_id'),)
```

**`models/invitation.py`:**
```python
class Invitation(Base):
    __tablename__ = "invitations"
    
    id = Column(UUID, primary_key=True, default=uuid4)
    tenant_id = Column(UUID, ForeignKey("tenants.id"), nullable=False)
    email = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)
    token = Column(String(255), unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    accepted_at = Column(DateTime)
    created_by = Column(UUID, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
```

**`models/session.py`:**
```python
class Session(Base):
    __tablename__ = "sessions"
    
    id = Column(UUID, primary_key=True, default=uuid4)
    user_id = Column(UUID, ForeignKey("users.id"), nullable=False)
    refresh_token_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    revoked_at = Column(DateTime)
```

- [x] Create Alembic migration:
  ```bash
  alembic revision --autogenerate -m "Create auth tables"
  ```

### Constraints

✅ Agent MUST:
- Use `cognito_sub` as user identity (not email)
- Never store passwords
- Include `tenant_id` foreign keys for multi-tenancy
- Add proper indexes

❌ Agent must NOT:
- Create authentication tables
- Store password hashes
- Create custom user credentials

### Test Checkpoint

```bash
# Run migration
alembic upgrade head

# Verify tables exist
psql -d trustos -c "\dt"
```

**Expected tables:**
- `tenants`
- `users`
- `memberships`
- `invitations`
- `sessions`

---

## Phase 3: User Sync (Cognito → Database)

**Goal:** Link Cognito users with application database.

### AI Agent Tasks

- [x] Create endpoint `POST /auth/sync`:

```python
@router.post("/sync")
async def sync_user(
    token_payload: TokenPayload = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """
    Sync Cognito user to database.
    Called after successful Cognito login.
    """
    # Check if user exists
    user = db.query(User).filter(User.cognito_sub == token_payload.sub).first()
    
    if not user:
        # Create new user
        user = User(
            cognito_sub=token_payload.sub,
            email=token_payload.email,
            name=token_payload.get("name")
        )
        db.add(user)
        db.commit()
    
    return {"user_id": user.id, "email": user.email}
```

- [x] Create service `services/user_service.py`:
  - `sync_user_from_cognito(token_payload)` → User
  - `get_user_by_cognito_sub(sub)` → User | None
  - `get_user_by_id(user_id)` → User | None

### Constraints

✅ Agent MUST:
- Store only: `cognito_sub`, `email`, `name`
- Extract data from JWT claims
- Handle idempotent syncing

❌ Agent must NOT:
- Create login endpoint
- Store passwords or tokens
- Implement custom authentication

### Test Checkpoint

**Flow:**
1. Login via Cognito Hosted UI
2. Get `access_token`
3. Call:
   ```bash
   curl -X POST \
     -H "Authorization: Bearer <access_token>" \
     http://localhost:8000/auth/sync
   ```

**Expected:** User row created in database

```sql
SELECT * FROM users;
```

---

## Phase 4: Authentication Dependency

**Goal:** Secure backend endpoints with JWT validation.

### AI Agent Tasks

- [x] Create dependency `security/dependencies.py`:

```python
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Verify JWT and return current user.
    
    Raises:
        HTTPException 401: If token invalid
        HTTPException 404: If user not found
    """
    payload = verify_token(token)
    user = db.query(User).filter(User.cognito_sub == payload.sub).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user
```

- [x] Create protected endpoint `GET /auth/me`:

```python
@router.get("/me")
async def get_current_user_profile(
    current_user: User = Depends(get_current_user)
):
    """Get authenticated user profile."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "is_platform_admin": current_user.is_platform_admin
    }
```

### Constraints

✅ Agent MUST:
- Require valid JWT for protected routes
- Load user from database (not trust JWT data alone)
- Return 401 for invalid/expired tokens

❌ Agent must NOT:
- Trust frontend user data
- Skip JWT verification
- Allow unauthenticated access to protected routes

### Test Checkpoint

```bash
# With valid token
curl -H "Authorization: Bearer <valid_token>" \
  http://localhost:8000/auth/me

# Without token
curl http://localhost:8000/auth/me
```

**Expected:**
- With token: User profile returned
- Without token: 401 Unauthorized

---

## Phase 5: Tenant Creation

**Goal:** Enable multi-tenant organization creation.

### AI Agent Tasks

- [x] Create endpoint `POST /tenants`:

```python
@router.post("/tenants")
async def create_tenant(
    data: TenantCreateSchema,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create new tenant (organization)."""
    # Create tenant
    tenant = Tenant(name=data.name, plan=data.plan)
    db.add(tenant)
    db.flush()
    
    # Create owner membership
    membership = Membership(
        user_id=current_user.id,
        tenant_id=tenant.id,
        role="owner"
    )
    db.add(membership)
    db.commit()
    
    return {"tenant_id": tenant.id, "name": tenant.name}
```

- [x] Create endpoint `GET /tenants/my`:

```python
@router.get("/tenants/my")
async def get_my_tenants(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all tenants user belongs to."""
    memberships = db.query(Membership).filter(
        Membership.user_id == current_user.id,
        Membership.status == "active"
    ).all()
    
    return [
        {
            "tenant_id": m.tenant.id,
            "name": m.tenant.name,
            "role": m.role
        }
        for m in memberships
    ]
```

### Constraints

✅ Agent MUST:
- Automatically create owner membership on tenant creation
- Enforce authentication (require current_user)
- Return tenant list for multi-tenant users

### Test Checkpoint

```bash
# Create tenant
curl -X POST \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "Acme Corp", "plan": "pro"}' \
  http://localhost:8000/tenants

# List my tenants
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/tenants/my
```

**Verify:** Membership row created with role="owner"

---

## Phase 6: Tenant Context Middleware (Critical for Multi-Tenancy)

**Goal:** Enforce tenant isolation at the request level.

### AI Agent Tasks

- [x] Create `security/tenant_context.py`:

```python
from dataclasses import dataclass
from uuid import UUID

@dataclass
class TenantContext:
    """Request-scoped tenant context."""
    user_id: UUID
    tenant_id: UUID
    role: str
    is_platform_admin: bool
```

- [x] Create middleware `security/tenant_middleware.py`:

```python
from starlette.middleware.base import BaseHTTPMiddleware

class TenantContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Skip for public routes
        if request.url.path in ["/health", "/auth/sync"]:
            return await call_next(request)
        
        # Get tenant from header
        tenant_id = request.headers.get("X-Tenant-ID")
        
        if not tenant_id:
            return JSONResponse(
                status_code=400,
                content={"detail": "X-Tenant-ID header required"}
            )
        
        # Verify JWT and load user
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        payload = verify_token(token)
        
        # Load user and verify membership
        user = db.query(User).filter(User.cognito_sub == payload.sub).first()
        
        membership = db.query(Membership).filter(
            Membership.user_id == user.id,
            Membership.tenant_id == tenant_id,
            Membership.status == "active"
        ).first()
        
        if not membership and not user.is_platform_admin:
            return JSONResponse(
                status_code=403,
                content={"detail": "Not a member of this tenant"}
            )
        
        # Create context
        request.state.tenant_context = TenantContext(
            user_id=user.id,
            tenant_id=UUID(tenant_id),
            role=membership.role if membership else "platform_admin",
            is_platform_admin=user.is_platform_admin
        )
        
        return await call_next(request)
```

- [x] Create dependency `get_tenant_context()`:

```python
def get_tenant_context(request: Request) -> TenantContext:
    """Get current request tenant context."""
    if not hasattr(request.state, "tenant_context"):
        raise HTTPException(status_code=403, detail="Tenant context not available")
    return request.state.tenant_context
```

- [x] Register middleware in `main.py`:

```python
app.add_middleware(TenantContextMiddleware)
```

### Constraints

✅ Agent MUST:
- Validate tenant membership from database
- Reject requests without valid membership
- Allow platform admin bypass
- Store context in `request.state`

❌ Agent must NOT:
- Trust X-Tenant-ID without validation
- Skip membership checks
- Allow cross-tenant access

### Test Checkpoint

```bash
# Valid tenant access
curl -H "Authorization: Bearer <token>" \
     -H "X-Tenant-ID: <tenant_uuid>" \
     http://localhost:8000/tenants/my

# Invalid tenant access
curl -H "Authorization: Bearer <token>" \
     -H "X-Tenant-ID: <wrong_uuid>" \
     http://localhost:8000/tenants/my
```

**Expected:**
- Valid: Success
- Invalid: 403 Forbidden

---

## Phase 7: Role-Based Authorization Guards

**Goal:** Protect tenant resources by role.

### AI Agent Tasks

- [x] Create `security/guards.py`:

```python
def require_role(*allowed_roles: str):
    """Require specific tenant role."""
    def dependency(ctx: TenantContext = Depends(get_tenant_context)):
        if ctx.role not in allowed_roles and not ctx.is_platform_admin:
            raise HTTPException(
                status_code=403,
                detail=f"Requires role: {', '.join(allowed_roles)}"
            )
        return ctx
    return dependency

# Convenience guards
require_owner = require_role("owner")
require_admin = require_role("owner", "admin")
require_member = require_role("owner", "admin", "member")
```

- [x] Example usage in routes:

```python
@router.delete("/tenants/{tenant_id}/users/{user_id}")
async def remove_user(
    tenant_id: UUID,
    user_id: UUID,
    ctx: TenantContext = Depends(require_admin),  # Only owner/admin
    db: Session = Depends(get_db)
):
    """Remove user from tenant (admin only)."""
    # Implementation
```

### Roles Hierarchy

```
owner       - Full control, can delete tenant
admin       - Manage users, settings
member      - Access tenant data
viewer      - Read-only access
```

### Test Checkpoint

```bash
# As owner - should succeed
curl -X DELETE \
  -H "Authorization: Bearer <owner_token>" \
  -H "X-Tenant-ID: <tenant_id>" \
  http://localhost:8000/tenants/<tenant_id>/users/<user_id>

# As viewer - should fail
curl -X DELETE \
  -H "Authorization: Bearer <viewer_token>" \
  -H "X-Tenant-ID: <tenant_id>" \
  http://localhost:8000/tenants/<tenant_id>/users/<user_id>
```

---

## Phase 8: Invitation System

**Goal:** Enable team collaboration via email invitations.

### Human Tasks

- [ ] Setup Amazon SES:
  - Verify email domain or single email
  - Request production access (if needed)
  - Get SMTP credentials or use AWS SDK

- [ ] Configure environment:
  ```bash
  SES_REGION=eu-west-1
  SES_SENDER_EMAIL=noreply@trustos.io
  ```

### AI Agent Tasks

- [ ] Create `POST /tenants/{tenant_id}/invite`:

```python
@router.post("/tenants/{tenant_id}/invite")
async def invite_user(
    tenant_id: UUID,
    data: InviteUserSchema,
    ctx: TenantContext = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Invite user to tenant."""
    # Generate secure token
    invite_token = secrets.token_urlsafe(32)
    
    # Create invitation
    invitation = Invitation(
        tenant_id=tenant_id,
        email=data.email,
        role=data.role,
        token=invite_token,
        expires_at=datetime.utcnow() + timedelta(days=7),
        created_by=ctx.user_id
    )
    db.add(invitation)
    db.commit()
    
    # Send email via SES
    await send_invitation_email(
        to_email=data.email,
        invite_url=f"https://app.trustos.io/invite/{invite_token}",
        tenant_name=ctx.tenant.name
    )
    
    return {"invitation_id": invitation.id}
```

- [ ] Create `GET /invites/{token}`:

```python
@router.get("/invites/{token}")
async def get_invitation(token: str, db: Session = Depends(get_db)):
    """Get invitation details (public endpoint)."""
    invitation = db.query(Invitation).filter(
        Invitation.token == token,
        Invitation.accepted_at == None,
        Invitation.expires_at > datetime.utcnow()
    ).first()
    
    if not invitation:
        raise HTTPException(status_code=404, detail="Invalid or expired invitation")
    
    return {
        "tenant_name": invitation.tenant.name,
        "role": invitation.role,
        "email": invitation.email
    }
```

- [ ] Create `POST /invites/accept`:

```python
@router.post("/invites/accept")
async def accept_invitation(
    data: AcceptInviteSchema,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Accept invitation and create membership."""
    invitation = db.query(Invitation).filter(
        Invitation.token == data.token,
        Invitation.accepted_at == None,
        Invitation.expires_at > datetime.utcnow()
    ).first()
    
    if not invitation:
        raise HTTPException(status_code=404, detail="Invalid invitation")
    
    # Verify email matches
    if invitation.email != current_user.email:
        raise HTTPException(status_code=403, detail="Email mismatch")
    
    # Create membership
    membership = Membership(
        user_id=current_user.id,
        tenant_id=invitation.tenant_id,
        role=invitation.role
    )
    db.add(membership)
    
    # Mark invitation as accepted
    invitation.accepted_at = datetime.utcnow()
    db.commit()
    
    return {"tenant_id": invitation.tenant_id}
```

- [ ] Create `services/email_service.py`:
  ```python
  async def send_invitation_email(to_email, invite_url, tenant_name):
      """Send invitation email via SES."""
  ```

### Test Checkpoint

**Flow:**
1. Admin invites user: `POST /tenants/{id}/invite`
2. Check email received
3. User clicks invite link
4. User accepts: `POST /invites/accept`
5. Verify membership created

---

## Phase 9: User Management APIs

**Goal:** Tenant admins manage team members.

### AI Agent Tasks

- [x] Create `GET /tenants/{tenant_id}/users`:

```python
@router.get("/tenants/{tenant_id}/users")
async def list_tenant_users(
    tenant_id: UUID,
    ctx: TenantContext = Depends(require_member),
    db: Session = Depends(get_db)
):
    """List all users in tenant."""
    memberships = db.query(Membership).filter(
        Membership.tenant_id == tenant_id,
        Membership.status == "active"
    ).all()
    
    return [
        {
            "user_id": m.user.id,
            "email": m.user.email,
            "name": m.user.name,
            "role": m.role,
            "joined_at": m.created_at
        }
        for m in memberships
    ]
```

- [x] Create `PATCH /tenants/{tenant_id}/users/{user_id}/role`:

```python
@router.patch("/tenants/{tenant_id}/users/{user_id}/role")
async def update_user_role(
    tenant_id: UUID,
    user_id: UUID,
    data: UpdateRoleSchema,
    ctx: TenantContext = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Update user role (admin only)."""
    membership = db.query(Membership).filter(
        Membership.tenant_id == tenant_id,
        Membership.user_id == user_id
    ).first()
    
    if not membership:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent removing last owner
    if membership.role == "owner" and data.role != "owner":
        owner_count = db.query(Membership).filter(
            Membership.tenant_id == tenant_id,
            Membership.role == "owner"
        ).count()
        
        if owner_count == 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot remove last owner"
            )
    
    membership.role = data.role
    db.commit()
    
    return {"user_id": user_id, "role": data.role}
```

- [x] Create `DELETE /tenants/{tenant_id}/users/{user_id}`:

```python
@router.delete("/tenants/{tenant_id}/users/{user_id}")
async def remove_user(
    tenant_id: UUID,
    user_id: UUID,
    ctx: TenantContext = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Remove user from tenant."""
    membership = db.query(Membership).filter(
        Membership.tenant_id == tenant_id,
        Membership.user_id == user_id
    ).first()
    
    if not membership:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Soft delete
    membership.status = "removed"
    db.commit()
    
    return {"message": "User removed"}
```

### Authorization Matrix

| Action | Owner | Admin | Member | Viewer |
|--------|-------|-------|--------|--------|
| View users | ✅ | ✅ | ✅ | ✅ |
| Invite users | ✅ | ✅ | ❌ | ❌ |
| Change roles | ✅ | ✅ | ❌ | ❌ |
| Remove users | ✅ | ✅ | ❌ | ❌ |
| Delete tenant | ✅ | ❌ | ❌ | ❌ |

---

## Phase 10: React Frontend Auth Module (Feature Module Pattern)

**Goal:** Build headless, reusable auth UI components and hooks for plug-and-play integration across all SaaS apps.

### Folder Structure (Auth Feature Module)

```
frontend/src/features/auth_usermanagement/
├── hooks/
│   ├── useAuth.ts              # Main auth hook
│   ├── useCurrentUser.ts        # User data hook
│   ├── useTenant.ts             # Tenant switcher hook
│   └── useRole.ts               # Permission checking
├── services/
│   ├── cognitoClient.ts         # Cognito auth flows
│   └── authApi.ts               # Backend API calls
├── components/
│   ├── LoginForm.tsx            # Headless (no layout)
│   ├── SignupForm.tsx
│   ├── InviteUserModal.tsx
│   ├── UserList.tsx
│   ├── TenantSwitcher.tsx
│   └── ProtectedRoute.tsx
├── context/
│   └── AuthProvider.tsx         # Global auth state
├── types/
│   └── index.ts
└── index.ts                     # Exports hooks, services, components
```

### Key Components (Headless Design)

**`hooks/useAuth.ts`** (Core hook, reusable everywhere):
```typescript
export const useAuth = () => {
  const context = useContext(AuthContext);
  return {
    user: context.user,           // Cognito user
    isLoading: context.isLoading,
    login: async (email, password) => { /* ... */ },
    logout: () => { /* ... */ },
    isAuthenticated: !!context.user
  };
};
```

Usage in any component:
```jsx
const App = () => {
  const { user, login } = useAuth();
  
  if (!user) return <LoginPage onLoginSuccess={login} />;
  return <Dashboard />;
};
```

**`components/LoginForm.tsx`** (Headless, fully customizable):
```typescript
interface LoginFormProps {
  onSuccess: (user: User) => void;        // Callback
  className?: string;                      // CSS override
  renderHeader?: () => React.ReactNode;   // Custom header
  renderFooter?: () => React.ReactNode;   // Custom footer
  isLoading?: boolean;
}

export const LoginForm: React.FC<LoginFormProps> = ({
  onSuccess,
  className = "login-form",
  renderHeader,
  isLoading
}) => {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  
  const handleSubmit = async (e) => {
    const user = await login(email, password);
    onSuccess(user);
  };
  
  return (
    <div className={className}>
      {renderHeader?.()}
      <input value={email} onChange={(e) => setEmail(e.target.value)} />
      <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
      <button onClick={handleSubmit} disabled={isLoading}>
        {isLoading ? "Logging in..." : "Login"}
      </button>
    </div>
  );
};
```

**`context/AuthProvider.tsx`** (Wraps entire app):
```typescript
export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState(null);
  const [tenant, setTenant] = useState(null);
  
  useEffect(() => {
    // On mount, check localStorage for JWT and restore session
    const token = localStorage.getItem("id_token");
    if (token) {
      // Verify and load user
      syncUserFromBackend(token).then(setUser);
    }
  }, []);
  
  const login = async (email: string, password: string) => {
    // Cognito login
    const result = await cognitoClient.authenticate(email, password);
    localStorage.setItem("id_token", result.idToken);
    
    // Sync with backend
    const user = await authApi.syncUser(result.accessToken);
    setUser(user);
    return user;
  };
  
  const logout = () => {
    localStorage.removeItem("id_token");
    setUser(null);
    setTenant(null);
  };
  
  return (
    <AuthContext.Provider value={{ user, tenant, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};
```

### AI Agent Tasks

### Hosted UI Decision (TrustOS)

TrustOS uses **Cognito Hosted UI** for sign-up and sign-in. This means local email/password forms are optional.

- Local `SignupForm` is **not required** for MVP when Hosted UI is the source of truth.
- Frontend should focus on redirecting to Cognito, handling callback code exchange, syncing user, and restoring session.

### AI Agent Tasks (Hosted UI Aligned)

- [ ] Finalize `hooks/useAuth.ts` API with `login` (Hosted UI redirect), `logout`, `isLoading`, `isAuthenticated`.
- [ ] Finalize `hooks/useTenant.ts` for tenant switching state.
- [ ] Finalize `hooks/useRole.ts` permission checks (role hierarchy helpers).
- [ ] Finalize `services/authApi.ts` with:
  - `syncUser(token)` → POST `/auth/sync`
  - `getCurrentUser(token)` → GET `/auth/me`
  - `listTenants(token)` → GET `/auth/tenants/my`
  - `switchTenant(tenantId)` → app-level current-tenant setter (or backend endpoint if later added)
- [ ] Finalize `services/cognitoClient.ts` Hosted UI methods:
  - build Hosted UI URL
  - redirect to Hosted UI
  - exchange authorization code for tokens
  - optional wrappers for compatibility (`authenticate`, `signup`) that delegate to Hosted UI flow
- [ ] Finalize `components/LoginForm.tsx` as headless trigger UI (no app-specific layout).
- [ ] `components/SignupForm.tsx` is optional in Hosted UI mode (only needed if product wants custom pre-signup UI).
- [ ] Finalize `context/AuthProvider.tsx` for callback handling, user sync, tenant bootstrap, session restore/logout.

### What Still Needs Implementation (Do Not Mark Complete Yet)

- [ ] Add a formal `switchTenant` API surface in frontend module (current state switch is local only).
- [ ] Normalize naming contract (`listTenants` vs `listMyTenants`) for cleaner reusable module API.
- [ ] Decide and standardize module path: keep `src/auth_usermanagement/` or move to `src/features/auth_usermanagement/`.
- [ ] Add explicit Hosted UI mode note in module README/comments so future contributors do not reintroduce local password auth.

### If You Later Build Your Own UI (Instead of Hosted Pages)

If TrustOS moves from Cognito Hosted UI to custom frontend screens, add these items before marking Phase 10 complete:

- [ ] Add headless `SignupForm` (and optional local `LoginForm` credentials mode) that only talks to Cognito APIs, never local passwords.
- [ ] Implement robust form validation and error states for sign-up/sign-in/challenge flows (unverified email, MFA challenge, password reset required).
- [ ] Add explicit callback/redirect handling for success and failure paths equal to Hosted UI reliability.
- [ ] Add anti-abuse controls in UI flows (rate-limit friendly retry UX, lockout messaging, clear support handoff).
- [ ] Add E2E tests for full auth lifecycle in custom UI mode (signup, verify, login, logout, token refresh, expired session handling).
- [ ] Keep Hosted UI as fallback path until custom UI has parity in security and reliability.

### Integration Example

In **TrustOS app**:
```jsx
// index.jsx
import { AuthProvider } from './features/auth_usermanagement/context/AuthProvider';
import { App } from './App';

ReactDOM.createRoot(document.getElementById('root')).render(
  <AuthProvider>
    <App />
  </AuthProvider>
);

// pages/LoginPage.jsx
import { LoginForm } from '../features/auth_usermanagement/components/LoginForm';

export const LoginPage = () => {
  return (
    <div className="trustos-login-wrapper">
      <header className="trustos-header">
        <img src="/logo.png" alt="TrustOS" />
        <h1>Brand Analytics</h1>
      </header>
      
      <LoginForm
        className="trustos-login-form"
        renderHeader={() => <p>Sign in to your TrustOS account</p>}
        onSuccess={() => navigate('/dashboard')}
      />
    </div>
  );
};
```

In **ClientA app** (different brand):
```jsx
// pages/LoginPage.jsx
import { LoginForm } from '../features/auth_usermanagement/components/LoginForm';

export const LoginPage = () => {
  return (
    <div className="clienta-login-wrapper">
      <aside className="clienta-sidebar">
        <ClientABranding />
      </aside>
      
      <main>
        <LoginForm
          className="clienta-login-form"
          renderHeader={() => <h2>ClientA Dashboard</h2>}
          onSuccess={() => navigate('/dashboard')}
        />
      </main>
    </div>
  );
};
```

**Key Difference:** Same `LoginForm` component, completely different UI per app using props and CSS.

### Constraints

✅ Agent MUST:
- Export hooks, services, components from `index.ts`
- Make components Accept className and render props
- Never hardcode layout or styling
- Isolate feature module logic from app pages

❌ Agent must NOT:
- Create app-specific page layouts in the module
- Hardcode tailwindcss or design system classes
- Import from pages/ or app/

### Test Checkpoint

**Storybook stories** (optional but recommended):
```typescript
// components/LoginForm.stories.tsx
export default {
  title: 'Auth/LoginForm'
};

export const Default = () => <LoginForm className="default" onSuccess={console.log} />;
export const WithCustomHeader = () => (
  <LoginForm
    renderHeader={() => <h2>Welcome to MyApp</h2>}
    onSuccess={console.log}
  />
);
```

---

### Phase 11: Admin UI Components

Build permission-aware management UI:

**Components:**
- `UserList.tsx` → List tenant users, sortable, searchable
- `InviteUserModal.tsx` → Invite form with role selector
- `RoleSelector.tsx` → Dropdown with available roles
- `TenantSwitcher.tsx` → Let users switch between tenants

**Features:**
- Headless design (CSS overridable)
- Permission checks via `useRole()` hook
- Admin-only visibility

**Example:**
```jsx
export const UserList = ({ className }) => {
  const { can } = useRole();
  const [users, setUsers] = useState([]);
  
  if (!can('list_users')) return <div>Unauthorized</div>;
  
  return (
    <table className={className}>
      <thead>
        <tr>
          <th>Name</th>
          <th>Role</th>
          {can('remove_users') && <th>Actions</th>}
        </tr>
      </thead>
      <tbody>
        {users.map(user => (
          <tr key={user.id}>
            <td>{user.name}</td>
            <td>{user.role}</td>
            {can('remove_users') && (
              <td>
                <button onClick={() => removeUser(user.id)}>Remove</button>
              </td>
            )}
          </tr>
        ))}
      </tbody>
    </table>
  );
};
```

### Phase 11 Status (Current)

Phase 11 components are present in the module, but completion is pending final hardening.

### What Still Needs Implementation (Do Not Mark Complete Yet)

- [ ] Enforce permissions inside components with `useRole()` (not only via parent props):
  - `InviteUserModal` should self-block non-admin/non-owner usage.
  - `UserList` should self-enforce view/manage actions by role.
- [ ] Add search and sorting to `UserList` (email/name/role sort; search by name/email).
- [ ] Reduce inline styles in admin components and keep them fully headless via `className` and optional render hooks.
- [ ] Standardize permission names for UI checks (for example `list_users`, `invite_users`, `remove_users`) and map them consistently to role logic.
- [ ] Add focused component/integration tests for admin visibility and forbidden actions.

---

### Phase 12: Security Hardening

Add production-grade security features:

**Backend:**
- Audit logging (log all user/membership changes)
- Session revocation (users can logout other devices)
- Rate limiting on auth endpoints (prevent brute force)
- Account suspension (admin can disable users)
- Security headers (HSTS, CSP, X-Frame-Options)

**Frontend:**
- Secure JWT storage (localStorage only, no cookies for XSS protection)
- Token refresh before expiry (refresh 5 min before exp)
- Logout on token revocation
- Content Security Policy headers

**Database:**
- PostgreSQL Row-Level Security (RLS) on all tables
- Never trust tenant_id from frontend alone
- Audit table tracks all auth events

**Example: RLS Policy**
```sql
-- Enable RLS on users table
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

-- Users can only see themselves + their tenants' users
CREATE POLICY users_isolation ON users
  FOR SELECT USING (
    auth.uid() = id OR
    id IN (
      SELECT user_id FROM memberships
      WHERE tenant_id = (
        SELECT tenant_id FROM memberships
        WHERE user_id = auth.uid() LIMIT 1
      )
    )
  );
```

### Phase 12 Status (Current)

**✅ Implemented:**
- Audit logging service (`audit_service.py` with `log_audit_event`)
- Rate limiting middleware (`RateLimitMiddleware` - 30 req/60s on auth endpoints)
- Security headers middleware (`SecurityHeadersMiddleware` - CSP, X-Frame-Options, HSTS, etc.)
- Session model with revocation capability (`Session.is_revoked`, `Session.revoke()`)
- Secure JWT storage (frontend uses `localStorage` only, no cookies)
- All middlewares registered in `main.py`

**❌ Missing (Do Not Mark Complete Yet):**

### What Still Needs Implementation

1. **Session revocation endpoints:**
   - `DELETE /auth/sessions/{session_id}` to revoke specific session
   - `DELETE /auth/sessions/all` to logout all devices (keep current session)
   - Frontend logout should call revocation endpoint

2. **Account suspension system:**
   - Add `is_active: bool` field to User model
   - Add `suspended_at: DateTime` field to User model
   - Create `PATCH /auth/users/{user_id}/suspend` endpoint (admin only)
   - Check `is_active` in `get_current_user` dependency

3. **Token refresh automation:**
   - Frontend: Decode JWT expiry time in `AuthProvider`
   - Add `useEffect` to check token expiry every 1 minute
   - Auto-refresh token 5 minutes before expiry via Cognito refresh token
   - Logout user if refresh fails

4. **Database Row-Level Security (RLS):**
   - Create Alembic migration to enable RLS on all tables
   - Add policies: users can only see their tenant's data
   - Test cross-tenant isolation with RLS active

5. **Audit table in database:**
   - Create `audit_events` table (id, event, actor_user_id, tenant_id, timestamp, details JSON)
   - Store audit logs in database instead of application logs only
   - Query audit history via `GET /auth/audit` (platform admin only)

6. **Tests:**
   - Unit tests for audit_service, rate limiting logic
   - Integration tests for session revocation flow
   - E2E test: verify RLS prevents cross-tenant access
   - E2E test: verify rate limiting blocks excessive requests

---

### Phase 13: Next-Gen SaaS Agency Template

Transform the auth module into a reusable template for all future projects.

**Template Structure:**
```
saas-template/
├── backend/
│   └── app/features/
│       ├── auth_usermanagement/   ← Reuse directly
│       ├── billing/               ← Future module
│       └── notifications/         ← Future module
├── frontend/
│   └── src/features/
│       ├── auth_usermanagement/   ← Reuse directly
│       ├── billing/
│       └── notifications/
├── ui/                            ← Shared button, modal, table
├── infra/
│   └── terraform/                 ← IaC for AWS resources
└── README.md
```

**For Next Project:**
1. Clone saas-template
2. Copy `features/auth_usermanagement/` (backend + frontend)
3. Copy `infra/` (Terraform for Cognito, RDS, SES)
4. Update `.env.example` with new AWS credentials
5. Run Phase 0–9 setup
6. Create app-specific pages/ and styling
7. Done (auth ready in 1 day instead of 2 weeks)

**Multi-App Integration Benefits:**
- ✅ Same auth logic across 10 SaaS apps
- ✅ Security fixes propagate automatically via git updates
- ✅ New features (SSO, MFA) added once, available everywhere
- ✅ Teams stay consistent across brands
- ✅ Reduces maintenance overhead

### Phase 13: Reusable Module Packaging

Package auth module for portability

### Phase 13 Status (Current)

**✅ Core Module Complete:**
- Backend auth module exists at `backend/app/auth_usermanagement/`
- Frontend auth module exists at `frontend/src/auth_usermanagement/`
- Module is feature-complete with all core auth functionality
- Clean separation from TrustOS-specific code (headless components, no tight coupling)

**❌ Missing Template/Packaging Work:**

### What Still Needs Implementation (Do Not Mark Complete Yet)

1. **Create template repository structure:**
   - Create new `trustos-saas-template` repository
   - Setup `backend/app/features/` folder structure
   - Setup `frontend/src/features/` folder structure
   - Copy auth module into template features/ folders

2. **Infrastructure as Code (IaC):**
   - Create Terraform/CDK scripts for Cognito User Pool setup
   - Create Terraform/CDK scripts for RDS PostgreSQL setup
   - Create Terraform/CDK scripts for SES email configuration
   - Create Terraform/CDK scripts for Redis ElastiCache (future)
   - Add `.env.example` with all required environment variables

3. **Documentation for template:**
   - Write template README.md with quick-start guide
   - Document how to copy auth module to new project
   - Document how to run infrastructure setup
   - Add migration guide for database setup
   - Add checklist for going from template → production app in 1 day

4. **Module README files:**
   - Create `backend/app/features/auth_usermanagement/README.md`
   - Create `frontend/src/features/auth_usermanagement/README.md`
   - Document module API surface (hooks, services, components)
   - Document environment variables required
   - Document integration steps

5. **Testing template reusability:**
   - Create a second test project using the template
   - Verify all steps work end-to-end
   - Document any missing dependencies or setup steps

---

## Testing Strategy

### Unit Tests
- JWT verification
- User sync logic
- Tenant membership validation
- Role guards

### Integration Tests
- Cross-tenant access blocking
- Multi-person invitation flow
- Permission enforcement
- Database isolation

### E2E Tests (Frontend)
- Complete login flow
- Tenant switching
- User invitation and acceptance
- Role-based UI visibility

---

## Success Metrics

✅ **Authentication:** Cognito JWT validation working  
✅ **Multi-Tenancy:** Zero cross-tenant data leaks  
✅ **Authorization:** Role-based guards enforced  
✅ **Invitations:** Email flow end-to-end  
✅ **UI:** Login, signup, user management functional  
✅ **Security:** Audit logs, session revocation enabled  

---

## Common Pitfalls (Avoid These)

❌ **Storing passwords in database** → Use Cognito  
❌ **Trusting X-Tenant-ID without validation** → Always verify membership  
❌ **Skipping JWT signature verification** → Always validate JWKS  
❌ **Forgetting `WHERE tenant_id = ?`** → Use RLS or base repository  
❌ **Hardcoding tenant in frontend** → Use TenantSwitcher  
❌ **Allowing users to change their own role** → Only admins  
❌ **No rate limiting on invite endpoints** → Prevents spam  

---

## Deployment Checklist

### Pre-Production

- [ ] All tests passing
- [ ] Environment variables configured
- [ ] Cognito user pool verified
- [ ] RDS database provisioned
- [ ] SES production access approved
- [ ] Rate limiting configured
- [ ] CORS origins restricted
- [ ] Audit logging enabled

### Production Launch

- [ ] Database migrations run
- [ ] First super admin user created
- [ ] Monitoring alerts configured
- [ ] Backup strategy tested
- [ ] Disaster recovery plan documented

---

## Multi-App Integration Examples

Once auth module is complete, it becomes a reusable plug-and-play feature for all future SaaS apps.

### Example: TrustOS App

**Step 1: Wrap app with AuthProvider**
```jsx
// frontend/index.jsx
import { AuthProvider } from './features/auth_usermanagement/context/AuthProvider';
import { App } from './App';

ReactDOM.createRoot(document.getElementById('root')).render(
  <AuthProvider>
    <App />
  </AuthProvider>
);
```

**Step 2: Create app-specific LoginPage**
```jsx
// frontend/pages/LoginPage.jsx
import { LoginForm } from '../features/auth_usermanagement/components/LoginForm';
import { useNavigate } from 'react-router-dom';

export const LoginPage = () => {
  const navigate = useNavigate();
  
  return (
    <div className="trustos-login-container">
      <header>
        <h1>TrustOS — Brand Analytics Platform</h1>
        <p>Understand what your stakeholders really think</p>
      </header>
      
      <LoginForm
        className="trustos-login-form"
        renderHeader={() => (
          <h2>Sign in to your account</h2>
        )}
        onSuccess={() => navigate('/dashboard')}
      />
      
      <footer>
        <p>Don't have an account? <Link to="/signup">Sign up</Link></p>
      </footer>
    </div>
  );
};
```

**Step 3: Protect routes using useAuth**
```jsx
// App.jsx
import { useAuth } from './features/auth_usermanagement/hooks/useAuth';

export const App = () => {
  const { user, isLoading } = useAuth();
  
  if (isLoading) return <LoadingSpinner />;
  if (!user) return <LoginPage />;
  
  return (
    <Layout>
      <Dashboard />
    </Layout>
  );
};
```

### Example: ClientA (Different Brand)

**Same module, completely different UI:**

```jsx
// frontend/pages/LoginPage.jsx
import { LoginForm } from '../features/auth_usermanagement/components/LoginForm';

export const LoginPage = () => {
  return (
    <div className="clienta-login-layout">
      <aside className="clienta-sidebar">
        <img src="/clienta-logo.png" alt="ClientA" />
        <h2>Professional Marketing Suite</h2>
        <nav>
          <a href="/">Home</a>
          <a href="#features">Features</a>
          <a href="#pricing">Pricing</a>
        </nav>
      </aside>
      
      <main className="clienta-login-main">
        <LoginForm
          className="clienta-login-form clienta-dark-theme"
          renderHeader={() => (
            <div className="clienta-auth-header">
              <h1>Welcome Back</h1>
              <p>Access your marketing campaigns</p>
            </div>
          )}
          onSuccess={() => navigate('/campaigns')}
        />
      </main>
    </div>
  );
};
```

**Same auth logic, entirely different layout.**

### Example: ClientB (Mobile-First)

```jsx
// frontend/pages/LoginPage.jsx
import { LoginForm } from '../features/auth_usermanagement/components/LoginForm';

export const LoginPage = () => {
  return (
    <div className="clientb-mobile-login">
      <LoginForm
        className="clientb-login-form-compact"
        renderHeader={() => (
          <div className="clientb-mobile-header">
            <BackButton />
            <h2>Sign In</h2>
          </div>
        )}
        onSuccess={() => navigate('/dashboard')}
      />
      
      <div className="clientb-signup-link">
        New user? <Link to="/signup">Create account</Link>
      </div>
    </div>
  );
};
```

### Reusing User Management

All apps use the same admin UI components:

```jsx
// All apps share this component
import { UserList } from '../features/auth_usermanagement/components/UserList';
import { InviteUserModal } from '../features/auth_usermanagement/components/InviteUserModal';

export const TeamManagementPage = () => {
  const [showInviteModal, setShowInviteModal] = useState(false);
  
  return (
    <div>
      <button onClick={() => setShowInviteModal(true)}>
        Invite Team Member
      </button>
      
      <UserList className="my-app-user-list" />
      
      {showInviteModal && (
        <InviteUserModal
          onClose={() => setShowInviteModal(false)}
          onSuccess={() => window.location.reload()}
        />
      )}
    </div>
  );
};
```

### Backend Module Reuse

Backend module is also reusable across projects:

**Copy entire folder:**
```bash
# For new SaaS project
cp -r saas-template/backend/app/features/auth_usermanagement \
      my-new-saas/backend/app/features/auth_usermanagement

# Register in main.py
app.include_router(auth_router, prefix="/auth")
```

**TenantContext middleware works identically in all apps** because it's agnostic to business logic.

### Summary: One Module, Infinite Apps

| App | UI Theme | Auth Logic | Database | Tenant Isolation |
|-----|----------|-----------|----------|-----------------|
| TrustOS | Light, modern | Same | Shared template | ✅ Via middleware |
| ClientA | Dark, branded | Same | Shared template | ✅ Via middleware |
| ClientB | Mobile-first | Same | Shared template | ✅ Via middleware |
| ClientC | Custom design | Same | Shared template | ✅ Via middleware |

Logic centralized, UI distributed per brand.

---

## Next Steps After Completion

Once auth module is complete:

1. **Integrate with TrustOS features:**
   - Snapshots (tenant-scoped)
   - Clients (tenant-scoped)
   - Survey templates (tenant-scoped)

2. **Add permission system:**
   - Feature flags per tenant
   - Usage limits (plan-based)
   - Billing integration

3. **Build admin dashboard:**
   - Platform admin panel
   - Tenant analytics
   - Usage monitoring

---

## Next-Gen SaaS Agency Template (Complete Setup)

Once you complete auth module for TrustOS, you have the foundation for a reusable agency template that becomes your competitive advantage.

### Template Repository Structure

```
trustos-saas-template/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── db.py
│   │   └── features/
│   │       ├── auth_usermanagement/     ← Copy to all new projects
│   │       ├── billing/                 ← Build after auth works
│   │       └── notifications/           ← Optional future module
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/App.jsx
│   │   ├── features/
│   │   │   ├── auth_usermanagement/     ← Copy to all new projects
│   │   │   ├── billing/
│   │   │   └── notifications/
│   │   ├── ui/                          ← Shared button, modal, input
│   │   │   ├── Button.jsx
│   │   │   ├── Modal.jsx
│   │   │   ├── Input.jsx
│   │   │   └── Table.jsx
│   │   └── pages/                       ← App-specific layouts
│   ├── vite.config.js
│   └── package.json
├── infra/
│   ├── terraform/
│   │   ├── cognito.tf
│   │   ├── rds.tf
│   │   ├── iam.tf
│   │   └── variables.tf
│   └── scripts/
│       ├── deploy.sh
│       └── setup-env.sh
├── .env.example
├── docker-compose.yml               ← Local dev environment
├── README.md
└── CONTRIBUTING.md
```

### Usage: Spinning Up New SaaS Project

**Scenario:** You need to build "Analytics Pro" for a new client in 2 weeks.

**Day 1-2: Bootstrap from template**
```bash
# Clone template
git clone https://github.com/agency/trustos-saas-template analytics-pro

# Install dependencies
cd analytics-pro
npm install
pip install -r backend/requirements.txt

# Configure environment
cp .env.example .env
# Fill in: COGNITO_* variables, DATABASE_URL, etc.

# Run locally
docker-compose up
npm run dev          # Frontend
python -m uvicorn app.main:app --reload  # Backend
```

**Day 3: Auth fully working**
```bash
git checkout feature/auth-usermanagement
# All Phases 0-9 already implemented
# Just customize pages/ for Analytics Pro brand
```

**Day 4-7: Add Analytics Pro features**
- Snapshot module (tenant-scoped)
- Report generation
- Custom dashboards

**Day 8-14: Polish & deploy**
- UI customization
- Testing
- Production deployment via CloudFormation

**Result:** Full production SaaS in 2 weeks instead of 8+ weeks.

### Template Advantages

**For Your Agency:**
- ✅ Reduce time-to-market (80% faster)
- ✅ Consistent architecture across clients
- ✅ Shared security patches (fix once, deploy everywhere)
- ✅ Reusable billing + notifications modules
- ✅ Built-in multi-tenancy (eliminate data leaks)
- ✅ Cost: Infrastructure is standard (no custom setup per project)

**For Your Clients:**
- ✅ Professional, secure auth system
- ✅ Team collaboration built-in
- ✅ GDPR-compliant multi-tenancy
- ✅ Scalable from 10 → 10k users

### Making the Template Production-Ready

Before cloning the template for 10 different client projects:

**Checklist:**
- [ ] Auth module passes all security audit tests
- [ ] TenantContext middleware is battle-tested
- [ ] Database RLS policies are enforced
- [ ] Cognito integration is documented
- [ ] All env variables are in .env.example
- [ ] Terraform IaC is working for AWS setup
- [ ] Docker compose works locally
- [ ] CI/CD pipeline configured
- [ ] Monitoring/alerting setup for production
- [ ] Disaster recovery plan documented

### Customization Points Per Client

Each new app controls:
- **pages/** → App-specific layouts, routes, branding
- **ui/colors.css** → Color scheme per client
- **pages/LoginPage.jsx** → Custom header/footer
- **pages/DashboardPage.jsx** → Feature-specific UI
- **.env** → Cognito pool ID, database, etc.
- **infra/variables.tf** → AWS region, instance size, etc.

**Auth logic never changes.** Same hooks, same middleware, same security guarantees.

### Example Client Customization

For "Analytics Pro" client:
```jsx
// only this file changes per app
// pages/LoginPage.jsx

export const LoginPage = () => {
  return (
    <div className="login-wrapper analytics-pro-brand">
      <header>
        <img src="/analytics-pro-logo.png" />
        <h1>Analytics Pro Dashboard</h1>
      </header>
      
      <LoginForm
        className="analytics-pro-login"
        renderHeader={() => <p>Sign in with your Analytics Pro account</p>}
        onSuccess={() => navigate('/campaigns')}
      />
    </div>
  );
};
```

Everything else (auth logic, multi-tenancy, API calls) is identical across all clients.

### Documentation for Template Users (Your Team)

Create `TEMPLATE_USAGE.md` in the repo:

```markdown
# SaaS Template Usage Guide

## For New Projects

1. Clone: `git clone ...`
2. Update `.env` with client Cognito details
3. Create `pages/` matching your client's brand
4. Deploy to `https://client-name.company.com`
5. All auth/multi-tenancy/billing is ready to go

## Customization Points

- **Frontend:** pages/, ui/colors.css, App.jsx
- **Backend:** features/billing/*, infra/
- **Do NOT modify:** features/auth_usermanagement/*, middleware/

## Adding New Features

1. Create `backend/app/features/my_feature/`
2. Create `frontend/src/features/my_feature/`
3. Use TenantContext in backend (auto-scoped)
4. Use useTenant() in frontend (auto-set X-Tenant-ID)
5. All requests are tenant-safe by default

## Deployment

```bash
terraform apply  # Creates AWS resources
git push        # Triggers CI/CD pipeline
```
```

---

**Last Updated:** March 7, 2026  
**Status:** Ready for implementation  
**Estimated Effort:** 10-12 days (full-stack developer)  
**Branch Strategy:** Feature branches from `dev`, merge via PR  
**Next Milestone:** After auth is complete, create dedicated `billing` feature module for subscription management

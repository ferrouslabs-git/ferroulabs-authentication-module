# Setup Guide: Integrating auth_usermanagement into a New Project

> How to add multi-tenant auth, user management, and permission-based access control to any FastAPI + React application.

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11+ | f-strings, `|` union types |
| Node.js | 18+ | Frontend build |
| PostgreSQL | 14+ | Row-level security support |
| AWS Cognito | — | User pool + app client (PKCE) |
| AWS SES | — | Optional, for invitation emails |

### Python Packages (backend/requirements.txt)

```
fastapi==0.110.0
uvicorn[standard]==0.27.1
sqlalchemy==2.0.25
psycopg2-binary==2.9.9
pydantic==2.6.1
pydantic-settings==2.1.0
python-dotenv==1.0.1
python-jose[cryptography]==3.3.0
requests==2.31.0
boto3==1.34.51
alembic==1.13.1
```

---

## Step 1: Copy the Module

Copy `backend/app/auth_usermanagement/` into your host project. The module is entirely self-contained — it brings its own models, routes, middleware, services, and schemas.

Your host project structure should look like:

```
your-project/
├── backend/
│   ├── app/
│   │   ├── config.py           ← host settings (you create)
│   │   ├── database.py         ← host DB runtime (you create)
│   │   ├── main.py             ← host entrypoint (you create)
│   │   └── auth_usermanagement/  ← copied module
│   ├── alembic/
│   │   └── env.py              ← host migration runner
│   ├── alembic.ini
│   └── requirements.txt
├── frontend/
│   └── src/
│       └── auth_usermanagement/  ← copied module
└── .env
```

---

## Step 2: Create Host Database Runtime

**File: `backend/app/database.py`**

The host app **must** own the database engine, session factory, and declarative base. The auth module imports these — it never creates its own.

```python
import os
from collections.abc import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/myapp")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

**Rule**: Never put `create_engine()`, `sessionmaker()`, or `declarative_base()` inside `auth_usermanagement/`. The module's `database.py` is a thin re-export layer — it's the **only** file that references `from app.database import ...`. All other module files use relative imports (`from ..database import Base`).

---

## Step 3: Create Host Settings

**File: `backend/app/config.py`**

Host owns root-level settings like CORS. Module settings remain in `auth_usermanagement/config.py`.

```python
from functools import lru_cache
import os
from pydantic_settings import BaseSettings
from app.auth_usermanagement.config import Settings, get_settings


class HostSettings(BaseSettings):
    cors_allowed_origins: str = os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:3000,http://localhost:5173",
    )

    @property
    def resolved_cors_allowed_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_host_settings() -> HostSettings:
    return HostSettings()
```

---

## Step 4: Wire the FastAPI App

**File: `backend/app/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_host_settings
from app.auth_usermanagement.api import router as auth_router
from app.auth_usermanagement.config import get_settings
from app.auth_usermanagement.security.rate_limit_middleware import RateLimitMiddleware
from app.auth_usermanagement.security.security_headers_middleware import SecurityHeadersMiddleware
from app.auth_usermanagement.security.tenant_middleware import TenantContextMiddleware

app = FastAPI(title="My App")
settings = get_settings()
host_settings = get_host_settings()

# CORS — host owned
app.add_middleware(
    CORSMiddleware,
    allow_origins=host_settings.resolved_cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth middleware stack (order matters — added last executes first)
app.add_middleware(TenantContextMiddleware, auth_prefix=settings.auth_api_prefix)
app.add_middleware(RateLimitMiddleware, auth_prefix=settings.auth_api_prefix)
app.add_middleware(SecurityHeadersMiddleware)

# Mount auth routes
app.include_router(auth_router, prefix=settings.auth_api_prefix, tags=["auth"])

# Your own routes
@app.get("/health")
async def health():
    return {"status": "ok"}
```

### Middleware Execution Order

Requests flow through middleware in reverse registration order:

```
Request → SecurityHeaders → RateLimit → TenantContext → Route Handler
Response ← SecurityHeaders ← RateLimit ← TenantContext ← Route Handler
```

- **SecurityHeadersMiddleware**: Adds CSP, X-Frame-Options, etc. to every response
- **RateLimitMiddleware**: IP-based rate limiting on sensitive auth endpoints
- **TenantContextMiddleware**: Validates X-Tenant-ID or X-Scope-Type/X-Scope-ID headers, stores on `request.state`

---

## Step 5: Environment Variables

**File: `.env`**

```env
# Database (host owned)
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/myapp

# CORS (host owned)
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173

# Cognito (module settings)
COGNITO_REGION=eu-west-1
COGNITO_USER_POOL_ID=eu-west-1_XXXXXXXXX
COGNITO_CLIENT_ID=your-cognito-app-client-id
COGNITO_DOMAIN=your-domain.auth.eu-west-1.amazoncognito.com

# SES (optional — for invitation emails)
SES_REGION=eu-west-1
SES_SENDER_EMAIL=noreply@yourdomain.com

# Frontend URL (for invitation links)
FRONTEND_URL=http://localhost:5173

# Cookie settings
COOKIE_SECURE=false

# Module prefix (default: /auth)
AUTH_API_PREFIX=/auth
AUTH_NAMESPACE=authum
```

---

## Step 6: Configure Roles and Permissions

**File: `backend/app/auth_usermanagement/auth_config.yaml`**

This YAML drives the entire permission system. Edit it to match your application's authorization needs.

```yaml
version: "3.0"

layers:
  account:
    enabled: true
    display_name: "Account"
  space:
    enabled: true
    display_name: "Space"

inheritance:
  account_member_space_access: none   # none | space_viewer | space_member

roles:
  platform:
    - name: super_admin
      display_name: "Super Admin"
      permissions:
        - platform:configure
        - accounts:manage
        - users:suspend

  account:
    - name: account_owner
      display_name: "Account Owner"
      permissions:
        - account:delete
        - account:read
        - spaces:create
        - members:manage
        - members:invite

    - name: account_admin
      display_name: "Account Admin"
      permissions:
        - account:read
        - spaces:create
        - members:invite

    - name: account_member
      display_name: "Account Member"
      permissions:
        - account:read

  space:
    - name: space_admin
      permissions: [space:delete, space:configure, space:read, members:manage, members:invite, data:read, data:write]
    - name: space_member
      permissions: [space:read, data:read, data:write]
    - name: space_viewer
      permissions: [space:read, data:read]
```

### Adding Custom Permissions

Add any `noun:verb` permission string. Use them in route guards:

```python
# In auth_config.yaml
- name: account_admin
  permissions:
    - reports:generate    # custom permission

# In your route
@router.post("/reports")
async def generate_report(
    ctx: ScopeContext = Depends(require_permission("reports:generate")),
    db: Session = Depends(get_db),
):
    ...
```

---

## Step 7: Alembic Migrations

### Initial Setup

```bash
cd backend
pip install alembic
alembic init alembic
```

### Configure `alembic/env.py`

```python
import sys
from pathlib import Path
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import Base, DATABASE_URL
from app.auth_usermanagement.models import (
    Tenant, User, Membership, Invitation, Session, RefreshTokenStore,
)

config = context.config
config.set_main_option("sqlalchemy.url", DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
```

### Run Migrations

Copy the migration files from `backend/alembic/versions/` into your project's `alembic/versions/` directory, then:

```bash
alembic upgrade head
```

The migration chain creates these tables in order:
1. `users`, `tenants`, `memberships`, `invitations` (core)
2. `sessions`, `audit_events`, `rate_limit_hits` (tracking)
3. `refresh_token_store` (cookie auth)
4. `role_definitions`, `permission_grants` (v3.0 RBAC)
5. `spaces` (sub-tenant grouping)
6. Row-level security policies (PostgreSQL only)

---

## Step 8: Frontend Wiring

### Copy Frontend Module

Copy `frontend/src/auth_usermanagement/` into your React project's `src/` directory.

### Configure Frontend Environment

**File: `frontend/.env`**

```env
VITE_API_BASE_URL=http://localhost:8001
VITE_COGNITO_DOMAIN=your-domain.auth.eu-west-1.amazoncognito.com
VITE_COGNITO_CLIENT_ID=your-cognito-app-client-id
VITE_COGNITO_REDIRECT_URI=http://localhost:5173/callback
```

### Wrap Your App

```jsx
import { AuthProvider, ProtectedRoute, TenantSwitcher, useAuth } from './auth_usermanagement'

function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/callback" element={<CallbackHandler />} />
        <Route path="/dashboard" element={
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        } />
      </Routes>
    </AuthProvider>
  )
}
```

### Available Frontend Exports

```javascript
// Context & hooks
AuthProvider, useAuth, useCurrentUser, useTenant, useRole, useSpace

// Components
LoginForm, ProtectedRoute, TenantSwitcher, RoleSelector,
InviteUserModal, UserList, SessionPanel, AcceptInvitation,
ToastProvider, AdminDashboard

// Services
authApi, cognitoClient
```

---

## Step 9: Cognito Setup

1. Create a Cognito User Pool in AWS Console
2. Add an App Client with:
   - Auth flow: `ALLOW_USER_SRP_AUTH`, `ALLOW_REFRESH_TOKEN_AUTH`
   - OAuth: Authorization code grant with PKCE
   - Callback URL: `http://localhost:5173/callback`
   - Sign-out URL: `http://localhost:5173`
3. Configure Hosted UI domain
4. Set the `COGNITO_*` env vars to match

See [cognito_and_sso_guide.md](cognito_and_sso_guide.md) for detailed Cognito configuration.

---

## Step 10: Verify Integration

### Run Tests

```bash
cd backend
pip install pytest httpx
pytest -q tests
```

### Quick API Smoke Test

```bash
# Health check
curl http://localhost:8001/health

# Should return 401 (no token)
curl http://localhost:8001/auth/me

# After Cognito login, sync user
curl -X POST http://localhost:8001/auth/sync \
  -H "Authorization: Bearer <your-jwt>"

# Create a tenant
curl -X POST http://localhost:8001/auth/tenants \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"name": "My Org"}'
```

### PostgreSQL RLS Tests

For production-grade tenant isolation verification:

```bash
RUN_POSTGRES_RLS_TESTS=1 DATABASE_URL=postgresql://... pytest -q tests/test_row_level_security.py
```

---

## Host Integration Contract

| Component | Host Owns | Module Owns |
|---|---|---|
| Database engine/session/Base | ✅ | imports from host |
| DATABASE_URL | ✅ | — |
| CORS configuration | ✅ | — |
| Alembic execution | ✅ | schema definitions |
| Cognito settings | — | ✅ |
| SES settings | — | ✅ |
| auth_config.yaml | — | ✅ |
| All models | — | ✅ |
| All routes | — | ✅ (host sets prefix) |
| Middleware logic | — | ✅ (host registers) |
| Permission guards | — | ✅ |
| JWT verification | — | ✅ |

---

## Docker-Based Local Development

A `docker-compose.yml` is provided at the project root for quick local setup:

```bash
docker compose up --build
```

This starts three services:

| Service | Image | Port | Purpose |
|---|---|---|---|
| **db** | postgres:15 | 5432 | PostgreSQL with health check |
| **backend** | ./backend (Dockerfile) | 8000 | FastAPI + auto-runs `alembic upgrade head` |
| **frontend** | ./frontend (Dockerfile) | 5173 | Vite React dev server |

The backend container automatically runs migrations on startup. The database uses a named Docker volume (`pgdata`) so data persists across restarts.

### Environment Overrides

The compose file reads `backend/.env` for Cognito and SES credentials. Override `DATABASE_URL` in the compose environment block (already set to `postgresql://postgres:postgres@db:5432/authsystem`).

For production, set `COOKIE_SECURE=true` and provide real Cognito/SES values.

---

## Cleanup Job Setup

The module provides `cleanup_service.run_cleanup()` for purging expired data. Call it on a schedule (e.g. nightly cron).

### Option A: Cron + Management Script

Create a script (e.g. `backend/scripts/run_cleanup.py`):

```python
from app.database import SessionLocal
from app.auth_usermanagement.services.cleanup_service import run_cleanup

db = SessionLocal()
try:
    result = run_cleanup(
        db,
        invitation_days=30,       # purge expired/revoked invitations older than 30d
        rate_limit_hours=24,      # purge rate-limit hits older than 24h
        audit_retention_days=365, # purge audit events older than 1 year (0 to skip)
    )
    print(f"Cleanup: {result}")
finally:
    db.close()
```

Schedule with cron:

```bash
# Run nightly at 2 AM
0 2 * * * cd /app && python scripts/run_cleanup.py
```

### Option B: Celery Beat

```python
from celery import Celery
from celery.schedules import crontab

app = Celery("myapp")

@app.task
def cleanup_auth_data():
    from app.database import SessionLocal
    from app.auth_usermanagement.services.cleanup_service import run_cleanup
    db = SessionLocal()
    try:
        run_cleanup(db)
    finally:
        db.close()

app.conf.beat_schedule = {
    "auth-cleanup-nightly": {
        "task": "cleanup_auth_data",
        "schedule": crontab(hour=2, minute=0),
    },
}
```

### Default Retention Periods

| Data | Default Retention | Configurable |
|---|---|---|
| Expired refresh tokens | Immediate (past `expires_at`) | No |
| Expired/revoked invitations | 30 days | `invitation_days` |
| Rate-limit hit records | 24 hours | `rate_limit_hours` |
| Audit events | 365 days | `audit_retention_days` (0 = skip) |

---

## API Versioning

The module's route prefix is configurable via `AUTH_API_PREFIX` (default: `/auth`). To version your API:

```env
AUTH_API_PREFIX=/v1/auth
```

All module endpoints will then be served under `/v1/auth/*`. The frontend must be updated to match:

```env
VITE_AUTH_API_BASE_PATH=/v1/auth
```

Existing clients using `/auth` will need to be migrated if you change the prefix.

---

## Suspended-User JWT Behavior

When a user is suspended via `PATCH /users/{id}/suspend`:

1. The user's `is_active` flag is set to `false` in the database
2. A Cognito `AdminUserGlobalSignOut` is issued to revoke their refresh tokens
3. Their existing access token (JWT) **remains valid** until it naturally expires (typically 1 hour)

**Mitigation**: Every protected endpoint calls `get_current_user()`, which checks `is_active` against the database. A suspended user receives `401 Account suspended` on any API call, even with a valid JWT. The token gap is limited to the window between suspension and their next API call.

---

## API Quick Reference

All endpoints are mounted under the configured prefix (default: `/auth`).

| Method | Path | Auth | Scope | Purpose |
|---|---|---|---|---|
| POST | /sync | Bearer | — | Sync Cognito user to DB |
| GET | /me | Bearer | — | Get current user profile |
| GET | /debug-token | Bearer | — | Debug JWT claims |
| POST | /tenants | Bearer | — | Create tenant |
| GET | /tenants/my | Bearer | — | List user's tenants |
| GET | /tenants/{id}/users | Bearer | account | List tenant members |
| PATCH | /tenants/{id}/users/{uid}/role | Bearer | account | Change member role |
| DELETE | /tenants/{id}/users/{uid} | Bearer | account | Remove member |
| POST | /invite | Bearer | account/space | Send invitation |
| POST | /invites/accept | Bearer | — | Accept invitation |
| GET | /invites/{token}/preview | — | — | Preview invitation |
| DELETE | /invites/{token} | Bearer | account/space | Revoke invitation |
| GET | /sessions | Bearer | account | List sessions |
| DELETE | /sessions/{id} | Bearer | account | Revoke session |
| POST | /spaces | Bearer | account | Create space |
| GET | /spaces/my | Bearer | account | List user's spaces |
| POST | /token/refresh | Cookie | — | Refresh access token |
| POST | /cookie/store-refresh | Bearer | — | Store refresh token |
| GET | /config/roles | — | — | List configured roles |
| GET | /config/permissions | — | — | List configured permissions |
| GET | /accounts | Bearer | platform | List all tenants (admin) |
| POST | /accounts/{id}/suspend | Bearer | platform | Suspend tenant |
| POST | /accounts/{id}/unsuspend | Bearer | platform | Unsuspend tenant |
| GET | /platform/users | Bearer | platform | List all users |
| POST | /platform/users/{id}/suspend | Bearer | platform | Suspend user |
| POST | /platform/users/{id}/unsuspend | Bearer | platform | Unsuspend user |

### Required Headers for Scoped Routes

```
Authorization: Bearer <jwt>
X-Tenant-ID: <tenant-uuid>
```

Or v3.0 scope headers:

```
Authorization: Bearer <jwt>
X-Scope-Type: account|space
X-Scope-ID: <uuid>
```

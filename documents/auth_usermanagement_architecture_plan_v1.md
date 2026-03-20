# Auth and User Management
Architecture Plan
v2.0 • Code-Aligned Implementation Contract

Date: 2026-03-18
Scope: Current code in backend/app/auth_usermanagement + frontend/src/auth_usermanagement
Rule: This document describes only what exists in code today.

---

## What Changed in v2.0
| # | Addition | Type | Why |
|---|----------|------|-----|
| 1 | Full database schema with column types, constraints, and indexes | Schema completeness | v1 listed table names only — insufficient for code review or onboarding |
| 2 | State machine definitions for invitation, session, user, tenant, and membership | Architecture addition | No formalized allowed transitions — silent state corruption possible without guards |
| 3 | Cognito sync and external call boundaries | Architecture addition | Cognito-succeeds / DB-fails window undocumented — must know where external calls sit |
| 4 | Role hierarchy enforcement matrix with guard bypass rules | Security completeness | Admin privilege escalation rules were implicit — must be explicit for auditors |
| 5 | Token lifecycle and management matrix | Security completeness | Four token types with different storage, scope, and rotation rules need a single reference |
| 6 | Complete testing strategy with 10 categories (77 tests) | Testing completeness | v1 had 5 release gates by file name — no visibility into what behaviors are verified |
| 7 | Concurrency and race condition analysis | Architecture addition | Concurrent session rotations, invitation accepts, and role updates had no documented invariants |
| 8 | Operational runbook expanded with decision trees | Ops completeness | v1 runbook had checklist items but no diagnostic decision trees |
| 9 | Future considerations and V2 evolution path | Forward planning | v1 had "known limitations" but no roadmap for resolution |
| 10 | Idempotency contract per operation | Architecture addition | Critical for retry safety — no operation had documented idempotency guarantees |

---

## 0. Purpose

This is the implementation contract for the auth and user management module.

It is not a wishlist.
It is not a future roadmap.
It is the locked description of current architecture, invariants, and operational rules derived from the codebase.

---

## 1. Design Principles

RULE: Non-negotiable decisions every developer must understand before writing a single line. When in doubt, come back here.

Principle 1 — Host Owns DB Runtime
The module must not create its own engine, SessionLocal, or Base in runtime code. Auth module DB runtime imports from host DB runtime. Any PR that adds `create_engine()`, `sessionmaker()`, or `declarative_base()` in reusable module paths must be blocked unless explicitly approved as standalone sandbox code.

```python
# CORRECT — auth module database.py
from app.database import Base, SessionLocal, get_db, engine

# WRONG — never do this in reusable module
engine = create_engine(DATABASE_URL)  # BLOCKED by review gate
```

Evidence:
- backend/app/database.py
- backend/app/auth_usermanagement/database.py
- backend/tests/test_db_ownership_boundary.py
- backend/tests/test_db_runtime_guardrails.py

Principle 2 — Host Owns Root App Config
Root settings such as CORS origins are host-owned. Module settings are auth-module specific. The auth module config must not define DATABASE_URL or any host-level setting.

Evidence:
- backend/app/config.py
- backend/app/main.py
- backend/app/auth_usermanagement/config.py

Principle 3 — Dependency Path Owns Tenant Validation
Middleware performs request prechecks only (header format, auth header presence). Tenant membership validation happens in the dependency path using a request-scoped DB session provided by the host's `get_db`. Middleware must never create an alternate DB validation path.

```python
# Middleware: pre-check only — no DB access
def tenant_middleware(request):
    validate_header_format(request.headers["X-Tenant-ID"])  # format check
    request.state.requested_tenant_id = tenant_id           # store for deps

# Dependency: real validation — uses host DB session  
def get_tenant_context(user=Depends(get_current_user), db=Depends(get_db)):
    membership = db.query(Membership).filter(...).first()   # actual DB check
```

Evidence:
- backend/app/auth_usermanagement/security/tenant_middleware.py
- backend/app/auth_usermanagement/security/dependencies.py

Principle 4 — No DB Session Creation in Middleware
Middleware must not instantiate `SessionLocal()` directly. This is enforced by static analysis in test gates — the tenant middleware source code is scanned for `SessionLocal(` calls.

Evidence:
- backend/app/auth_usermanagement/security/tenant_middleware.py
- backend/tests/test_db_ownership_boundary.py

Principle 5 — Invitation Tokens Are Stored as Hashes for Lookup
Invitation creation stores `token_hash` (SHA256 hex digest). Token lookup queries by `token_hash`, not by raw token. The raw token is returned to the inviter exactly once and never stored in the database.

Evidence:
- backend/app/auth_usermanagement/services/invitation_service.py
- backend/app/auth_usermanagement/models/invitation.py

Principle 6 — Refresh Tokens Never Touch JavaScript
Refresh tokens are stored server-side in the `refresh_tokens` table and referenced by an opaque cookie key. The browser holds only the opaque key in an HttpOnly/Secure/SameSite=Strict cookie. The refresh endpoint requires double-submit CSRF token validation (X-CSRF-Token header must match CSRF cookie value).

```python
# Token flow:
# 1. Browser sends HttpOnly cookie (opaque key) automatically
# 2. Frontend sends X-CSRF-Token header (read from non-HttpOnly CSRF cookie)
# 3. Backend resolves opaque key → actual Cognito refresh token
# 4. Backend calls Cognito /oauth2/token
# 5. Backend returns new access_token to frontend
```

Evidence:
- backend/app/auth_usermanagement/services/cookie_token_service.py
- backend/app/auth_usermanagement/api/refresh_token_routes.py

Principle 7 — Session Lifecycle Is First-Class
Session register, rotate, list, revoke-one, and revoke-all are API-level operations. Session refresh tokens are hashed (SHA256) before storage — never stored in plaintext.

Evidence:
- backend/app/auth_usermanagement/services/session_service.py
- backend/app/auth_usermanagement/api/session_routes.py
- backend/app/auth_usermanagement/models/session.py

Principle 8 — Audit Logging Must Not Block Auth Flows
Audit writes are best-effort. Failure to persist audit rows must not fail core auth operations. The logging path (structured console log) always executes. DB persistence is attempted when a `db` session is passed and silently continues on failure.

```python
# Correct pattern in every service:
try:
    log_audit_event("tenant_created", actor_user_id=user.id, db=db, tenant_name=name)
except Exception:
    pass  # best-effort — auth flow must not fail
```

Evidence:
- backend/app/auth_usermanagement/services/audit_service.py

Principle 9 — Role Hierarchy Is Explicit and Monotonic
`owner (4) > admin (3) > member (2) > viewer (1)`. Guards enforce minimum role level. Platform admin bypasses all tenant role checks explicitly. Role updates must include hierarchy checks — admins cannot escalate to owner/admin.

```python
ROLE_LEVELS = {"owner": 4, "admin": 3, "member": 2, "viewer": 1}

# Guard example:
def require_min_role(min_role):
    if ctx.is_platform_admin: return ctx          # explicit bypass
    if ROLE_LEVELS[ctx.role] >= ROLE_LEVELS[min_role]: return ctx
    raise HTTPException(403)
```

Evidence:
- backend/app/auth_usermanagement/security/guards.py

Principle 10 — UTC Datetimes Everywhere
Every datetime stored or compared is UTC. Auth services use UTC helper functions and store naive UTC timestamps for SQLite compatibility. No exceptions.

Evidence:
- backend/app/auth_usermanagement/services/session_service.py
- backend/app/auth_usermanagement/services/invitation_service.py
- backend/app/auth_usermanagement/services/audit_service.py

Principle 11 — RLS Validation Is PostgreSQL-Gated
RLS tests run only when `RUN_POSTGRES_RLS_TESTS=1` and `DATABASE_URL` points to PostgreSQL. The test fixture verifies the DB role is NOT superuser (superuser bypasses RLS). SQLite-only test runs are insufficient for sign-off on tenant isolation changes.

Evidence:
- backend/tests/test_row_level_security.py

Principle 12 — Rate Limiting Supports Distributed and Local Modes
Middleware uses a pluggable limiter interface. PostgreSQL-backed limiter when DB factory is provided (multi-process safe); in-memory deque fallback otherwise (single-process only). Rate limit key is `"{client_ip}:{request_path}"`.

Evidence:
- backend/app/auth_usermanagement/security/rate_limit_middleware.py
- backend/app/auth_usermanagement/services/rate_limiter_service.py

---

## 2. Recorded Decisions

RULE: Explicit decisions that have been made and locked. Must not be re-decided during implementation. If circumstances change, update this section and version the document.

Decision 1 — Auth Prefix Is Configurable
`AUTH_API_PREFIX` environment variable controls where all auth routes are mounted. Default is `/auth`. Changing this value at startup rebinds all routes — no code changes required. Middleware route matching uses the same prefix.

Evidence:
- backend/app/auth_usermanagement/config.py
- backend/app/main.py
- backend/tests/test_main_auth_prefix.py

Decision 2 — Invitation TTL Default Is 2 Days
`create_invitation` default `expires_in_days=2`. Creating a new invitation for the same email+tenant automatically revokes the previous pending invitation (only one active invitation per email+tenant pair).

Evidence:
- backend/app/auth_usermanagement/services/invitation_service.py

Decision 3 — Session List Endpoint Exists for Device Visibility
GET /auth/sessions returns sessions with `is_current` and `is_revoked` metadata. The `X-Current-Session-ID` header is compared against each session to set the `is_current` flag. This powers the "manage active devices" UI.

Evidence:
- backend/app/auth_usermanagement/api/session_routes.py
- frontend/src/auth_usermanagement/components/SessionPanel.jsx

Decision 4 — CORS Origins Are Environment Configured in Host Config
`CORS_ALLOWED_ORIGINS` is a comma-separated string in host config. `main.py` reads host settings — no hardcoded origins.

Evidence:
- backend/app/config.py
- backend/app/main.py

Decision 5 — SES Invitation Sending Is Optional/Config-Driven
If `SES_REGION` or `SES_SENDER_EMAIL` is missing, invitation creation continues and the email is marked as unsent in the response. The invitation token is still returned to the caller for manual delivery. This is a deliberate choice — invitation creation should never fail due to email infrastructure.

Evidence:
- backend/app/auth_usermanagement/services/email_service.py
- backend/app/auth_usermanagement/api/route_helpers.py

Decision 6 — Permission Demo Endpoints Are Included in Router
Demonstration endpoints (`/admin/settings`, `/owner/danger-zone`, `/member/dashboard`, `/viewer/reports`, `/permissions/check`) are active under the auth prefix. These are integration test aids and should be removed or gated before production deployment.

Evidence:
- backend/app/auth_usermanagement/api/permission_demo_routes.py

Decision 7 — Privileged Operations
The auth module enforces authorization internally. The following operations have elevated permission requirements:

| Privileged Operation | Why It Is Privileged | Required Role |
|---------------------|---------------------|---------------|
| `suspend_user()` | Blocks all auth flows for target | Platform admin only |
| `promote_to_platform_admin()` | Grants god-mode access | Platform admin only |
| `demote_from_platform_admin()` | Removes god-mode access | Platform admin only (cannot self-demote) |
| `suspend_tenant()` | Blocks all tenant operations | Platform admin only |
| `update_user_role()` to owner/admin | Escalates tenant privileges | Owner only (admins blocked) |
| `remove_user_from_tenant()` (last owner) | Would orphan tenant | Blocked for all roles |

Decision 8 — Self-Action Prevention
Platform admins cannot suspend themselves, demote themselves, or be the last admin demoted. This prevents accidental lockout. Enforced at the API handler level.

Evidence:
- backend/app/auth_usermanagement/api/platform_user_routes.py
- backend/tests/test_user_suspension_api.py

Decision 9 — Invitation Role Accepts Never Downgrade
When accepting an invitation, if the user already has a membership with a higher role (e.g., owner) and the invitation has a lower role (e.g., member), the existing higher role is preserved. The membership is reactivated but never downgraded.

```python
# In accept_invitation:
if existing_membership:
    if ROLE_LEVELS[existing.role] >= ROLE_LEVELS[invitation.role]:
        existing.status = "active"  # reactivate, keep higher role
    else:
        existing.role = invitation.role  # upgrade
        existing.status = "active"
```

Evidence:
- backend/app/auth_usermanagement/services/invitation_service.py
- backend/tests/test_invitation_service.py

Decision 10 — Cognito User Sync Handles User Recreation
When a Cognito user is deleted and recreated (new `cognito_sub`), `sync_user_from_cognito` falls back to email-based lookup and re-links the user record. This prevents orphaned accounts.

Evidence:
- backend/app/auth_usermanagement/services/user_service.py

---

## 3. Core Abstractions

### 3.1 TenantContext

Data contract (runtime object):

```python
@dataclass
class TenantContext:
    user_id: UUID
    tenant_id: UUID
    role: str | None      # "owner" | "admin" | "member" | "viewer" | None (platform admin)
    is_platform_admin: bool

    def can_access_tenant(self) -> bool   # is_platform_admin OR role is not None
    def is_owner(self) -> bool
    def is_admin_or_owner(self) -> bool
```

Evidence:
- backend/app/auth_usermanagement/security/tenant_context.py
- backend/app/auth_usermanagement/security/dependencies.py

### 3.2 Role Guard Abstractions

| Guard | Usage | Allows |
|-------|-------|--------|
| `require_role(*roles)` | `Depends(require_role("owner", "admin"))` | User with one of specified roles OR platform admin |
| `require_min_role(min_role)` | `Depends(require_min_role("admin"))` | User at minimum role level OR platform admin |
| `require_owner` | `Depends(require_owner)` | Owner only OR platform admin |
| `require_admin` | `Depends(require_admin)` | Admin or owner OR platform admin |
| `require_member` | `Depends(require_member)` | Member, admin, or owner OR platform admin |
| `require_viewer` | `Depends(require_viewer)` | Any tenant member OR platform admin |
| `check_permission(ctx, perm)` | Runtime check | Role-based permission map |

Permission Matrix:
```
owner:   tenant:delete, tenant:edit, users:manage, users:invite, settings:edit, data:read, data:write
admin:   tenant:edit, users:manage, users:invite, settings:edit, data:read, data:write
member:  data:read, data:write, settings:read
viewer:  data:read, settings:read
```

Evidence:
- backend/app/auth_usermanagement/security/guards.py

### 3.3 Dependency Injection Chain

```
HTTP Request
  │
  ├─ get_current_user (dependency)
  │    ├─ Extract Authorization: Bearer <token>
  │    ├─ verify_token() → validate JWT signature, issuer, audience, expiry, token_use
  │    ├─ get_user_by_cognito_sub() → load User from DB
  │    └─ Check is_active → raise 401 if suspended
  │
  ├─ get_current_user_optional (dependency)
  │    └─ Same as above but returns None if missing/invalid
  │
  └─ get_tenant_context (dependency)
       ├─ Requires get_current_user
       ├─ Read X-Tenant-ID header → validate UUID format
       ├─ Query Membership for user+tenant+active status
       ├─ SET PostgreSQL session variables:
       │    SET app.current_tenant_id = :tenant_id
       │    SET app.is_platform_admin = 'true' | 'false'
       └─ Return TenantContext(user_id, tenant_id, role, is_platform_admin)
```

Error Responses:
| Condition | Status | Detail |
|-----------|--------|--------|
| Missing Authorization header | 401 | Unauthorized |
| Invalid/expired JWT | 401 | Unauthorized |
| User suspended (`is_active=False`) | 401 | Unauthorized |
| User not found in local DB | 404 | Not Found |
| Missing X-Tenant-ID header | 400 | Bad Request |
| Invalid X-Tenant-ID UUID | 400 | Bad Request |
| No active membership (non-admin) | 403 | Access denied |

Evidence:
- backend/app/auth_usermanagement/security/dependencies.py

### 3.4 Session Lifecycle Abstractions

Service operations:

| Operation | Signature | Returns | Notes |
|-----------|-----------|---------|-------|
| `create_user_session` | `(db, user_id, refresh_token, user_agent?, ip_address?, device_info?, expires_at?)` | Session | Hashes token (SHA256) |
| `validate_refresh_session` | `(db, user_id, session_id, refresh_token)` | Session \| None | Returns None if revoked/expired/hash mismatch |
| `rotate_user_session` | `(db, user_id, session_id, old_token, new_token, ...)` | Session \| None | Revokes old, creates replacement |
| `list_user_sessions` | `(db, user_id, include_revoked=False, limit=50)` | list[Session] | Newest first |
| `revoke_user_session` | `(db, user_id, session_id)` | Session \| None | Sets revoked_at |
| `revoke_all_user_sessions` | `(db, user_id, except_session_id?)` | int | Returns count revoked |

Evidence:
- backend/app/auth_usermanagement/services/session_service.py

### 3.5 Cookie Refresh Token Abstractions

Service operations:

| Operation | Signature | Returns | Purpose |
|-----------|-----------|---------|---------|
| `store_refresh_token` | `(db, refresh_token)` | opaque cookie_key | Server-side storage |
| `get_refresh_token` | `(db, cookie_key)` | refresh_token \| None | Resolve key → token |
| `rotate_refresh_token` | `(db, cookie_key, new_token)` | new_key | Rotate & return new key |
| `revoke_refresh_token` | `(db, cookie_key)` | None | Delete from store |
| `set_refresh_cookie` | `(response, cookie_key, ...)` | None | HttpOnly/Secure/SameSite=Strict |
| `clear_refresh_cookie` | `(response, ...)` | None | max_age=0 |
| `generate_csrf_token` | `()` | token (64 chars) | Cryptographic random |
| `set_csrf_cookie` | `(response, csrf_token, ...)` | None | Non-HttpOnly (JS readable) |
| `clear_csrf_cookie` | `(response, ...)` | None | max_age=0 |
| `call_cognito_refresh` | `(refresh_token, cognito_domain, client_id)` | dict | POST to Cognito /oauth2/token |

Cookie Settings:
| Property | Value |
|----------|-------|
| Cookie Name | `{namespace}_refresh_token` (default: `authum_refresh_token`) |
| Cookie Path | `/auth/token` |
| Max-Age | 30 days (2,592,000 seconds) |
| HttpOnly | true |
| Secure | true (production) |
| SameSite | Strict |

Evidence:
- backend/app/auth_usermanagement/services/cookie_token_service.py

### 3.6 Audit Event Abstraction

Single logging entrypoint:
```python
log_audit_event(
    event: str,           # e.g. "tenant_created", "user_suspended"
    actor_user_id: UUID = None,
    db: Session = None,   # when provided, attempts DB persistence
    **details             # tenant_id, target_type, target_id, ip_address, etc.
)
```

Events Currently Logged:
| Category | Events |
|----------|--------|
| Tenant | `tenant_created`, `tenant_suspended`, `tenant_unsuspended` |
| User | `user_suspended`, `user_unsuspended`, `user_promoted_to_platform_admin`, `user_demoted_from_platform_admin` |
| Invitation | `invitation_created`, `invitation_accepted`, `invitation_revoked` |
| Session | `session_registered`, `session_rotated`, `session_revoked`, `all_sessions_revoked` |
| Cookie | `refresh_cookie_stored` |
| User Mgmt | `tenant_user_role_updated`, `tenant_user_removed` |

Evidence:
- backend/app/auth_usermanagement/services/audit_service.py
- backend/app/auth_usermanagement/models/audit_event.py

### 3.7 JWT Verification

```python
verify_token(token: str, allowed_token_uses=("access",)) → TokenPayload
```

Validation chain (all must pass):
1. Token header contains `kid` (key ID)
2. `kid` found in Cognito JWKS (cached via LRU)
3. RS256 signature valid against Cognito public key
4. Issuer matches `https://cognito-idp.{region}.amazonaws.com/{user_pool_id}`
5. `token_use` in allowed list (`access` or `id`)
6. `aud` / `client_id` matches configured app client
7. `exp` claim not in the past

Any failure raises `InvalidTokenError` → 401 response.

Evidence:
- backend/app/auth_usermanagement/security/jwt_verifier.py

---

## 4. API Surface (Auth Prefix)

### 4.1 Auth Core

| Method | Path | Auth | Request | Response | Notes |
|--------|------|------|---------|----------|-------|
| GET | `/debug-token` | Bearer token | — | Token claims | Phase 1 test endpoint; no DB access |
| POST | `/sync` | Bearer token | — | `{user_id, email, name, cognito_sub, is_platform_admin, message}` | Idempotent user sync from Cognito |
| GET | `/me` | `get_current_user` | — | User profile | Current user info |

Source: backend/app/auth_usermanagement/api/auth_routes.py

### 4.2 Tenant Endpoints

| Method | Path | Auth | Request | Response | Notes |
|--------|------|------|---------|----------|-------|
| POST | `/tenants` | `get_current_user` | `{name, plan?}` | `{tenant_id, name, plan, role="owner", message}` | Creator becomes owner |
| GET | `/tenants/my` | `get_current_user` | — | `[{id, name, plan, status, role, created_at}]` | User's tenants |
| GET | `/tenant-context` | `get_tenant_context` | — | `{user_id, tenant_id, role, is_platform_admin, is_owner, is_admin_or_owner}` | Debug endpoint |

Source: backend/app/auth_usermanagement/api/tenant_routes.py

### 4.3 Invitation Endpoints

| Method | Path | Auth | Request | Response | Notes |
|--------|------|------|---------|----------|-------|
| POST | `/invite` | `require_admin` + X-Tenant-ID | `{email, role?="member"}` | `{invitation_id, tenant_id, email, role, token, expires_at, status, email_sent}` | Uses tenant from context |
| POST | `/tenants/{tenant_id}/invite` | `require_admin` | `{email, role?="member"}` | Same as above | Explicit tenant path |
| GET | `/invites/{token}` | None (public) | — | `{token, tenant_id, tenant_name, email, role, expires_at, status, is_expired, is_accepted}` | Public preview |
| DELETE | `/tenants/{tenant_id}/invites/{token}` | `require_admin` | — | `{invitation_id, tenant_id, status="revoked"}` | Revoke pending |
| POST | `/invites/accept` | `get_current_user` | `{token}` | `{tenant_id, role, message}` | Accept & create membership |

Source: backend/app/auth_usermanagement/api/invitation_routes.py

### 4.4 Tenant User Management

| Method | Path | Auth | Request | Response | Notes |
|--------|------|------|---------|----------|-------|
| GET | `/tenants/{tenant_id}/users` | `require_member` | — | `[{user_id, email, name, role, status, is_active, joined_at}]` | Active members |
| PATCH | `/tenants/{tenant_id}/users/{user_id}/role` | `require_admin` | `{role}` | `{user_id, tenant_id, role, message}` | Admins cannot assign owner/admin |
| DELETE | `/tenants/{tenant_id}/users/{user_id}` | `require_admin` | — | `{user_id, tenant_id, status="removed"}` | Soft-delete; blocks last owner |

Source: backend/app/auth_usermanagement/api/tenant_user_routes.py

### 4.5 Session Endpoints

| Method | Path | Auth | Request | Response | Notes |
|--------|------|------|---------|----------|-------|
| GET | `/sessions` | `get_current_user` | `include_revoked?`, `limit?` | `[{session_id, user_agent, ip_address, device_info, created_at, expires_at, is_current, is_revoked}]` | X-Current-Session-ID for comparison |
| POST | `/sessions/register` | `get_current_user` | `{refresh_token, user_agent?, ip_address?, device_info?, expires_at?}` | `{session_id, user_id}` | Creates session |
| POST | `/sessions/{session_id}/rotate` | `get_current_user` | `{old_refresh_token, new_refresh_token, ...}` | `{session_id, user_id}` | Rotates token |
| DELETE | `/sessions/{session_id}` | `get_current_user` | — | `{session_id, user_id, revoked_at}` | Revoke one |
| DELETE | `/sessions/all` | `get_current_user` | `X-Current-Session-ID?` | `{user_id, revoked_count, kept_session_id}` | Revoke all except current |

Source: backend/app/auth_usermanagement/api/session_routes.py

### 4.6 Platform Admin Endpoints

| Method | Path | Auth | Request | Response | Notes |
|--------|------|------|---------|----------|-------|
| GET | `/platform/users` | Platform admin | — | `[{user_id, email, is_platform_admin, is_active, suspended_at, memberships[]}]` | All users |
| PATCH | `/users/{user_id}/suspend` | Platform admin | — | `{user_id, is_active=false, suspended_at}` | Cannot self-suspend |
| PATCH | `/users/{user_id}/unsuspend` | Platform admin | — | `{user_id, is_active=true, suspended_at=null}` | — |
| PATCH | `/platform/users/{user_id}/promote` | Platform admin | — | `{user_id, is_platform_admin=true}` | Grants platform admin |
| PATCH | `/platform/users/{user_id}/demote` | Platform admin | — | `{user_id, is_platform_admin=false}` | Cannot self-demote; prevents last admin |
| GET | `/platform/tenants` | Platform admin | — | `[{tenant_id, name, plan, status, member_count, owner_count}]` | All tenants |
| PATCH | `/platform/tenants/{tenant_id}/suspend` | Platform admin | — | `{tenant_id, status="suspended"}` | — |
| PATCH | `/platform/tenants/{tenant_id}/unsuspend` | Platform admin | — | `{tenant_id, status="active"}` | — |

Source:
- backend/app/auth_usermanagement/api/platform_user_routes.py
- backend/app/auth_usermanagement/api/platform_tenant_routes.py

### 4.7 Cookie + Refresh Endpoints

| Method | Path | Auth | Request | Response | Notes |
|--------|------|------|---------|----------|-------|
| POST | `/cookie/store-refresh` | `get_current_user` | `{refresh_token}` | `{message}` | Sets HttpOnly + CSRF cookies |
| POST | `/token/refresh` | Cookie + CSRF | Cookie-based | `{access_token, id_token?, expires_in}` | X-CSRF-Token + X-Requested-With headers required |
| POST | `/cookie/clear-refresh` | None | Cookie-based | `{message}` | Clears both refresh & CSRF cookies |

Source: backend/app/auth_usermanagement/api/refresh_token_routes.py

### 4.8 Permission Demo Endpoints

| Method | Path | Guard | Purpose |
|--------|------|-------|---------|
| GET | `/admin/settings` | `require_admin` | Admin-only demo |
| GET | `/owner/danger-zone` | `require_owner` | Owner-only demo |
| GET | `/member/dashboard` | `require_member` | Member access demo |
| GET | `/viewer/reports` | `require_viewer` | Viewer access demo |
| GET | `/permissions/check` | `get_tenant_context` | Check all permissions for current user |

Source: backend/app/auth_usermanagement/api/permission_demo_routes.py

---

## 5. Database Schema Contract

### 5.1 users

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK, default=uuid4 | |
| cognito_sub | String(255) | UNIQUE, indexed | Cognito user pool subject |
| email | String(255) | UNIQUE, indexed | Normalized to lowercase |
| name | String(255) | nullable | Display name |
| is_platform_admin | Boolean | default=False | God-mode flag |
| is_active | Boolean | NOT NULL, default=True | False = suspended |
| suspended_at | DateTime | nullable | UTC timestamp of suspension |
| created_at | DateTime | NOT NULL, default=utcnow | |
| updated_at | DateTime | NOT NULL, onupdate=utcnow | |

Relationships: `memberships` (1:N cascade), `sessions` (1:N cascade), `created_invitations` (1:N set null)

### 5.2 tenants

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK, default=uuid4 | |
| name | String(255) | NOT NULL | |
| plan | String(50) | default="free" | `free` \| `pro` \| `enterprise` |
| status | String(20) | default="active" | `active` \| `suspended` |
| created_at | DateTime | NOT NULL, default=utcnow | |
| updated_at | DateTime | NOT NULL, onupdate=utcnow | |

Relationships: `memberships` (1:N cascade), `invitations` (1:N cascade)

### 5.3 memberships

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK, default=uuid4 | |
| user_id | UUID | FK→users.id, indexed, CASCADE | |
| tenant_id | UUID | FK→tenants.id, indexed, CASCADE | |
| role | String(20) | NOT NULL | `owner` \| `admin` \| `member` \| `viewer` |
| status | String(20) | default="active" | `active` \| `removed` \| `suspended` |
| created_at | DateTime | NOT NULL, default=utcnow | |

UNIQUE(user_id, tenant_id) — one membership per user per tenant.
RLS ENABLED: `memberships_tenant_isolation` policy filters by `app.current_tenant_id` session variable. FORCE ROW LEVEL SECURITY enabled.

### 5.4 invitations

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK, default=uuid4 | |
| tenant_id | UUID | FK→tenants.id, indexed, CASCADE | |
| email | String(255) | indexed, NOT NULL | Normalized lowercase |
| role | String(20) | NOT NULL | `admin` \| `member` \| `viewer` |
| token | String(255) | UNIQUE, indexed, NOT NULL | Raw token (returned once to inviter) |
| token_hash | String(64) | indexed, nullable | SHA256 hex digest for lookup |
| expires_at | DateTime | NOT NULL | |
| accepted_at | DateTime | nullable | Terminal state |
| revoked_at | DateTime | nullable | Terminal state |
| created_by | UUID | FK→users.id, SET NULL | |
| created_at | DateTime | NOT NULL, default=utcnow | |

Computed properties: `is_expired`, `is_accepted`, `is_revoked`, `status` ("revoked" | "accepted" | "expired" | "pending")
RLS ENABLED: `invitations_tenant_isolation` policy. FORCE ROW LEVEL SECURITY enabled.

### 5.5 sessions

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK, default=uuid4 | |
| user_id | UUID | FK→users.id, indexed, CASCADE | |
| refresh_token_hash | String(255) | NOT NULL | SHA256 hash — never plaintext |
| user_agent | String(512) | nullable | Browser/device UA string |
| ip_address | String(64) | nullable | Client IP |
| device_info | String(255) | nullable | Human-readable device label |
| expires_at | DateTime | nullable | Session TTL |
| created_at | DateTime | NOT NULL, default=utc_now | |
| revoked_at | DateTime | nullable | Set on revocation |

Methods: `is_revoked` (@property), `revoke()` (sets `revoked_at`)

### 5.6 refresh_tokens

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| cookie_key | String(255) | PK | Opaque key stored in browser cookie |
| refresh_token | Text | NOT NULL | Actual Cognito refresh token |
| expires_at | DateTime | indexed, NOT NULL | 30-day default |
| created_at | DateTime | NOT NULL, default=utc_now | |

Purpose: Server-side mapping between opaque HttpOnly cookie key and Cognito refresh token. Keeps refresh token out of JavaScript memory.

### 5.7 rate_limit_hits

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK, default=uuid4 | |
| key | String(255) | indexed | `"{ip}:{path}"` format |
| hit_at | DateTime | indexed, NOT NULL | |

### 5.8 audit_events

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| id | UUID | PK, default=uuid4 | |
| timestamp | DateTime | indexed, NOT NULL | UTC |
| actor_user_id | UUID | indexed, nullable | Who triggered the action |
| tenant_id | UUID | indexed, nullable | Tenant scope (if applicable) |
| action | String(100) | indexed, NOT NULL | e.g. `tenant_created`, `user_suspended` |
| target_type | String(100) | nullable | e.g. `user`, `tenant`, `invitation` |
| target_id | String(255) | nullable | Target entity ID |
| ip_address | String(64) | nullable | Request IP |
| metadata_json | JSON | NOT NULL, default={} | Flexible event-specific payload |

### 5.9 Migration Timeline

| Order | Revision | Migration | Changes |
|-------|----------|-----------|---------|
| 1 | d3494139f54d | `create_auth_tables` | Creates users, tenants, invitations, memberships, sessions |
| 2 | 7a454a9250b1 | `add_user_suspension_fields` | Adds `is_active`, `suspended_at` to users |
| 3 | 0eec64567dac | `enable_row_level_security` | Enables RLS on invitations, memberships; creates policies |
| 4 | 8c5f69f3b5d1 | `add_session_metadata_fields` | Adds `user_agent`, `ip_address`, `device_info`, `expires_at` to sessions |
| 5 | f1c2d3e4a5b6 | `add_refresh_token_store_table` | Creates `refresh_tokens` table |
| 6 | 2a9b67c1d3ef | `add_invitation_revoked_at` | Adds `revoked_at` to invitations |
| 7 | 4f2a1e9c7b10 | `force_rls_on_tenant_tables` | Executes `ALTER TABLE FORCE ROW LEVEL SECURITY` |
| 8 | 5b3c4d2e8f9a | `add_rate_limit_hits_table` | Creates `rate_limit_hits` table |
| 9 | 6c5d7e4f8a2b | `add_token_hash_to_invitations` | Adds `token_hash` (String 64) + index to invitations |
| 10 | 9f2e1c7a4b3d | `add_audit_events_table` | Creates `audit_events` table with indexes |

Model sources: backend/app/auth_usermanagement/models/*.py
Migration sources: backend/alembic/versions/*.py

---

## 6. State Machine Definitions

### 6.1 Invitation State Machine

```
                  ┌─────────────────────────────────────┐
                  │                                     │
  [create]──►  PENDING  ──[accept]──►  ACCEPTED (terminal)
                  │
                  ├──[revoke]──►  REVOKED (terminal)
                  │
                  ├──[expire (time)]──►  EXPIRED (terminal)
                  │
                  └──[new invite same email+tenant]──►  REVOKED (auto)
```

State Guards:
- `accept` requires: `status == "pending"` AND `not is_expired` AND `email matches user.email` AND `not is_revoked`
- `revoke` requires: `accepted_at IS NULL` AND `revoked_at IS NULL`
- Creating a new invitation for the same email+tenant auto-revokes the previous pending one

### 6.2 Session State Machine

```
  [register]──►  ACTIVE  ──[revoke]──►  REVOKED (terminal)
                    │
                    ├──[rotate]──►  REVOKED (old) + ACTIVE (new)
                    │
                    └──[expire (time)]──►  EXPIRED (terminal)
```

State Guards:
- `validate` requires: `revoked_at IS NULL` AND `expires_at > now()` AND `hash matches`
- `rotate` requires: `validate` passes on old token → revoke old + create new
- Rotate failure (bad old token) returns None — no side effects

### 6.3 User State Machine

```
  [sync/create]──►  ACTIVE (is_active=True)
                        │
                        ├──[suspend]──►  SUSPENDED (is_active=False, suspended_at=now)
                        │                    │
                        │                    └──[unsuspend]──►  ACTIVE (is_active=True, suspended_at=None)
                        │
                        ├──[promote]──►  PLATFORM_ADMIN (is_platform_admin=True)
                        │                    │
                        │                    └──[demote]──►  ACTIVE (is_platform_admin=False)
                        │
                        └──  ACTIVE (stable)
```

Idempotency: Suspending an already-suspended user updates `suspended_at` but is otherwise a no-op. Unsuspending an active user is a no-op.

### 6.4 Tenant State Machine

```
  [create]──►  ACTIVE (status="active")  ◄──[unsuspend]──  SUSPENDED (status="suspended")
                    │                                           ▲
                    └──────────[suspend]────────────────────────┘
```

### 6.5 Membership State Machine

```
  [invitation accepted / tenant created]──►  ACTIVE (status="active")
                                                │
                                                ├──[remove]──►  REMOVED (status="removed") ◄─── soft delete
                                                │                    │
                                                │                    └──[re-invite + accept]──►  ACTIVE
                                                │
                                                └──  ACTIVE (stable)
```

Role Update Guards:
- Admins can only assign `member` or `viewer` roles
- Admins cannot modify users with `owner` or `admin` roles
- Owners can assign any role
- Cannot remove last owner of a tenant

---

## 7. Cognito Integration & External Call Boundaries

### 7.1 Outbound Cognito Calls

The system makes exactly two types of outbound Cognito calls:

| Call | Where | Trigger | Failure Mode |
|------|-------|---------|-------------|
| JWKS fetch | `jwt_verifier.py` | Every token verification (LRU cached) | `InvalidTokenError` → 401 |
| Token refresh | `cookie_token_service.py` | POST /auth/token/refresh | `ValueError` → 401 |

### 7.2 Cognito-Succeeds / DB-Fails Window

**Scenario:** User authenticates with Cognito, frontend calls `POST /auth/sync`, but the DB write fails.

Current handling: `sync_user_from_cognito` is called on every `POST /auth/sync`. If the DB write fails, the next sync call will retry the same idempotent operation. The user remains unauthenticated locally until sync succeeds. There is no compensation mechanism — the Cognito user exists but the local user row does not.

**Impact:** User sees "authenticated with Cognito but cannot access app features" until the next successful sync. This is acceptable for V1 because sync is called on every login flow.

### 7.3 Token Refresh Flow (External I/O Boundary)

```python
# Step 1 — Resolve cookie to token (DB read)
refresh_token = get_refresh_token(db, cookie_key)

# Step 2 — Call Cognito (EXTERNAL — outside any DB transaction)
cognito_response = call_cognito_refresh(refresh_token, domain, client_id)

# Step 3 — Rotate cookie if new refresh token returned (DB write)
if cognito_response.get("refresh_token"):
    new_key = rotate_refresh_token(db, cookie_key, new_refresh_token)
    set_refresh_cookie(response, new_key)
```

Note: The Cognito call (Step 2) happens outside of any DB transaction. If Step 3 fails after Cognito returns a new refresh token, the old cookie key becomes invalid but the old Cognito refresh token may still work on the next attempt.

---

## 8. Security Control Matrix

| # | Control | Enforced In | Validation |
|---|---------|-------------|------------|
| 1 | JWT signature + claim validation (RS256, issuer, audience, expiry, token_use) | security/jwt_verifier.py | JWKS cached; 7-step validation chain |
| 2 | Authenticated user resolution + suspension block | security/dependencies.py | `is_active=False` → 401 |
| 3 | Tenant header precheck (UUID format + auth header presence) | security/tenant_middleware.py | Header-only; no DB access |
| 4 | Tenant membership validation + RLS session variables | security/dependencies.py | Active membership required; sets PostgreSQL `app.current_tenant_id` |
| 5 | Role-based authorization with explicit hierarchy | security/guards.py | `ROLE_LEVELS` dict; platform admin bypass |
| 6 | CSRF double-submit on refresh endpoint | api/refresh_token_routes.py | X-CSRF-Token header must match CSRF cookie value |
| 7 | HttpOnly refresh cookie + Strict SameSite | services/cookie_token_service.py | JavaScript cannot read refresh token |
| 8 | Invitation token hashed for storage (SHA256) | services/invitation_service.py | Raw token returned once; lookup by hash |
| 9 | Distributed-safe rate limiting (pluggable) | security/rate_limit_middleware.py | PostgreSQL or in-memory backend |
| 10 | Secure response headers (CSP, CORP, COOP, X-Frame-Options, etc.) | security/security_headers_middleware.py | Applied to every response |
| 11 | Audit event logging (best-effort) | services/audit_service.py | Console log always; DB persistence optional |
| 12 | Row-Level Security (PostgreSQL) | Alembic migrations + RLS policies | `app.current_tenant_id` session variable; FORCE RLS enabled |
| 13 | Refresh token hashed in session store (SHA256) | services/session_service.py | Never stored plaintext |
| 14 | Static analysis guardrails on module DB ownership | tests/test_db_runtime_guardrails.py | Glob + regex scan for forbidden patterns |

### 8.1 Secure Response Headers

| Header | Value |
|--------|-------|
| X-Content-Type-Options | `nosniff` |
| X-Frame-Options | `DENY` |
| Referrer-Policy | `strict-origin-when-cross-origin` |
| Permissions-Policy | `camera=(), microphone=(), geolocation=()` |
| Content-Security-Policy | `default-src 'self'; object-src 'none'; ...` |
| Cross-Origin-Resource-Policy | `same-origin` |
| Cross-Origin-Opener-Policy | `same-origin` |

---

## 9. Idempotency Contract

| Operation | Idempotency Key | Scope | Behavior on Duplicate |
|-----------|----------------|-------|----------------------|
| `sync_user_from_cognito` | `cognito_sub` (or email fallback) | UNIQUE on users table | Updates existing user; re-links cognito_sub |
| `create_invitation` | `(email, tenant_id)` | One active per pair | Auto-revokes previous pending invitation |
| `accept_invitation` | `accepted_at IS NOT NULL` | Per invitation | Returns error if already accepted |
| `store_refresh_token` | `cookie_key` (UUID) | PK on refresh_tokens | New key per call — not idempotent (by design) |
| `create_user_session` | None | Per call | Creates new session every time (by design) |
| `rotate_user_session` | Old session validation | Per session | Revokes old + creates new; returns None if old already revoked |
| `revoke_user_session` | `revoked_at IS NOT NULL` | Per session | Already-revoked session is a no-op |
| `suspend_user` / `unsuspend_user` | `is_active` flag | Per user | Idempotent — suspending suspended user updates timestamp only |
| `create_tenant` | None | Per call | Creates new tenant every time (by design) |

---

## 10. Request Lifecycle (Full Path)

```
1) Request enters FastAPI app

2) Middleware stack executes (reverse registration order — last added runs first):
   ┌─ SecurityHeadersMiddleware
   │   └─ Adds X-Content-Type-Options, X-Frame-Options, CSP, CORP, COOP headers
   ├─ RateLimitMiddleware
   │   └─ Checks "{ip}:{path}" against limiter
   │   └─ Returns 429 + Retry-After if exceeded (30 req/60s default)
   │   └─ Protected paths: /auth/debug-token, /auth/sync, /auth/invite,
   │      /auth/invites/accept, /auth/token/refresh, /auth/cookie/store-refresh
   ├─ TenantContextMiddleware
   │   └─ Skips: /health, /auth/sync, /auth/me, /auth/tenants, /auth/sessions/*,
   │      /auth/cookie/*, /auth/token/refresh, /auth/platform/*, /auth/invites/*
   │   └─ Validates: X-Tenant-ID header (UUID format) + Authorization header present
   │   └─ Stores: request.state.requested_tenant_id
   └─ CORSMiddleware
       └─ Allows: origins from CORS_ALLOWED_ORIGINS

3) Endpoint dependency chain resolves:
   get_db() → yield DB session from host SessionLocal
   get_current_user() → verify JWT → load user → check not suspended
   get_tenant_context() → validate membership → set RLS session variables

4) Role guard dependency validates role/permission level

5) Handler executes service logic with request-scoped DB session

6) Audit events emitted:
   └─ Always: structured console log with full event payload
   └─ When db passed: best-effort INSERT into audit_events table
```

---

## 11. Token Lifecycle Matrix

| Token Type | Storage | Lifespan | Rotation | Security Properties |
|-----------|---------|----------|----------|---------------------|
| Access Token (JWT) | In-memory (JS variable) | ~1 hour (Cognito default) | Auto-refresh 5 min before expiry | Sent in `Authorization: Bearer` header; never persisted client-side |
| ID Token (JWT) | In-memory (JS variable) | ~1 hour | Refreshed alongside access token | Used for user profile claims; decoded client-side (no verification) |
| Refresh Token | Server-side DB (`refresh_tokens` table) | 30 days | Rotated when Cognito returns new one | Browser holds only opaque cookie key; actual token never in JS |
| CSRF Token | Non-HttpOnly cookie + header | Per login session | Regenerated on token store | JS-readable cookie; must be sent as X-CSRF-Token header on /token/refresh |
| Session ID | In-memory (JS variable) | Request-scoped | New ID on rotate | Links access token to active device session; UUID format |
| Invitation Token | Returned once to inviter | 2 days (default) | Not rotated | Stored as SHA256 hash in DB; raw token never stored |

---

## 12. Frontend Architecture Contract

### 12.1 Auth Provider

Bootstrap Flow:
```
1. Check for OAuth authorization code in URL
2. Exchange code for tokens via Cognito PKCE flow
3. Store refresh token in HttpOnly cookie (POST /auth/cookie/store-refresh)
4. Register session in backend (POST /auth/sessions/register)
5. Sync user from Cognito (POST /auth/sync)
6. Load current user profile (GET /auth/me)
7. Load user's tenants (GET /auth/tenants/my)
8. Auto-select first tenant if none selected
9. Set up token auto-refresh loop (check every 60s, refresh if <5 min to expiry)
```

Logout Flow:
```
1. Revoke all sessions (DELETE /auth/sessions/all)
2. Clear refresh cookie (POST /auth/cookie/clear-refresh)
3. Redirect to Cognito /logout endpoint
4. Clear local state (token, user, tenants, sessionId)
```

Context value:
```javascript
{
  token, idToken, user, tenants, tenantId, sessionId,
  authError, isLoading, isAuthenticated,
  loginWithToken(), logout(), changeTenant(), refreshAuthState()
}
```

Source: frontend/src/auth_usermanagement/context/AuthProvider.jsx

### 12.2 Frontend API Wrapper

All auth endpoints consumed via `authApi.js`. Every function that requires authentication takes `token` as the first parameter. Tenant-scoped functions include `tenantId`. The `X-Tenant-ID` header is set automatically for tenant-scoped requests.

API Function Groups:
| Group | Functions |
|-------|-----------|
| User/Auth | `syncUser`, `getCurrentUser`, `listMyTenants` |
| Tenant Users | `getTenantUsers`, `updateTenantUserRole`, `removeTenantUser`, `inviteTenantUser` |
| Platform Admin | `getPlatformUsers`, `promotePlatformUser`, `demotePlatformUser`, `suspendUser`, `unsuspendUser`, `getPlatformTenants`, `suspendPlatformTenant`, `unsuspendPlatformTenant` |
| Sessions | `registerSession`, `rotateSession`, `revokeSession`, `revokeAllSessions`, `listSessions` |
| Cookie Auth | `storeRefreshCookie`, `refreshAccessToken`, `clearRefreshCookie` |
| Invitations | `getInvitationDetails`, `acceptInvitation`, `createTenant` |

Source: frontend/src/auth_usermanagement/services/authApi.js

### 12.3 Cognito Integration Layer (PKCE)

| Function | Purpose |
|----------|---------|
| `getHostedLoginUrl()` | Generates Cognito authorize URL with PKCE code_challenge |
| `getHostedSignupUrl()` | Generates Cognito signup URL with PKCE code_challenge |
| `exchangeAuthCodeForTokens(code)` | Exchanges authorization code for token set |
| `refreshTokens(refreshToken)` | DEPRECATED — use backend cookie proxy |
| `decodeJwt(token)` | Client-side decode (no verification) |
| `logoutFromCognito()` | Redirects to Cognito logout endpoint |

Source: frontend/src/auth_usermanagement/services/cognitoClient.js

### 12.4 Hooks

| Hook | Returns | Purpose |
|------|---------|---------|
| `useAuth()` | `{token, user, tenants, tenantId, isAuthenticated, logout, changeTenant, ...}` | Full auth context |
| `useTenant()` | `{tenantId, tenant, tenants, changeTenant}` | Current tenant context |
| `useRole()` | `{role, can(minRole), isOwner, isAdminOrOwner}` | Role-based UI decisions |
| `useCurrentUser()` | `{user, isLoading, isPlatformAdmin}` | User profile data |

Source: frontend/src/auth_usermanagement/hooks/*.js

### 12.5 Admin Surface

Components:
- `AdminDashboard.jsx` — tab-based admin page (users, tenants, invitations, sessions)
- `UserManagementPanel.jsx` — tenant user list with role editing
- `PlatformTenantPanel.jsx` — platform-wide tenant management
- `InvitationModal.jsx` — invite new users to tenant
- `SessionPanel.jsx` — active device/session list with revoke actions

Source: frontend/src/auth_usermanagement/pages/ + components/

---

## 13. Configuration Contract

### 13.1 Backend Module Config

| Variable | Type | Default | Required | Notes |
|----------|------|---------|----------|-------|
| `COGNITO_REGION` | string | `eu-west-1` | Yes | AWS region for Cognito |
| `COGNITO_USER_POOL_ID` | string | — | Yes | Cognito user pool ID |
| `COGNITO_CLIENT_ID` | string | — | Yes | Cognito app client ID |
| `COGNITO_DOMAIN` | string | — | Yes | Cognito hosted UI domain |
| `SES_REGION` | string | `""` | No | Empty = email disabled |
| `SES_SENDER_EMAIL` | string | `""` | No | Empty = email disabled |
| `FRONTEND_URL` | string | `http://localhost:5173` | Yes | For invitation links |
| `COOKIE_SECURE` | bool | `True` | Yes | `False` for local dev |
| `AUTH_NAMESPACE` | string | `authum` | Yes | Prefix for cookies/storage keys |
| `AUTH_API_PREFIX` | string | `/auth` | Yes | API mount point |
| `AUTH_COOKIE_NAME` | string | `""` | No | Override: `{namespace}_refresh_token` |
| `AUTH_COOKIE_PATH` | string | `""` | No | Override: `{prefix}/token` |
| `AUTH_CSRF_COOKIE_NAME` | string | `""` | No | Override: `{namespace}_csrf_token` |

Source: backend/app/auth_usermanagement/config.py

### 13.2 Host Config

| Variable | Type | Default | Notes |
|----------|------|---------|-------|
| `CORS_ALLOWED_ORIGINS` | string (comma-separated) | `http://localhost:3000,http://localhost:5173` | Parsed to list |

Source: backend/app/config.py

### 13.3 Frontend Config

| Variable | Default | Notes |
|----------|---------|-------|
| `VITE_COGNITO_DOMAIN` | — | Cognito hosted UI base URL |
| `VITE_COGNITO_CLIENT_ID` | — | Same as backend COGNITO_CLIENT_ID |
| `VITE_COGNITO_REDIRECT_URI` | — | OAuth callback URL |
| `VITE_AUTH_NAMESPACE` | `authum` | Must match backend namespace |
| `VITE_AUTH_API_BASE_PATH` | `/auth` | Must match backend AUTH_API_PREFIX |
| `VITE_AUTH_CALLBACK_PATH` | `/callback` | OAuth redirect path |
| `VITE_AUTH_INVITE_PATH_PREFIX` | `/invite/` | Invitation URL prefix |
| `VITE_AUTH_CSRF_COOKIE_NAME` | `{namespace}_csrf_token` | CSRF cookie for token refresh |

Derived Storage Keys:
```javascript
STORAGE_KEYS = {
    tenantId: "{namespace}_tenant_id",
    postLoginRedirect: "{namespace}_post_login_redirect",
    pkceCodeVerifier: "{namespace}_pkce_code_verifier",
}
```

Source: frontend/src/auth_usermanagement/config.js

---

## 14. Host Integration Contract

### 14.1 Ownership Matrix

| Concern | Owner | Evidence |
|---------|-------|----------|
| DB engine, SessionLocal, Base, get_db | Host | backend/app/database.py |
| Alembic migration execution | Host | backend/alembic/ |
| FastAPI app creation + middleware registration | Host | backend/app/main.py |
| CORS configuration | Host | backend/app/config.py |
| DATABASE_URL | Host | Environment variable |
| Auth routes + services + models + schemas | Auth module | backend/app/auth_usermanagement/ |
| Auth-specific config (Cognito, SES, cookies) | Auth module | backend/app/auth_usermanagement/config.py |
| Frontend provider + hooks + API client + UI | Auth module | frontend/src/auth_usermanagement/ |
| Auth migration definitions (schema/upgrade) | Auth module | backend/alembic/versions/ |

### 14.2 Host Must Provide

1. **DB runtime objects** — engine, SessionLocal, Base, get_db as FastAPI dependency
2. **Alembic execution** — run auth migrations in host pipeline
3. **FastAPI wiring** — `app.include_router(auth_router, prefix=settings.auth_api_prefix)`
4. **Middleware registration** — TenantContextMiddleware, RateLimitMiddleware, SecurityHeadersMiddleware
5. **Environment variables** — host config (CORS_ALLOWED_ORIGINS) + module config (COGNITO_*, SES_*, etc.)

### 14.3 Auth Module Provides

1. **Router** — `auth_router` with all endpoints mounted
2. **Middleware classes** — ready to register on host app
3. **Models** — all table definitions inheriting from host's Base
4. **Services** — stateless functions that accept `db: Session` parameter
5. **Frontend package** — AuthProvider, hooks, authApi, cognitoClient, admin UI

Evidence:
- backend/app/auth_usermanagement/database.py (re-exports host objects)
- backend/app/auth_usermanagement/api/__init__.py (exports auth_router)
- backend/app/main.py (host wiring)

---

## 15. Multi-Tenancy Isolation Strategy

### 15.1 Three Layers of Isolation

| Layer | Mechanism | Enforced By | Coverage |
|-------|-----------|-------------|----------|
| 1. Application | Active membership check in dependency | `get_tenant_context()` | Every tenant-scoped endpoint |
| 2. PostgreSQL RLS | Session variable `app.current_tenant_id` | RLS policies on memberships, invitations | Query-level filtering even if app logic has bugs |
| 3. Query scoping | Explicit `tenant_id` filter in service queries | Service layer | Business logic queries |

### 15.2 RLS Policy Details

Tables with RLS enabled:
- **memberships**: `tenant_id = current_setting('app.current_tenant_id')::uuid OR current_setting('app.is_platform_admin') = 'true'`
- **invitations**: Same policy pattern

RLS characteristics:
- FORCE ROW LEVEL SECURITY enabled (table owners must also follow policies)
- Default deny: queries without setting `app.current_tenant_id` return 0 rows
- Platform admin bypass: `app.is_platform_admin = 'true'` sees all rows

### 15.3 Session Variable Lifecycle

```python
# Set per-request in get_tenant_context dependency:
db.execute(text("SET app.current_tenant_id = :tid"), {"tid": str(tenant_id)})
db.execute(text("SET app.is_platform_admin = :val"), {"val": "true" if is_admin else "false"})

# Cleared automatically when DB session is returned to pool (connection reset)
```

---

## 16. Rate Limiting Specification

### 16.1 Configuration

| Setting | Default | Notes |
|---------|---------|-------|
| Limit | 30 requests | Per window per key |
| Window | 60 seconds | Sliding window |
| Key format | `"{client_ip}:{path}"` | Per-IP, per-endpoint |

### 16.2 Protected Paths

| Path Pattern | Why Protected |
|-------------|---------------|
| `/auth/debug-token` | Token inspection endpoint |
| `/auth/sync` | User creation/update |
| `/auth/invite` | Invitation creation |
| `/auth/invites/accept` | Invitation acceptance |
| `/auth/token/refresh` | Token rotation |
| `/auth/cookie/store-refresh` | Cookie creation |
| `/auth/tenants/{id}/invite` | Invitation creation (explicit tenant) |

### 16.3 Response on Limit Exceeded

Status: 429 Too Many Requests
Headers: `Retry-After: <seconds remaining in window>`
Body: `{"detail": "Rate limit exceeded"}`

### 16.4 Backend Implementations

| Backend | Class | Use Case |
|---------|-------|----------|
| PostgreSQL | `PostgresRateLimiter` | Multi-process (production) |
| In-memory | `InMemoryRateLimiter` | Single-process (development) |

Factory: `create_rate_limiter(db_factory=None)` — returns PostgresRateLimiter if db_factory provided, InMemoryRateLimiter otherwise.

---

## 17. Testing Strategy

### 17.1 Test Inventory (77 tests across 20 files)

| Category | Test File(s) | Count | What It Validates |
|----------|-------------|-------|-------------------|
| Architecture Guardrails | `test_db_ownership_boundary`, `test_db_runtime_guardrails` | 4 | Module never creates own DB runtime; no forbidden patterns in source |
| JWT & Token Mgmt | `test_cookie_token_service`, `test_cookie_token_endpoints` | 12 | HttpOnly cookies, CSRF validation, Cognito refresh, token rotation |
| Refresh Token Store | `test_refresh_token_store_service` | 4 | Store/get/rotate/revoke roundtrip; expiry purge |
| Session Lifecycle | `test_session_service`, `test_session_api` | 11 | Create, validate, rotate, revoke, list; hash verification; API integration |
| Invitation Lifecycle | `test_invitation_service` | 9 | Create, accept, revoke; email normalization; expiry; role downgrade prevention |
| Role & Authorization | `test_guards` | 5 | RBAC enforcement; platform admin bypass; invalid role rejection |
| Tenant Middleware | `test_tenant_middleware`, `test_tenant_isolation_api` | 9 | Route skipping; header validation; cross-tenant blocking; custom prefix |
| User Management | `test_user_management_service` | 3 | Admin role restrictions; owner promotion rights |
| User Suspension | `test_user_suspension`, `test_user_suspension_api` | 13 | Suspend/unsuspend lifecycle; self-action prevention; platform admin requirements |
| Platform Tenant | `test_platform_tenant_api` | 3 | Tenant suspend/unsuspend; tenant listing; non-admin rejection |
| Audit Logging | `test_audit_service` | 2 | DB persistence; graceful degradation without DB |
| RLS (PostgreSQL) | `test_row_level_security` | 4 | Membership isolation; invitation isolation; platform admin bypass; default deny |
| Rate Limiting | `test_rate_limit_middleware` | 2 | Protected route matching; custom prefix |
| Auth Prefix | `test_main_auth_prefix` | 1 | Dynamic prefix binding at startup |

### 17.2 Unit Tests

**Token & Cookie Security:**
- HttpOnly cookie flag enforced on refresh token cookie
- SameSite=Strict set on all auth cookies
- CSRF token mismatch → 403
- Missing CSRF header → 403
- Missing refresh cookie → 401
- Cognito HTTP error → ValueError with error_description
- Cognito error-in-200-body → ValueError
- Cookie rotation on new refresh token from Cognito

**Session Service:**
- Token hashed before storage (SHA256)
- Hash mismatch → validation returns None
- Expired session → validation returns None
- Rotation revokes old + creates new in single commit
- Rotation failure (bad old token) → None, no side effects
- Revoke-all returns correct count
- List returns newest-first with limit

**Invitation Service:**
- Email normalized (whitespace + casing)
- Previous pending invitation auto-revoked on new invite
- Expired invitation → ValueError
- Email mismatch → PermissionError
- Revoked invitation → ValueError
- Already-accepted invitation → cannot revoke
- Reactivation preserves higher existing role (never downgrades)

**User Management:**
- Admin cannot assign owner/admin roles → ValueError
- Admin cannot modify owner-role users → ValueError
- Owner can promote member to admin

**User Suspension:**
- Suspend sets is_active=False + suspended_at timestamp
- Unsuspend sets is_active=True + clears suspended_at
- Nonexistent user → ValueError
- Suspending already-suspended user is idempotent
- Unsuspending active user is idempotent
- New users default to is_active=True

### 17.3 Integration Tests

**API Endpoint Tests:**
- Session register + rotate + list lifecycle via HTTP
- Rotating already-revoked session → 404
- Invalid X-Current-Session-ID format → 400
- Store refresh endpoint requires auth (401 without token)
- Token refresh rate limited (429 on 3rd request with limit=2)
- Platform admin can list all users with membership details
- Non-admin cannot list users (403)
- Suspend/unsuspend via API returns correct state
- Self-suspend prevention (400)
- Self-demote prevention (400)
- User/tenant 404 on missing ID
- Cross-tenant access blocked (403)
- Member can access own tenant (200)

### 17.4 Architecture Guardrail Tests

- Auth module re-exports host DB runtime objects (not new instances)
- Auth config does not define DATABASE_URL
- Tenant middleware source does not contain `SessionLocal(` calls
- No `create_engine(`, `sessionmaker(`, `declarative_base(` in auth_usermanagement/**/*.py

### 17.5 Data Isolation Tests (RLS — PostgreSQL Only)

- Membership query with tenant_a context returns only tenant_a memberships
- Membership query with tenant_b context returns only tenant_b memberships
- Invitation query respects same tenant isolation
- Platform admin with `app.is_platform_admin='true'` sees all rows
- No context set → 0 rows returned (default deny)

### 17.6 State Transition Tests

| Entity | Transition Tested | File |
|--------|------------------|------|
| Invitation | pending → accepted | test_invitation_service |
| Invitation | pending → expired (rejection) | test_invitation_service |
| Invitation | pending → revoked | test_invitation_service |
| Invitation | accepted → revoke (blocked) | test_invitation_service |
| Session | active → revoked | test_session_service |
| Session | active → rotated (old revoked + new active) | test_session_service |
| User | active → suspended | test_user_suspension |
| User | suspended → active | test_user_suspension |
| User | active → suspended → active (API) | test_user_suspension_api |
| User | regular → platform_admin → regular | test_user_suspension_api |
| Tenant | active → suspended → active | test_platform_tenant_api |
| Membership | member → admin (owner-promoted) | test_user_management_service |
| Membership | removed → active (re-invite with role preservation) | test_invitation_service |

### 17.7 Security Tests

| Attack Vector | Test | Expected Behavior |
|--------------|------|-------------------|
| CSRF token missing | test_cookie_token_endpoints | 403 |
| CSRF token mismatch | test_cookie_token_endpoints | 403 |
| Cross-tenant data access | test_tenant_middleware | 403 |
| Privilege escalation (admin → owner role) | test_user_management_service | ValueError |
| Self-suspension | test_user_suspension_api | 400 |
| Self-demotion | test_user_suspension_api | 400 |
| Non-admin accessing admin endpoints | test_user_suspension_api | 403 |
| Missing auth token on protected endpoint | test_cookie_token_endpoints | 401 |
| Expired invitation acceptance | test_invitation_service | ValueError |
| Email mismatch on invitation accept | test_invitation_service | PermissionError |
| DB runtime bypass in module | test_db_runtime_guardrails | Pattern scan blocks |
| SessionLocal in middleware | test_db_ownership_boundary | Source scan blocks |
| RLS default deny (no context) | test_row_level_security | 0 rows |

### 17.8 Concurrency & Race Condition Analysis

**Currently Not Tested (V2 Candidates):**

| Scenario | Risk | Mitigation in Code | Test Gap |
|----------|------|-------------------|----------|
| Two concurrent `accept_invitation` for same token | Double membership creation | `accepted_at IS NULL` check, but no DB-level lock | No concurrent test |
| Two concurrent `rotate_user_session` for same session | Double rotation → orphaned sessions | Validation check on old token, but no SELECT FOR UPDATE | No concurrent test |
| Concurrent `create_invitation` for same email+tenant | Race on auto-revoke of previous | Sequential revoke + create, but no explicit lock | No concurrent test |
| Concurrent `remove_user_from_tenant` for last owner | Both pass "last owner" check | Count query not locked | No concurrent test |
| Concurrent `demote_from_platform_admin` for last admin | Both pass "last admin" check | Count query not locked | No concurrent test |

---

## 18. Release Gates

Gate 1 — DB ownership and runtime guardrails
```
pytest -q tests/test_db_ownership_boundary.py tests/test_db_runtime_guardrails.py
```

Gate 2 — Auth prefix/bootstrap and middleware behavior
```
pytest -q tests/test_main_auth_prefix.py tests/test_tenant_middleware.py tests/test_rate_limit_middleware.py
```

Gate 3 — Session, invitation, cookie-refresh, audit core behavior
```
pytest -q tests/test_session_service.py tests/test_session_api.py tests/test_invitation_service.py tests/test_cookie_token_endpoints.py tests/test_audit_service.py
```

Gate 4 — Authorization and user management
```
pytest -q tests/test_guards.py tests/test_user_management_service.py tests/test_user_suspension.py tests/test_user_suspension_api.py tests/test_platform_tenant_api.py tests/test_tenant_isolation_api.py
```

Gate 5 — Full backend regression
```
pytest -q tests
```

Gate 6 — PostgreSQL RLS validation
```
RUN_POSTGRES_RLS_TESTS=1 DATABASE_URL=<postgres-url> pytest -q tests/test_row_level_security.py
```

RULE: Gate 6 is mandatory for any PR touching tenant middleware, tenant dependencies, or tenant-scoped query logic. SQLite-only runs are insufficient for sign-off on tenant isolation changes.

---

## 19. Operational Runbook

### Scenario A — Refresh Cookie Not Working

```
1. Is the refresh cookie present in browser DevTools → Application → Cookies?
   ├─ No → Was POST /auth/cookie/store-refresh called after login?
   │        Check AuthProvider bootstrap flow (Step 3).
   └─ Yes → Is the cookie name correct?
             Check AUTH_NAMESPACE env var → expected: {namespace}_refresh_token
             │
             ├─ Name correct → Is CSRF cookie also present?
             │   ├─ No → CSRF cookie was not set. Check store-refresh response headers.
             │   └─ Yes → Is X-CSRF-Token header sent on /token/refresh?
             │       ├─ No → Frontend authApi.refreshAccessToken() not reading CSRF cookie
             │       └─ Yes → Does CSRF header value match cookie value?
             │           ├─ No → Token mismatch. Check cookie domain/path scope.
             │           └─ Yes → Check backend logs for Cognito refresh errors.
             │                    Call to Cognito /oauth2/token may be failing.
             │                    Verify COGNITO_DOMAIN and COGNITO_CLIENT_ID.
             └─ Name wrong → AUTH_NAMESPACE mismatch between frontend and backend config
```

### Scenario B — Tenant Access Denied (403)

```
1. Is X-Tenant-ID header present in request?
   ├─ No → Frontend not setting header. Check authApi tenant-scoped functions.
   └─ Yes → Is it a valid UUID?
       ├─ No → Middleware rejects malformed UUID → 400
       └─ Yes → Does user have active membership for this tenant?
           ├─ No → Check memberships table: user_id + tenant_id + status="active"
           │       Was user removed? Check status="removed".
           │       Was tenant suspended? Check tenants.status.
           └─ Yes → Is user suspended?
               ├─ Yes → User is_active=False → 401 from get_current_user
               └─ No → Check RLS session variables being set.
                        Run: SELECT current_setting('app.current_tenant_id')
                        If empty/wrong → get_tenant_context dependency not setting variables.
```

### Scenario C — Session List/Revoke Mismatch

```
1. Is X-Current-Session-ID header set correctly?
   ├─ No → is_current flag will be false for all sessions.
   │       Frontend must store session_id from register response.
   └─ Yes → Is the UUID format valid?
       ├─ No → API returns 400 "Invalid session ID format"
       └─ Yes → Does session belong to current user?
           ├─ No → Session query scoped to user_id. Other users' sessions invisible.
           └─ Yes → Is session already revoked?
                    Check sessions.revoked_at — non-null means revoked.
                    Revoke on already-revoked session is idempotent (no error).
```

### Scenario D — Invitation Not Arriving / Not Working

```
1. Was email_sent=true in the create response?
   ├─ No → SES not configured. Check SES_REGION and SES_SENDER_EMAIL env vars.
   │       Invitation was created but email not sent. Token is in response — deliver manually.
   └─ Yes → Is the invitation still pending?
       ├─ Check status: "revoked" means it was auto-revoked by a newer invitation.
       ├─ Check status: "expired" means TTL exceeded (default 2 days).
       └─ "pending" → Has user trying to accept logged in with matching email?
            Email must match exactly (case-insensitive after normalization).
            PermissionError raised if emails don't match.
```

### Scenario E — Audit Record Missing in DB

```
1. Is the structured log present in application logs?
   ├─ No → log_audit_event() was not called. Check service code for the operation.
   └─ Yes → Was db parameter passed to log_audit_event()?
       ├─ No → DB persistence was not attempted. Log-only path.
       └─ Yes → Check for DB write errors in logs (best-effort catch).
                Common: connection pool exhausted, table schema mismatch.
```

### Scenario F — RLS Not Filtering Correctly

```
1. Is the database PostgreSQL (not SQLite)?
   ├─ No → RLS does not exist on SQLite. Isolation is app-layer only.
   └─ Yes → Is the DB role a superuser?
       ├─ Yes → Superuser bypasses all RLS policies. Use a non-superuser role.
       └─ No → Is FORCE ROW LEVEL SECURITY enabled?
           ├─ Check: SELECT relforcerowsecurity FROM pg_class WHERE relname = 'memberships'
           └─ Run RLS test suite:
              RUN_POSTGRES_RLS_TESTS=1 DATABASE_URL=<url> pytest -q tests/test_row_level_security.py
```

---

## 20. Known Limitations (Only What Code Shows)

Limitation 1 — No Package Distribution Metadata
Current reuse mode is source-level integration. No `pyproject.toml` or `setup.py` in module path. Consumers copy the module directory into their project.

Limitation 2 — Frontend Tests Narrower Than Backend
Existing frontend tests cover config, user list, and admin dashboard. No frontend tests for PKCE flow, token refresh, or session management.

Limitation 3 — RLS Requires Explicit PostgreSQL Test Mode
SQLite runs do not validate RLS policy behavior. Developers must run `RUN_POSTGRES_RLS_TESTS=1` explicitly.

Limitation 4 — Invitation Delivery Depends on SES
If SES is not configured, invitation creation succeeds and returns `email_sent=false`. The token must be delivered manually.

Limitation 5 — No Concurrency Tests
Race conditions on concurrent invitation accepts, session rotations, and last-owner removals are not tested. Application-layer checks exist but lack DB-level locks.

Limitation 6 — No Cognito ↔ Local User Reconciliation Job
If a user exists in Cognito but not locally (e.g., sync failed), there is no background job to detect and repair the drift. Recovery depends on the next `POST /auth/sync` call.

Limitation 7 — Audit Events Lack Actor Type Classification
Unlike billing-domain audit logs, auth audit events do not distinguish between `webhook`, `cron`, `admin`, and `system` actor types. The `actor_user_id` field captures who but not what triggered the action.

Limitation 8 — Permission Demo Endpoints in Production Router
`/admin/settings`, `/owner/danger-zone`, `/member/dashboard`, `/viewer/reports` are always mounted. No feature flag or environment gate to disable them in production.

---

## 21. Future Considerations

### 21.1 Concurrency Guards (V2)
Add `SELECT FOR UPDATE` on critical paths:
- Invitation acceptance (prevent double membership)
- Session rotation (prevent orphaned sessions)
- Last-owner removal check (prevent tenant orphaning)
- Last-admin demotion check (prevent platform lockout)

### 21.2 Cognito ↔ Local Reconciliation Job (V2)
A periodic job that lists Cognito users and compares against the local users table. Detects: orphaned local users (deleted from Cognito), orphaned Cognito users (no local row), and `cognito_sub` drift (user recreated in Cognito). Writes findings to a reconciliation log.

### 21.3 Audit Event Actor Classification (V2)
Add `actor_type` (string: `user` | `admin` | `system` | `cron`) and `trigger_source` (string: `api` | `middleware` | `background_job`) columns to `audit_events`. Required for compliance investigations ("which admin suspended this user?").

### 21.4 Materialized Entitlements Cache (V2)
Background job projects auth state into `user_id → {tenants[], roles{}, is_admin}` materialized view. O(1) lookups. Zero consumer API changes. Useful when entitlement checks become a performance bottleneck.

### 21.5 Feature Flag for Demo Endpoints (V2)
Gate permission demo endpoints behind `ENABLE_DEMO_ENDPOINTS=true` environment variable. Default to disabled in production.

### 21.6 Session Cleanup Cron (V2)
A periodic job to delete expired sessions and expired `refresh_tokens` rows. Currently, expired refresh tokens are purged lazily on retrieval only.

### 21.7 Rate Limit Cleanup Cron (V2)
Periodic deletion of old `rate_limit_hits` rows. Without cleanup, the table grows indefinitely when using the PostgreSQL backend.

### 21.8 Frontend Test Expansion (V2)
Add frontend tests for:
- PKCE OAuth flow (mock Cognito responses)
- Token auto-refresh loop (mock timer + API)
- Session management panel (revoke actions)
- Invitation acceptance flow
- Error state handling (expired token, suspended user)

### 21.9 Package Distribution (V2)
Add `pyproject.toml` with entry points so the auth module can be installed via `pip install` rather than source-level copy. Frontend module published as npm package.

### 21.10 Multi-Region Cognito Support (V2)
Allow configuring multiple Cognito user pools for different regions. JWKS cache would need to be keyed by region. JWT validation would check issuer against all configured pools.

---

## 22. Final Statement

This architecture plan is intentionally strict and code-aligned.

If a behavior is not represented in the listed source files or tests, it is out of scope for v2.0 of this plan.

When code changes, update this document and keep it synchronized with test gates.

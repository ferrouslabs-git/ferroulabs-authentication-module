# auth_usermanagement — AI Agent Reference

> Machine-readable reference for AI coding agents working with this module.
> Structured for LLM consumption: every section is self-contained with exact file paths, function signatures, and behavioral rules.

---

## 1. System Identity

- **Module**: `auth_usermanagement` — reusable FastAPI auth + multi-tenancy + RBAC module
- **Version**: 1.0 (three-layer scope architecture: platform / account / space)
- **Auth Provider**: AWS Cognito (PKCE OAuth2 + JWT)
- **Database**: PostgreSQL (production), SQLite (tests)
- **ORM**: SQLAlchemy 2.0
- **Permission Model**: YAML-driven roles → resolved permission strings
- **Frontend**: React (hooks + context), Vite bundler
- **Tests**: 597 backend (SQLite, 95% coverage) + 57 frontend

---

## 2. Project Structure

```
backend/
├── app/
│   ├── config.py                        # Host settings (CORS, env)
│   ├── database.py                      # Host DB: engine, SessionLocal, Base, get_db()
│   ├── main.py                          # FastAPI app, middleware registration, router mount
│   └── auth_usermanagement/
│       ├── __init__.py
│       ├── auth_config.yaml             # Role + permission definitions (v3.0)
│       ├── config.py                    # Module settings (Cognito, SES, prefixes)
│       ├── database.py                  # Bridge: re-exports host DB objects via relative imports
│       ├── logging_config.py            # JSON structured logging (auto-configured on import)
│       ├── api/
│       │   ├── __init__.py              # Router composition (includes all sub-routers)
│       │   ├── auth_routes.py           # /sync, /debug-token, /me
│       │   ├── config_routes.py         # /config/roles, /config/permissions
│       │   ├── custom_ui_routes.py      # /custom/login, /signup, /confirm, /set-password, /forgot-password (AUTH_MODE=custom_ui only)
│       │   ├── invitation_routes.py     # /invite, /invites/accept, /invites/{token}
│       │   ├── permission_demo_routes.py
│       │   ├── platform_tenant_routes.py # /platform/tenants, /platform/tenants/{id}/suspend, /platform/invitations/failed
│       │   ├── platform_user_routes.py  # /platform/users, suspend/unsuspend
│       │   ├── refresh_token_routes.py  # /token/refresh, /cookie/store-refresh
│       │   ├── route_helpers.py         # Shared helpers (ensure_scope_access, invitation response)
│       │   ├── session_routes.py        # /sessions
│       │   ├── space_routes.py          # /spaces, /spaces/my
│       │   ├── tenant_routes.py         # /tenants, /tenants/my
│       │   └── tenant_user_routes.py    # /tenants/{id}/users, role changes, deactivate/reactivate
│       ├── models/
│       │   ├── __init__.py              # Exports all models
│       │   ├── audit_event.py           # AuditEvent
│       │   ├── invitation.py            # Invitation
│       │   ├── membership.py            # Membership (multi-scope)
│       │   ├── permission_grant.py      # PermissionGrant
│       │   ├── rate_limit_hit.py        # RateLimitHit
│       │   ├── refresh_token.py         # RefreshTokenStore
│       │   ├── role_definition.py       # RoleDefinition
│       │   ├── session.py               # Session (device tracking)
│       │   ├── space.py                 # Space (sub-tenant)
│       │   ├── tenant.py               # Tenant (organization)
│       │   └── user.py                  # User (Cognito-linked)
│       ├── schemas/
│       │   ├── __init__.py
│       │   ├── invitation.py
│       │   ├── session.py
│       │   ├── space.py
│       │   ├── tenant.py
│       │   ├── token.py                 # TokenPayload (JWT claims)
│       │   └── user_management.py
│       ├── security/
│       │   ├── __init__.py              # Public exports for all security utilities
│       │   ├── dependencies.py          # get_current_user, get_tenant_context, get_scope_context
│       │   ├── guards.py               # Permission guards → depend on get_scope_context → return ScopeContext
│       │   ├── jwt_verifier.py          # Cognito JWKS download + RS256 verification
│       │   ├── rate_limit_middleware.py  # IP-based rate limiting
│       │   ├── scope_context.py         # ScopeContext dataclass (v3.0, includes role_name property)
│       │   ├── security_headers_middleware.py
│       │   ├── tenant_context.py        # TenantContext dataclass (legacy compat)
│       │   └── tenant_middleware.py     # Header validation middleware
│       └── services/
│           ├── __init__.py
│           ├── audit_service.py
│           ├── auth_config_loader.py    # YAML parser, AuthConfig class
│           ├── cleanup_service.py       # Purge expired tokens, invitations, rate-limit hits, audit events
│           ├── cognito_admin_service.py # Cognito Admin API (custom_ui): create invited users, initiate auth, forgot password
│           ├── cookie_token_service.py
│           ├── email_service.py         # SES invitation emails
│           ├── invitation_service.py
│           ├── rate_limiter_service.py
│           ├── session_service.py
│           ├── space_service.py
│           ├── tenant_service.py
│           ├── user_management_service.py
│           └── user_service.py
├── alembic/
│   ├── env.py                           # Host-owned migration runner
│   └── versions/                        # 18 migration files
├── tests/
│   ├── conftest.py                      # SQLite in-memory fixtures
│   ├── test_audit_service.py
│   ├── test_auth_routes_api.py
│   ├── test_cleanup_service.py          # 9 tests for expired data purging
│   ├── test_cognito_admin_ops.py
│   ├── test_cognito_integration.py     # 28 real Cognito tests (RUN_COGNITO_TESTS=1)
│   ├── test_cognito_service_flows.py    # 43 mock-based Cognito service tests
│   ├── test_config_loader.py
│   ├── test_config_routes_api.py
│   ├── test_context_models.py
│   ├── test_cookie_token_endpoints.py
│   ├── test_cookie_token_service.py
│   ├── test_cross_feature_integration.py
│   ├── test_custom_ui_auth.py           # Custom UI auth endpoints + Cognito admin service tests
│   ├── test_db_ownership_boundary.py
│   ├── test_db_runtime_guardrails.py
│   ├── test_e2e_auth_lifecycle.py
│   ├── test_email_service.py
│   ├── test_guards.py
│   ├── test_invitation_service.py
│   ├── test_jwt_verifier.py
│   ├── test_main_auth_prefix.py
│   ├── test_medium_priority_api.py
│   ├── test_membership_backfill.py
│   ├── test_permission_guards.py
│   ├── test_platform_tenant_api.py
│   ├── test_platform_user_delete_api.py
│   ├── test_rate_limit_middleware.py
│   ├── test_rate_limiter_service.py
│   ├── test_refresh_token_store_service.py
│   ├── test_route_integration.py         # 51 route-level integration tests
│   ├── test_row_level_security.py       # PostgreSQL-only (RUN_POSTGRES_RLS_TESTS=1)
│   ├── test_scope_context.py
│   ├── test_scoped_invitations.py
│   ├── test_security_headers_middleware.py
│   ├── test_session_api.py
│   ├── test_session_service.py
│   ├── test_space_routes_api.py
│   ├── test_space_service.py
│   ├── test_tenant_detail_api.py
│   ├── test_tenant_isolation_api.py
│   ├── test_tenant_middleware.py
│   ├── test_tenant_service.py
│   ├── test_trustos_gap_features.py
│   ├── test_user_management_service.py
│   ├── test_user_service.py
│   ├── test_user_suspension_api.py
│   └── test_user_suspension.py
frontend/
├── src/
│   ├── App.jsx
│   ├── main.jsx
│   └── auth_usermanagement/
│       ├── index.js                     # Public exports
│       ├── config.js
│       ├── components/                  # LoginForm, ProtectedRoute, TenantSwitcher, CustomLoginForm, CustomSignupForm, InviteSetPassword, ForgotPasswordForm, etc.
│       ├── context/                     # AuthProvider
│       ├── hooks/                       # useAuth, useCurrentUser, useTenant, useRole, useSpace
│       ├── pages/                       # AdminDashboard
│       ├── services/                    # authApi, cognitoClient, customAuthApi
│       └── utils/
```

---

## 3. Data Model

### Tables and Key Columns

| Table | Primary Key | Key Columns | Relationships |
|---|---|---|---|
| `users` | `id` (UUID) | `cognito_sub`, `email`, `name`, `is_platform_admin`, `is_active`, `suspended_at` | → memberships, sessions, invitations |
| `tenants` | `id` (UUID) | `name`, `plan`, `status` | ← memberships, spaces |
| `memberships` | `id` (UUID) | `user_id`, `scope_type`, `scope_id`, `role_name`, `status`, `granted_by` | → user, tenant (viewonly) |
| `invitations` | `id` (UUID) | `token_hash`, `email`, `target_scope_type`, `target_scope_id`, `target_role_name`, `expires_at`, `accepted_at`, `revoked_at`, `created_by` | → creator (User) |
| `sessions` | `id` (UUID) | `user_id`, `refresh_token_hash`, `user_agent`, `ip_address`, `device_info`, `expires_at`, `revoked_at` | → user |
| `refresh_token_store` | `id` (UUID) | `cookie_key`, `refresh_token`, `expires_at` | — |
| `spaces` | `id` (UUID) | `name`, `account_id`, `status` | ← memberships |
| `role_definitions` | `id` (UUID) | `role_name`, `layer`, `display_name`, `permissions` (JSON) | — |
| `permission_grants` | `id` (UUID) | `membership_id`, `permission` | → membership |
| `audit_events` | `id` (UUID) | `action`, `actor_user_id`, `tenant_id`, `target_type`, `target_id`, `metadata_json`, `ip_address`, `created_at` | — |
| `rate_limit_hits` | `id` (UUID) | `key`, `hit_at` | — |

### Key Constraints

- `memberships`: `UNIQUE(user_id, role_name, scope_type, scope_id)` — prevents duplicate role assignments
- `users`: `UNIQUE(cognito_sub)`, `UNIQUE(email)`
- `memberships.scope_type`: one of `"platform"`, `"account"`, `"space"`
- `memberships.status`: one of `"active"`, `"removed"`, `"suspended"`

---

## 4. Scope and Permission System

### Three-Layer Hierarchy

```
platform (super_admin only)
  └── account (organization/tenant)
       └── space (sub-grouping within an account)
```

### Permission Resolution Flow

```
Request headers (X-Scope-Type + X-Scope-ID)
  → get_scope_context() dependency
    → Query memberships WHERE user_id + scope_type + scope_id + status=active
      → Collect role_names
        → For each role: auth_config.permissions_for_role(role_name) → set[str]
          → Union all → resolved_permissions
            → Guard checks: has_permission("members:manage") → bool
```

### auth_config.yaml Structure

```yaml
version: "3.0"
layers:
  account: { enabled: true, display_name: "Account" }
  space:   { enabled: true, display_name: "Space" }
inheritance:
  account_member_space_access: none  # none | space_viewer | space_member
roles:
  platform:
    - name: super_admin
      permissions: [platform:configure, accounts:manage, users:suspend]
  account:
    - name: account_owner
      permissions: [account:delete, account:read, spaces:create, members:manage, members:invite]
    - name: account_admin
      permissions: [account:read, spaces:create, members:invite]
    - name: account_member
      permissions: [account:read]
  space:
    - name: space_admin
      permissions: [space:delete, space:configure, space:read, members:manage, members:invite, data:read, data:write]
    - name: space_member
      permissions: [space:read, data:read, data:write]
    - name: space_viewer
      permissions: [space:read, data:read]
```

### Structural Permission Vocabulary

These are the built-in permission strings validated by the config loader:

```
platform:configure, accounts:manage, users:suspend,
account:delete, account:read, spaces:create, space:delete,
space:configure, space:read, members:manage, members:invite,
data:read, data:write
```

Custom permissions can be added (any `noun:verb` format).

### Space Inheritance

When `scope_type=space`, the system checks parent account memberships:
- `account_owner` → inherits `space_admin`
- `account_admin` → inherits `space_admin`
- `account_member` → inherits value of `inheritance.account_member_space_access` (default: `none`)

---

## 4a. Scope Mapping Guide — Adapting the Module to Any Application

This module ships with a generic three-layer scope hierarchy:

```
platform  →  account  →  space
```

These are abstract containers. **Every host application relabels them** to match its own domain language. No code changes, migrations, or new tables are needed — you only edit display names and trim unused roles in `auth_config.yaml`.

### How the Three Layers Work

| Layer | What It Represents | Who Lives Here |
|---|---|---|
| **platform** | The entire SaaS instance | Super Admin — manages all accounts, can suspend users/accounts |
| **account** | A top-level organizational unit (a portfolio, company, workspace, etc.) | The account owner and any account-level roles |
| **space** | A sub-grouping inside an account | End-user roles that operate on data inside this grouping |

The layer names `account` and `space` are internal identifiers stored in `memberships.scope_type`. The user-facing labels come from `auth_config.yaml → layers → display_name`.

### Inheritance Rule

When a user accesses a **space**, the system automatically checks their **parent account** membership and promotes their effective role:

| Account Role | Inherited Space Role |
|---|---|
| `account_owner` | `space_admin` (full access to every space in the account) |
| `account_admin` | `space_member` |
| `account_member` | configurable via `inheritance.account_member_space_access` (default: `none`) |

This is implemented in `security/dependencies.py → _resolve_space_inheritance()` using the `_ACCOUNT_SPACE_INHERITANCE` dict.

**Key consequence**: an `account_owner` never needs an explicit space membership — they automatically have `space_admin` in every child space.

### Mapping Steps for a New Application

1. **Identify your role hierarchy.** List every role in your app from most-privileged to least.

2. **Split into three tiers:**
   - **Platform tier** — god-mode admin(s) that manage the whole system. Maps to `super_admin`.
   - **Account tier** — the highest real-user scope. This is typically whoever "owns" a client, portfolio, workspace, or company. Maps to `account_owner` (and optionally `account_admin`, `account_member`).
   - **Space tier** — the scope where everyday work happens. Maps to `space_admin`, `space_member`, `space_viewer` (pick whichever subset you need).

3. **Update `auth_config.yaml`:**
   - Change `layers.account.display_name` and `layers.space.display_name` to match your domain language.
   - Remove any roles you don't need (e.g., if you only need `account_owner`, drop `account_admin` and `account_member`).
   - Add or remove permission strings per role as needed.
   - Adjust `inheritance.account_member_space_access` if needed.

4. **No backend code changes required.** The scope resolution, membership queries, permission guards, and inheritance logic all read from the YAML.

5. **Frontend:** Update `TenantSwitcher` labels and any UI copy to use your domain's terminology (e.g. "Organization" instead of "Space").

### Concrete Example — TrustOS

TrustOS has four roles: Super Admin, Consultant, Org Admin, Viewer.

**Step 1 — Identify the hierarchy:**
```
Super Admin  →  manages everything
Consultant   →  owns a portfolio of organizations
Org Admin    →  manages one organization
Viewer       →  read-only access to one organization
```

**Step 2 — Map to the three layers:**

| TrustOS Role | Module Layer | Module Role | Why |
|---|---|---|---|
| Super Admin | platform | `super_admin` | System-wide management |
| Consultant | account | `account_owner` | Owns a portfolio (account). Inheritance gives automatic `space_admin` in every org under the portfolio |
| Org Admin | space | `space_admin` | Full control within a single organization |
| Viewer | space | `space_viewer` | Read-only access within a single organization |

**Step 3 — YAML changes:**
```yaml
layers:
  account: { enabled: true, display_name: "Portfolio" }
  space:   { enabled: true, display_name: "Organization" }
roles:
  platform:
    - name: super_admin
      permissions: [platform:configure, accounts:manage, users:suspend]
  account:
    - name: account_owner
      display_name: "Consultant"
      permissions: [account:delete, account:read, spaces:create, members:manage, members:invite]
  space:
    - name: space_admin
      display_name: "Org Admin"
      permissions: [space:delete, space:configure, space:read, members:manage, members:invite, data:read, data:write]
    - name: space_viewer
      display_name: "Viewer"
      permissions: [space:read, data:read]
```

Roles removed (not needed by TrustOS): `account_admin`, `account_member`, `space_member`.

**Result:** A Consultant creates a portfolio (account), then creates Organizations (spaces) inside it. Because `account_owner → space_admin` inheritance, the Consultant automatically has full admin access to every Organization in their portfolio — without needing individual space memberships.

### What About Two-Layer Apps?

If your app has no sub-grouping (e.g., just "Admin" and "Member" inside a company):

```yaml
layers:
  account: { enabled: true, display_name: "Company" }
  space:   { enabled: false }
```

Set `space.enabled: false`. All roles live at the account layer. The space tables and logic remain dormant.

---

## 5. Request Lifecycle

```
1. Client sends request:
   Headers: Authorization: Bearer <jwt>, X-Tenant-ID: <uuid>
   (or: X-Scope-Type: account|space, X-Scope-ID: <uuid>)

2. SecurityHeadersMiddleware — adds CSP, X-Frame-Options, etc.

3. RateLimitMiddleware — checks IP:path against rate limits
   - Protected paths: /sync, /debug-token, /invite, /invites/accept, /token/refresh, /cookie/store-refresh
   - Limit: 30 requests / 60 seconds per IP:path

4. TenantContextMiddleware — validates headers (no DB access)
   - Stores request.state.requested_scope_type, requested_scope_id, requested_tenant_id
   - Skips: /health, /sync, /debug-token, /me, /tenants, /tenants/my, /config/*, /custom/*
     (Custom UI endpoints are pre-authentication and skip tenant context)

5. Route handler invoked with dependency injection:
   a. get_current_user() → verify JWT → load User from DB → check is_active
   b. get_scope_context() → parse scope headers → query memberships → resolve permissions → ScopeContext
   c. Guards: require_permission("members:invite")(ctx) → 403 if missing

6. Service layer executes business logic with DB session

7. Response returns through middleware stack (reverse order)
```

---

## 6. Service Reference

### user_service.py

```python
sync_user_from_cognito(token_payload: TokenPayload, db: Session) -> User
get_user_by_cognito_sub(cognito_sub: str, db: Session) -> Optional[User]
get_user_by_id(user_id: UUID, db: Session) -> Optional[User]
get_user_by_email(email: str, db: Session) -> Optional[User]
suspend_user(user_id: UUID, db: Session) -> User
unsuspend_user(user_id: UUID, db: Session) -> User
promote_to_platform_admin(user_id: UUID, db: Session) -> User
demote_from_platform_admin(user_id: UUID, db: Session) -> User
delete_user(user_id: UUID, db: Session) -> dict  # Full cleanup: Cognito + sessions + memberships + invitations + user record
```

### tenant_service.py

```python
create_tenant(name: str, user: User, db: Session, plan: str = "free") -> Tenant
get_tenant_by_id(tenant_id: UUID, db: Session) -> Optional[Tenant]
get_user_tenants(user_id: UUID, db: Session) -> List[dict]
get_user_tenant_role(user_id: UUID, tenant_id: UUID, db: Session) -> Optional[str]
list_platform_tenants(db: Session) -> List[dict]
verify_user_tenant_access(user_id: UUID, tenant_id: UUID, db: Session) -> bool
suspend_tenant(tenant_id: UUID, db: Session) -> Tenant
unsuspend_tenant(tenant_id: UUID, db: Session) -> Tenant
update_tenant(tenant_id: UUID, db: Session, *, name: str | None = None, plan: str | None = None) -> Tenant
delete_tenant(tenant_id: UUID, db: Session) -> dict
```

### invitation_service.py

```python
create_invitation(db, tenant_id, email, role, created_by, expires_in_days=2, target_scope_type=None, target_scope_id=None, target_role_name=None) -> tuple[Invitation, str]  # (invitation, raw_token)
get_invitation_by_token(db: Session, token: str) -> Invitation | None
accept_invitation(db: Session, invitation: Invitation, user: User) -> Membership
get_tenant_invitation_by_token(db: Session, tenant_id: UUID, token: str) -> Invitation | None
get_invitation_by_id(db: Session, tenant_id: UUID, invitation_id: UUID) -> Invitation | None
resend_invitation(db: Session, invitation: Invitation, expires_in_days: int = 2) -> tuple[Invitation, str]  # generates fresh token, extends expiry
revoke_invitation(db: Session, invitation: Invitation) -> Invitation
list_tenant_invitations(db: Session, tenant_id: UUID, *, status_filter: str | None = None) -> list[dict]
```

### session_service.py

```python
create_user_session(db, user_id, refresh_token, *, user_agent=None, ip_address=None, device_info=None, expires_at=None) -> AuthSession
list_user_sessions(db, user_id, *, include_revoked=False, limit=50) -> list[AuthSession]
validate_refresh_session(db, user_id, session_id, refresh_token) -> AuthSession | None
rotate_user_session(db, user_id, session_id, old_refresh_token, new_refresh_token, **kwargs) -> AuthSession | None
revoke_user_session(db, user_id, session_id) -> AuthSession | None
revoke_all_user_sessions(db, user_id, except_session_id=None) -> int
```

### space_service.py

```python
create_space(db, name, account_id, creator_user_id) -> Space
list_user_spaces(db, user_id) -> list[Space]
list_account_spaces(db, account_id) -> list[Space]
suspend_space(db, space_id) -> Space
unsuspend_space(db, space_id) -> Space
get_space_by_id(db, space_id) -> Space | None
update_space(db, space_id, *, name: str | None = None) -> Space
```

### user_management_service.py

```python
list_tenant_users(db: Session, tenant_id: UUID, *, role: str | None = None, status_filter: str | None = None) -> list[dict]
list_platform_users(db: Session, *, role: str | None = None) -> list[dict]
update_user_role(db, tenant_id, user_id, new_role, actor_role, actor_is_platform_admin=False) -> Membership | None
remove_user_from_tenant(db, tenant_id, user_id) -> Membership | None
reactivate_user_in_tenant(db: Session, tenant_id: UUID, user_id: UUID) -> Membership | None
```

### cookie_token_service.py

```python
store_refresh_token(db, refresh_token) -> str  # returns cookie_key
get_refresh_token(db, cookie_key) -> str | None
rotate_refresh_token(db, cookie_key, new_refresh_token) -> str
revoke_refresh_token(db, cookie_key) -> None
set_refresh_cookie(response, cookie_key, *, secure=True, cookie_name=..., cookie_path=...) -> None
clear_refresh_cookie(response, *, secure=True, ...) -> None
call_cognito_refresh(refresh_token, cognito_domain, client_id) -> dict
```

### cognito_admin_service.py

```python
# Custom UI auth flows (AUTH_MODE=custom_ui)
create_invited_cognito_user(email: str) -> dict  # Pre-creates Cognito user with FORCE_CHANGE_PASSWORD
initiate_auth(email: str, password: str) -> dict
respond_to_new_password_challenge(email: str, new_password: str, session: str) -> dict
sign_up_user(email: str, password: str) -> dict
confirm_sign_up(email: str, confirmation_code: str) -> dict
resend_confirmation_code(email: str) -> dict
forgot_password(email: str) -> dict
confirm_forgot_password(email: str, code: str, new_password: str) -> dict

# Admin operations (platform admin only)
admin_delete_user(email: str) -> dict     # Permanent Cognito deletion
admin_disable_user(email: str) -> dict    # Block sign-in
admin_enable_user(email: str) -> dict     # Re-enable sign-in
admin_get_user(email: str) -> dict        # Returns status, enabled, create_date, attributes
admin_reset_user_password(email: str) -> dict  # Force password reset via email
```

### audit_service.py

```python
log_audit_event(event: str, actor_user_id=None, db=None, **details) -> None
```

### auth_config_loader.py

```python
get_auth_config() -> AuthConfig       # Cached singleton
reset_auth_config() -> None           # Clear cache (tests only)
load_and_validate_config(config_path=None) -> AuthConfig

# AuthConfig methods:
.permissions_for_role(role_name: str) -> set[str]
.is_layer_enabled(layer: str) -> bool
```

### rate_limiter_service.py

```python
create_rate_limiter(db_factory=None) -> RateLimiter
# RateLimiter.is_rate_limited(key, limit, window_seconds) -> bool
# RateLimiter.close() -> None
```

### cleanup_service.py

```python
run_cleanup(db, invitation_days=30, rate_limit_hours=24, audit_retention_days=365) -> dict
# Returns: {"refresh_tokens": N, "invitations": N, "rate_limit_hits": N, "audit_events": N}
# Set audit_retention_days=0 to skip audit purging
```

### email_service.py

```python
send_invitation_email(to_email, invite_url, tenant_name) -> EmailSendResult  # async
```

---

## 7. Security Dependencies

```python
# Import from: app.auth_usermanagement.security

get_current_user          # Depends → User (401 if invalid/expired JWT, 404 if not synced)
get_current_user_optional # Depends → User | None
get_tenant_context        # Depends → TenantContext (legacy)
get_scope_context         # Depends → ScopeContext (v3.0, resolves permissions)

# Guards (use in route Depends) — all depend on get_scope_context, return ScopeContext:
require_permission(perm: str)              # Single permission check
require_any_permission(perms: list[str])   # Any of listed permissions
require_all_permissions(perms: list[str])  # All listed permissions  
require_super_admin                        # Platform admin only

# DEPRECATED (remove after 2026-05-20):
require_role, require_min_role, require_owner, require_admin, require_member, require_viewer
```

### Guard Usage Pattern

```python
from app.auth_usermanagement.security import require_permission, get_current_user
from ..database import get_db

@router.delete("/tenants/{tenant_id}/users/{user_id}")
async def remove_user(
    tenant_id: UUID,
    user_id: UUID,
    ctx: ScopeContext = Depends(require_permission("members:manage")),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ...
```

---

## 8. Key Invariants (Do Not Violate)

1. **Host owns DB runtime**: `engine`, `SessionLocal`, `Base`, `get_db()` live in `app/database.py`. Never create these inside `auth_usermanagement/`.

2. **Module uses relative imports for DB objects**: All files inside `auth_usermanagement/` import `Base` and `get_db` through the module's own `database.py` bridge (`from ..database import Base`). Only `auth_usermanagement/database.py` itself references `from app.database import ...`. This is enforced by `test_db_runtime_guardrails.py::test_no_direct_host_database_imports_outside_bridge`.

3. **No direct SessionLocal() in middleware**: Middleware does header validation only. DB access happens in dependency injection path.

3. **Module does not own DATABASE_URL**: Host app's `.env` and `app/config.py` control the connection string.

4. **Membership uses scope columns**: `scope_type` (platform/account/space) + `scope_id` (UUID). Legacy `tenant_id` and `role` columns have been dropped.

5. **Permission strings are `noun:verb`**: Format validated by regex `^[a-z_]+:[a-z_]+$`. Custom permissions are allowed.

6. **Invitation tokens are hashed**: `token_hash = sha256(raw_token)` stored in DB. The `token` column also stores the hash (never plaintext). The raw token is returned only from `create_invitation()` and must be used for email URLs and API responses.

7. **Platform admin bypasses all permission checks**: `ScopeContext.is_super_admin=True` → `has_permission()` always returns `True`.

8. **RLS requires PostgreSQL**: Row-level security policies are PostgreSQL-specific. SQLite tests skip them.

9. **Membership status filtering**: Queries must filter `status="active"` to exclude removed/suspended members.

10. **Last owner protection**: `remove_user_from_tenant` and `update_user_role` prevent removing or demoting the last `account_owner`.

11. **Owner role restriction**: `update_membership_role()` rejects attempts to assign `account_owner` role. Ownership must use a dedicated transfer flow.

12. **Cognito sign-out on suspension**: `suspend_user()` calls `AdminUserGlobalSignOut` to revoke all Cognito refresh tokens immediately.

13. **JWKS cache TTL**: 1-hour TTL with thread-safe double-check locking. Single-retry key rotation on `kid` miss prevents cache-busting DoS.

---

## 9. Environment Variables

### Host-Owned

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/trustos` | Database connection |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000,http://localhost:5173` | CORS whitelist |

### Module-Owned

| Variable | Default | Purpose |
|---|---|---|
| `COGNITO_REGION` | `eu-west-1` | AWS Cognito region |
| `COGNITO_USER_POOL_ID` | (required) | Cognito user pool |
| `COGNITO_CLIENT_ID` | (required) | Cognito app client |
| `COGNITO_DOMAIN` | (required) | Hosted UI domain |
| `SES_REGION` | (optional) | AWS SES region |
| `SES_SENDER_EMAIL` | (optional) | From address for emails |
| `FRONTEND_URL` | `http://localhost:5173` | Invitation link base |
| `COOKIE_SECURE` | `true` | HTTPS-only cookies |
| `AUTH_API_PREFIX` | `/auth` | Route mount point |
| `AUTH_NAMESPACE` | `authum` | Cookie name prefix |
| `AUTH_CONFIG_PATH` | `<module>/auth_config.yaml` | YAML config location |
| `AUTH_MODE` | `hosted_ui` | Auth mode: `hosted_ui` (Cognito redirect) or `custom_ui` (app-owned forms) |

### Frontend (Vite)

| Variable | Purpose |
|---|---|
| `VITE_API_BASE_URL` | Backend URL |
| `VITE_COGNITO_DOMAIN` | Cognito hosted UI |
| `VITE_COGNITO_CLIENT_ID` | App client ID |
| `VITE_COGNITO_REDIRECT_URI` | OAuth callback URL |
| `VITE_AUTH_MODE` | Auth mode: `hosted_ui` (default) or `custom_ui` |

---

## 10. API Endpoints

All prefixed with `AUTH_API_PREFIX` (default: `/auth`).

### Public (no scope headers)

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/sync` | Sync Cognito JWT → DB user |
| `GET` | `/me` | Current user profile |
| `GET` | `/debug-token` | JWT payload inspection |
| `POST` | `/tenants` | Create tenant (auto-owner) |
| `GET` | `/tenants/my` | List user's tenants |
| `GET` | `/tenants/{id}` | Get tenant detail (member+ or platform admin) |
| `PATCH` | `/tenants/{id}` | Update tenant name/plan (owner+ or platform admin) |
| `GET` | `/tenants/{id}/invitations` | List tenant invitations (member+ or platform admin) |
| `POST` | `/tenants/{id}/invitations/bulk` | Bulk create up to 50 invitations (member+ or platform admin) |
| `GET` | `/me/memberships` | List all memberships for authenticated user |
| `POST` | `/invites/accept` | Accept invitation by token |
| `GET` | `/invites/{token}` | Preview invitation (no auth) |
| `POST` | `/token/refresh` | Refresh access token via cookie |
| `POST` | `/cookie/store-refresh` | Store refresh token as httpOnly cookie |
| `GET` | `/config/roles` | List configured roles |
| `GET` | `/config/permissions` | List configured permissions |

### Custom UI (AUTH_MODE=custom_ui only — returns 404 otherwise)

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/custom/login` | Email + password login via Cognito |
| `POST` | `/custom/signup` | Self-service user registration |
| `POST` | `/custom/confirm` | Confirm email with verification code |
| `POST` | `/custom/set-password` | Complete NEW_PASSWORD_REQUIRED challenge (invited users) |
| `POST` | `/custom/resend-code` | Resend email verification code |
| `POST` | `/custom/forgot-password` | Request password reset code |
| `POST` | `/custom/confirm-forgot-password` | Reset password with code + new password |

### Account-Scoped (X-Tenant-ID or X-Scope-Type=account)

| Method | Path | Guard | Purpose |
|---|---|---|---|
| `GET` | `/tenants/{id}/users` | `account:read` | List tenant members (supports `?role=` and `?status=` filters) |
| `PATCH` | `/tenants/{id}/users/{uid}/role` | `members:manage` | Change member role |
| `DELETE` | `/tenants/{id}/users/{uid}` | `members:manage` | Remove member |
| `PATCH` | `/tenants/{id}/users/{uid}/deactivate` | `members:manage` | Deactivate member (soft-remove) |
| `PATCH` | `/tenants/{id}/users/{uid}/reactivate` | `members:manage` | Reactivate deactivated member |
| `POST` | `/invite` | `members:invite` | Send invitation |
| `POST` | `/tenants/{id}/invites/{token}/resend` | `members:invite` | Resend invitation by token (fresh token + email) |
| `POST` | `/tenants/{id}/invitations/{invitation_id}/resend` | `members:invite` | Resend invitation by ID (fresh token + email) |
| `DELETE` | `/tenants/{id}/invites/{token}` | `members:invite` | Revoke invitation |
| `GET` | `/sessions` | — | List user sessions |
| `DELETE` | `/sessions/{id}` | — | Revoke session |
| `POST` | `/spaces` | `spaces:create` | Create space |
| `GET` | `/spaces/my` | `account:read` | List user's spaces |
| `GET` | `/spaces/{id}` | `account:read` | Get space detail |
| `PATCH` | `/spaces/{id}` | `spaces:create` | Update space name |

### Platform-Scoped (platform admin only)

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/platform/tenants` | List all tenants |
| `PATCH` | `/platform/tenants/{id}/suspend` | Suspend tenant |
| `PATCH` | `/platform/tenants/{id}/unsuspend` | Unsuspend tenant |
| `GET` | `/platform/invitations/failed` | List failed invitation emails |
| `GET` | `/platform/users` | List all users (supports `?role=` filter) |
| `GET` | `/platform/users/{id}` | Get user detail with memberships |
| `PATCH` | `/users/{id}/suspend` | Suspend user |
| `PATCH` | `/users/{id}/unsuspend` | Unsuspend user |
| `PATCH` | `/platform/users/{id}/promote` | Promote to platform admin |
| `PATCH` | `/platform/users/{id}/demote` | Demote from platform admin |
| `DELETE` | `/platform/users/{id}` | Permanently delete user (Cognito + DB) |
| `POST` | `/platform/users/{id}/cognito/disable` | Disable Cognito sign-in |
| `POST` | `/platform/users/{id}/cognito/enable` | Re-enable Cognito sign-in |
| `GET` | `/platform/users/{id}/cognito` | Get Cognito user status |
| `POST` | `/platform/users/{id}/cognito/reset-password` | Force password reset |
| `GET` | `/platform/audit-events` | Query audit events with filters |
| `POST` | `/platform/cleanup` | Trigger cleanup of expired tokens/invitations |
| `DELETE` | `/platform/tenants/{id}` | Permanently delete tenant (cascade) |

---

## 11. Test Commands

```bash
# Standard unit tests (SQLite, fast)
cd backend
pytest -q tests

# PostgreSQL RLS verification (required for tenant isolation changes)
RUN_POSTGRES_RLS_TESTS=1 DATABASE_URL=postgresql://user:pass@localhost:5432/testdb pytest -q tests/test_row_level_security.py

# Run specific test file
pytest -q tests/test_invitation_service.py

# Verbose with output
pytest -v tests/test_guards.py -s
```

### Test Fixture Pattern

```python
@pytest.fixture
def db_session():
    from app.database import Base
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(engine)
```

---

## 12. Common Modification Patterns

### Adding a New Permission

1. Add to `auth_config.yaml` under the appropriate role
2. Use in route guard: `require_permission("your:permission")`
3. No migration needed (YAML-driven)

### Adding a New Role

1. Add to `auth_config.yaml` under the appropriate layer:
   ```yaml
   account:
     - name: account_billing
       display_name: "Billing Manager"
       permissions: [account:read, billing:manage]
   ```
2. Run seed migration if using `role_definitions` table

### Adding a New API Endpoint

1. Add route to appropriate router file in `api/`
2. Include guard dependency: `Depends(require_permission("..."))`
3. Include DB dependency: `Depends(get_db)`
4. Add to router composition in `api/__init__.py` if new router file

### Adding a New Model

1. Create model file in `models/`
2. Import `Base` from `app.database`
3. Export from `models/__init__.py`
4. Import in `alembic/env.py`
5. Generate migration: `alembic revision --autogenerate -m "description"`
6. Run migration: `alembic upgrade head`

### Adding a New Service Function

1. Add function to appropriate service file in `services/`
2. Signature convention: `def function_name(db: Session, ...) -> ReturnType`
3. All DB sessions come from caller (dependency injection) — never create sessions inside services

---

## 13. Alembic Migration Chain

```
d3494139f54d  ← create_auth_tables (users, tenants, memberships, invitations)
    ↓
2a9b67c1d3ef  ← add_invitation_revoked_at
    ↓
6c5d7e4f8a2b  ← add_token_hash_to_invitations
    ↓
9f2e1c7a4b3d  ← add_audit_events_table
    ↓
5b3c4d2e8f9a  ← add_rate_limit_hits_table
    ↓
7a454a9250b1  ← add_user_suspension_fields
    ↓
8c5f69f3b5d1  ← add_session_metadata_fields
    ↓
f1c2d3e4a5b6  ← add_refresh_token_store_table
    ↓
0eec64567dac  ← enable_row_level_security
    ↓
4f2a1e9c7b10  ← force_rls_on_tenant_tables
    ↓
a1b2c3d4e5f6  ← add_role_definitions_and_permission_grants
    ↓
f6a7b8c9d0e1  ← seed_role_definitions
    ↓
b2c3d4e5f6a7  ← add_spaces_table
    ↓
c3d4e5f6a7b8  ← replace_memberships_schema
    ↓
e5f6a7b8c9d0  ← backfill_memberships_scope
    ↓
d4e5f6a7b8c9  ← extend_invitations_scope
    ↓
a7b8c9d0e1f2  ← update_rls_for_scope
    ↓
b1c2d3e4f5a6  ← drop_legacy_columns (HEAD)
```

---

## 14. Frontend Module Exports

```javascript
// from 'auth_usermanagement/index.js'

// Context & Hooks
AuthProvider          // Wraps app, provides auth state
useAuth               // { isAuthenticated, isLoading, logout, user, tenantId, tenants }
useCurrentUser        // Current user data
useTenant             // Tenant switching
useRole               // Role checking
useSpace              // Space management

// Components
LoginForm             // Cognito hosted UI login trigger
CustomLoginForm       // Custom UI email+password login (AUTH_MODE=custom_ui)
CustomSignupForm      // Custom UI self-service registration
ForgotPasswordForm    // Custom UI password reset flow
InviteSetPassword     // Custom UI set-password for invited users
ProtectedRoute        // Route guard (redirects if not authed)
TenantSwitcher        // Dropdown for switching active tenant
RoleSelector          // Role assignment UI
InviteUserModal       // Modal for sending invitations
UserList              // Tenant user list
SessionPanel          // Active sessions management
AcceptInvitation      // Invitation acceptance page
ToastProvider         // Toast notifications
AdminDashboard        // Platform admin page

// Services
authApi               // Backend API calls
cognitoClient         // Cognito OAuth helpers (openHostedLogin, openHostedSignup)
customAuthApi         // Custom UI API calls (login, signup, forgot-password, etc.)

// Config
AUTH_CONFIG            // Frontend auth configuration
```

---

## 15. Deprecated Items (Remove After 2026-05-20)

| Item | Location | Replacement |
|---|---|---|
| `require_role()` | `security/guards.py` | `require_permission()` |
| `require_min_role()` | `security/guards.py` | `require_permission()` |
| `require_owner` | `security/guards.py` | `require_permission("account:delete")` |
| `require_admin` | `security/guards.py` | `require_permission("members:manage")` |
| `require_member` | `security/guards.py` | `require_permission("data:write")` |
| `require_viewer` | `security/guards.py` | `require_permission("data:read")` |
| `check_permission()` | `security/guards.py` | `ScopeContext.has_permission()` |
| `TenantContext` dependency path | `security/dependencies.py` | `ScopeContext` via `get_scope_context()` |
| `_bridge_to_scope()` + `_LEGACY_ROLE_PERMISSIONS` | `security/guards.py` | Used only by deprecated guards; new guards use `get_scope_context` directly |
| `auth_usermanagement/database.py` | sole bridge to host DB | Relative imports (`from ..database`) throughout module |

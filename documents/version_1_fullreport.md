# Version 1 Full Report: Auth and User Management

Date: 2026-03-28 (updated)
Scope: backend + frontend auth_usermanagement module
Source of truth: code only (no assumptions from planning docs)

---

## 1. Folder Structure

### 1.1 Backend module structure

    backend/
      app/
        auth_usermanagement/
          __init__.py
          auth_config.yaml              # Role + permission definitions (v3.0 scope arch)
          config.py                     # Module settings (Cognito, SES, prefixes)
          database.py                   # Bridge: re-exports host DB objects
          logging_config.py             # JSON structured logging (auto-configured on import)
          api/
            __init__.py                 # Router composition
            auth_routes.py              # /sync, /debug-token, /me
            config_routes.py            # /config/roles, /config/permissions
            custom_ui_routes.py         # /custom/login, /signup, /confirm, /set-password, /forgot-password (AUTH_MODE=custom_ui only)
            invitation_routes.py        # /invite, /invites/accept, /invites/{token}
            permission_demo_routes.py
            platform_tenant_routes.py   # /platform/tenants, suspend/unsuspend, /invitations/failed
            platform_user_routes.py     # /platform/users, suspend/unsuspend
            refresh_token_routes.py     # /token/refresh, /cookie/store-refresh
            route_helpers.py            # Shared helpers (ensure_scope_access, invitation response)
            session_routes.py           # /sessions
            space_routes.py             # /spaces, /spaces/my
            tenant_routes.py            # /tenants, /tenants/my
            tenant_user_routes.py       # /tenants/{id}/users, role changes, deactivate/reactivate
          models/
            __init__.py
            audit_event.py              # AuditEvent
            invitation.py               # Invitation (scope-targeted)
            membership.py               # Membership (multi-scope: platform/account/space)
            permission_grant.py         # PermissionGrant
            rate_limit_hit.py           # RateLimitHit
            refresh_token.py            # RefreshTokenStore
            role_definition.py          # RoleDefinition
            session.py                  # Session (device tracking)
            space.py                    # Space (sub-tenant grouping)
            tenant.py                   # Tenant (organization)
            user.py                     # User (Cognito-linked)
          schemas/
            __init__.py
            invitation.py
            session.py
            space.py
            tenant.py
            token.py                    # TokenPayload (JWT claims)
            user_management.py
          security/
            __init__.py                 # Public exports
            dependencies.py             # get_current_user, get_scope_context
            guards.py                   # Permission guards (require_permission, etc.)
            jwt_verifier.py             # Cognito JWKS download + RS256 + TTL cache
            rate_limit_middleware.py     # IP-based rate limiting
            scope_context.py            # ScopeContext dataclass (v3.0)
            security_headers_middleware.py
            tenant_context.py           # TenantContext dataclass (legacy compat, deprecated)
            tenant_middleware.py         # Header validation middleware
          services/
            __init__.py
            audit_service.py
            auth_config_loader.py       # YAML parser, AuthConfig class
            cleanup_service.py          # Purge expired tokens, invitations, rate-limit hits, audit events
            cognito_admin_service.py    # Cognito Admin API (custom_ui): create invited users, initiate auth, forgot password
            cookie_token_service.py
            email_service.py            # SES invitation emails
            invitation_service.py
            rate_limiter_service.py
            session_service.py
            space_service.py
            tenant_service.py
            user_management_service.py
            user_service.py

### 1.2 Backend integration and migration files

    backend/
      app/
        main.py                         # FastAPI app, middleware, router mount
        config.py                       # Host settings (CORS, env)
        database.py                     # Host DB: engine, SessionLocal, Base, get_db()
      alembic/
        env.py                          # Host migration runner
        versions/                       # 18 migration files (see section 14)

### 1.3 Frontend module structure

    frontend/
      src/
        auth_usermanagement/
          index.js                      # Public exports
          config.js                     # Frontend auth configuration
          constants/
            index.js
            permissions.js
          context/
            AuthProvider.jsx            # Auth state provider (PKCE, refresh, tenant switching)
          hooks/
            useAuth.js
            useCurrentUser.js
            useRole.js
            useSpace.js
            useTenant.js
          services/
            authApi.js                  # Backend API client (axios)
            cognitoClient.js            # Cognito OAuth helpers (PKCE)
            customAuthApi.js            # Custom UI API calls (login, signup, forgot-password, etc.)
          utils/
            errorHandling.js
            index.js
          components/
            AcceptInvitation.jsx
            ConfirmDialog.jsx
            InviteUserModal.jsx
            LoginForm.jsx
            PlatformTenantPanel.jsx
            ProtectedRoute.jsx
            RoleSelector.jsx
            SessionPanel.jsx
            TenantSwitcher.jsx
            Toast.jsx
            UserList.jsx
            CustomLoginForm.jsx         # Custom UI email+password login
            CustomSignupForm.jsx        # Custom UI self-service registration
            ForgotPasswordForm.jsx      # Custom UI password reset flow
            InviteSetPassword.jsx       # Custom UI set-password for invited users
          pages/
            AdminDashboard.jsx
            index.js

---

## 2. Executive Summary

This module is a reusable full-stack auth and user-management system for multi-tenant apps.

What it does in code:
- Cognito JWT authentication and user sync with JWKS TTL cache and key rotation retry.
- Three-layer scope-based RBAC (platform / account / space) driven by YAML config.
- Invitation lifecycle: create, preview, accept, revoke, with hashed tokens and SES email.
- Session lifecycle: register, rotate, list, revoke one, revoke all.
- Cookie-based refresh token flow with CSRF double-submit protection.
- Distributed rate limiting via PostgreSQL-backed hit table.
- Persistent audit events table and structured logging.
- Platform-admin operations for users and tenants.
- Row-level security (PostgreSQL) for tenant isolation.
- Automated cleanup service for expired data (tokens, invitations, rate-limit hits, audit events).
- Dual-mode auth: Cognito Hosted UI (default) or Custom UI with app-owned login/signup/forgot-password forms.
- Cognito AdminUserGlobalSignOut on user suspension.
- Frontend AuthProvider + hooks + admin UI components.

Architecture:
- Backend module plugs into host FastAPI app.
- Frontend module plugs into host React app.
- Host owns root DB runtime and app bootstrap.
- Module owns auth domain logic, routes, models, services, and UI/auth context.

---

## 3. Backend Architecture

### 3.1 Main composition

From backend/app/main.py:
- App creates FastAPI instance.
- App adds CORS middleware.
- App adds security middlewares in this registration order:
  1) TenantContextMiddleware
  2) RateLimitMiddleware
  3) SecurityHeadersMiddleware
- App mounts auth router under configurable prefix (default /auth).

Execution note:
- Starlette middleware execution is reverse of registration order.

### 3.2 Router composition

From backend/app/auth_usermanagement/api/__init__.py:
- Router includes the following route groups:
  - auth_routes
  - tenant_routes
  - config_routes
  - permission_demo_routes
  - invitation_routes
  - tenant_user_routes
  - session_routes
  - space_routes
  - platform_user_routes
  - platform_tenant_routes
  - refresh_token_routes
  - custom_ui_routes

### 3.3 Domain layering

- API layer: HTTP endpoints, request/response wiring.
- Security layer: token verification, tenant context, role guards, middleware.
- Services layer: business logic.
- Models layer: SQLAlchemy entities.
- Schemas layer: Pydantic models for request/response.

---

## 4. Backend Route Inventory

Auth prefix is configurable via AUTH_API_PREFIX (default /auth).

### 4.1 Auth core

From auth_routes.py:
- GET /auth/debug-token
- POST /auth/sync
- GET /auth/me
- GET /auth/me/memberships

### 4.2 Tenant endpoints

From tenant_routes.py:
- POST /auth/tenants
- GET /auth/tenants/my
- GET /auth/tenant-context
- GET /auth/tenants/{tenant_id}
- PATCH /auth/tenants/{tenant_id}
- GET /auth/tenants/{tenant_id}/invitations
- POST /auth/tenants/{tenant_id}/invitations/bulk

### 4.3 Config endpoints

From config_routes.py:
- GET /auth/config/roles
- GET /auth/config/permissions

### 4.4 Invitation endpoints

From invitation_routes.py:
- POST /auth/invite
- POST /auth/tenants/{tenant_id}/invite
- GET /auth/invites/{token}
- DELETE /auth/tenants/{tenant_id}/invites/{token}
- POST /auth/tenants/{tenant_id}/invites/{token}/resend
- POST /auth/tenants/{tenant_id}/invitations/{invitation_id}/resend
- POST /auth/invites/accept

### 4.5 Tenant user management endpoints

From tenant_user_routes.py:
- GET /auth/tenants/{tenant_id}/users (supports ?role= and ?status= query params)
- PATCH /auth/tenants/{tenant_id}/users/{user_id}/role
- DELETE /auth/tenants/{tenant_id}/users/{user_id}
- PATCH /auth/tenants/{tenant_id}/users/{user_id}/deactivate
- PATCH /auth/tenants/{tenant_id}/users/{user_id}/reactivate

### 4.6 Session endpoints

From session_routes.py:
- GET /auth/sessions
- POST /auth/sessions/register
- POST /auth/sessions/{session_id}/rotate
- DELETE /auth/sessions/{session_id}
- DELETE /auth/sessions/all

### 4.7 Space endpoints

From space_routes.py:
- POST /auth/spaces
- GET /auth/spaces/my
- GET /auth/spaces/{space_id}
- PATCH /auth/spaces/{space_id}

### 4.8 Platform admin endpoints

From platform_user_routes.py:
- GET /auth/platform/users (supports ?role= query param)
- PATCH /auth/users/{user_id}/suspend
- PATCH /auth/users/{user_id}/unsuspend
- PATCH /auth/platform/users/{user_id}/promote
- PATCH /auth/platform/users/{user_id}/demote
- DELETE /auth/platform/users/{user_id}
- POST /auth/platform/users/{user_id}/cognito/disable
- POST /auth/platform/users/{user_id}/cognito/enable
- GET /auth/platform/users/{user_id}/cognito
- GET /auth/platform/users/{user_id}
- POST /auth/platform/users/{user_id}/cognito/reset-password

From platform_tenant_routes.py:
- GET /auth/platform/tenants
- PATCH /auth/platform/tenants/{tenant_id}/suspend
- PATCH /auth/platform/tenants/{tenant_id}/unsuspend
- GET /auth/platform/invitations/failed
- GET /auth/platform/audit-events
- POST /auth/platform/cleanup
- DELETE /auth/platform/tenants/{tenant_id}

### 4.9 Cookie and refresh endpoints

From refresh_token_routes.py:
- POST /auth/cookie/store-refresh
- POST /auth/token/refresh
- POST /auth/cookie/clear-refresh

### 4.10 Permission demo endpoints

From permission_demo_routes.py:
- GET /auth/admin/settings
- GET /auth/owner/danger-zone
- GET /auth/member/dashboard
- GET /auth/viewer/reports
- GET /auth/permissions/check

### 4.11 Custom UI endpoints (AUTH_MODE=custom_ui only)

From custom_ui_routes.py (all return 404 when AUTH_MODE != "custom_ui"):
- POST /auth/custom/login
- POST /auth/custom/signup
- POST /auth/custom/confirm
- POST /auth/custom/set-password
- POST /auth/custom/resend-code
- POST /auth/custom/forgot-password
- POST /auth/custom/confirm-forgot-password

---

## 5. Data Model and Security-Critical Fields

### 5.1 Core tables

- users
- tenants
- memberships (scope-based: platform / account / space)
- invitations (scope-targeted)
- sessions
- refresh_token_store
- spaces
- role_definitions
- permission_grants
- rate_limit_hits
- audit_events

### 5.2 Security-relevant columns

users:
- cognito_sub (identity mapping)
- is_platform_admin (global privilege)
- is_active + suspended_at (account lock/suspension)

tenants:
- status (active/suspended)

memberships:
- scope_type (platform/account/space)
- scope_id (UUID reference to the scope entity)
- role_name (from auth_config.yaml)
- status (active/removed/suspended)
- granted_by

invitations:
- token_hash (SHA-256, raw token never stored)
- email, target_scope_type, target_scope_id, target_role_name
- expires_at, accepted_at, revoked_at
- created_by

sessions:
- refresh_token_hash
- user_agent, ip_address, device_info
- expires_at, revoked_at

refresh_token_store:
- cookie_key
- refresh_token
- expires_at

spaces:
- name, account_id (FK to tenants), status

role_definitions:
- role_name, layer, display_name, permissions (JSON array)

permission_grants:
- membership_id, permission

rate_limit_hits:
- key, hit_at

audit_events:
- action (e.g. user_suspended, invitation_accepted, email_send_failed)
- actor_user_id, tenant_id
- target_type, target_id
- ip_address, metadata_json

---

## 6. Security Model

### 6.1 JWT validation

From security/jwt_verifier.py and security/dependencies.py:
- Verifies JWT signature against Cognito JWKS (RS256).
- Validated claims: exp (expiration), token_use (must be "access"), client_id/aud (must match COGNITO_CLIENT_ID).
- JWKS cache with 1-hour TTL, thread-safe double-check locking.
- Key rotation: if a JWT's kid is not in cache, cache is invalidated and re-fetched once. A second miss returns 401 (prevents cache-busting DoS).
- Resolves current user by cognito_sub.
- Rejects suspended users (is_active false).

### 6.2 CSRF double-submit cookie pattern

Protects cookie-based token refresh endpoint (POST /token/refresh):
- Server generates CSRF token (secrets.token_urlsafe(32)), sets as readable (non-HttpOnly) cookie.
- Frontend reads CSRF cookie and sends value in X-CSRF-Token header.
- Server compares cookie value to header value. Mismatches rejected.
- X-Requested-With: XMLHttpRequest header also required.

Cookie attributes:

| Cookie | HttpOnly | Secure | SameSite | Path | Max-Age |
|--------|----------|--------|----------|------|---------|
| Refresh token (authum_refresh_token) | Yes | Yes (prod) | Strict | /auth/token | 30 days |
| CSRF token (authum_csrf_token) | No | Yes (prod) | Strict | / | 30 days |

Secure controlled by COOKIE_SECURE env var (false for local HTTP dev).

### 6.3 Row-level security (PostgreSQL)

- RLS policies on memberships, invitations, sessions, refresh_token_store, spaces, and audit_events keyed on tenant_id.
- Every scoped query sets `SET LOCAL app.current_tenant_id = '<uuid>'` within the transaction.
- Even if application code omits a WHERE tenant_id clause, the database filters rows to the current tenant.
- users table is cross-tenant by design (a user can belong to multiple tenants).
- Platform admin queries bypass tenant scoping intentionally.
- RLS is PostgreSQL-only — SQLite tests skip it. Always run test_row_level_security.py against real PostgreSQL.

### 6.4 Tenant isolation and role enforcement

From security/tenant_middleware.py, security/dependencies.py, security/guards.py:
- Middleware pre-checks X-Tenant-ID / X-Scope-Type / X-Scope-ID and bearer presence for protected routes.
- get_scope_context validates active membership in requested scope.
- Permission guards enforce specific permissions for endpoints.
- Platform admin bypasses all permission checks (ScopeContext.is_super_admin=True).

### 6.5 Refresh token and cookie hardening

From services/cookie_token_service.py and api/refresh_token_routes.py:
- Refresh token stored server-side in refresh_token_store table.
- Cookie is HttpOnly, SameSite=Strict, path-scoped to refresh endpoint.
- CSRF double-submit pattern required for refresh requests.

### 6.6 Session security

From services/session_service.py and api/session_routes.py:
- Stores hashed refresh token per session.
- Supports session rotation (old revoked, new created).
- Supports per-session and global revocation.
- List endpoint for device visibility (user_agent, ip_address, device_info).

### 6.7 Suspended user handling

1. Admin calls PATCH /users/{id}/suspend.
2. is_active set to false in database.
3. AdminUserGlobalSignOut called on Cognito to revoke all refresh tokens.
4. Audit event (user_suspended) recorded.

Token gap: existing access JWT remains valid until expiry (~1 hour), but every protected endpoint calls get_current_user() which checks is_active. Suspended users receive 401 on any API call.

### 6.8 Rate limiting

IP-based rate limiting on sensitive auth endpoints:
- Max requests: 30 per 60-second window per IP+path.
- Protected: /sync, /debug-token, /invite, /invites/accept, /token/refresh, /cookie/store-refresh.
- PostgreSQL backend (distributed, uses rate_limit_hits table) with in-memory fallback.
- Fail-open on database errors to avoid blocking all traffic.

### 6.9 Invitation token security

- Raw token: secrets.token_urlsafe(32) (256-bit entropy).
- Only SHA-256 hash stored in database (token_hash column).
- Email must match authenticated user's email (case-insensitive).
- Invitation must not be expired (default: 2 days), revoked, or already accepted.
- Previous pending invitations for same email+tenant auto-revoked on re-invite.

### 6.10 Security headers

SecurityHeadersMiddleware adds to every response:
- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- Content-Security-Policy: default-src 'self'
- Referrer-Policy: strict-origin-when-cross-origin
- X-XSS-Protection: 0

### 6.11 Audit events

All security-relevant actions logged to audit_events table:
- action, actor_user_id, tenant_id, target_type, target_id, ip_address, metadata_json.
- Events include: user_suspended, user_unsuspended, invitation_accepted, invitation_created, invitation_revoked, email_send_failed, role_changed, tenant_created, tenant_suspended, session_revoked, etc.
- Retained for 365 days by default (configurable via cleanup_service).

---

## 7. Frontend Architecture

### 7.1 Module entry and exports

From frontend/src/auth_usermanagement/index.js:
- Exports AuthProvider, hooks, reusable components, and auth API/service modules.

### 7.2 AuthProvider lifecycle

From context/AuthProvider.jsx:
- Bootstraps from Cognito code callback.
- Exchanges code for tokens via PKCE through cognitoClient.
- Stores refresh token in backend cookie endpoint.
- Registers session metadata on backend.
- Syncs user and loads tenants.
- Handles silent refresh via backend cookie refresh endpoint.
- Rotates/revokes sessions as part of lifecycle/logout paths.
- Stores only tenant and redirect helpers in localStorage; removes legacy token keys.

### 7.3 Frontend API client

From services/authApi.js:
- Central axios client for all auth backend endpoints.
- Supports tenant-aware headers.
- Supports session operations, invitation operations, platform operations, and refresh cookie endpoints.

### 7.4 Cognito integration

From services/cognitoClient.js:
- PKCE code verifier/challenge generation.
- Hosted login/signup URL generation.
- Auth code exchange for tokens.
- Optional deprecated direct refresh function.
- Cognito logout redirect.

### 7.5 UI and authorization behavior

From hooks and components:
- useAuth, useTenant, useRole, useSpace expose context and role semantics.
- ProtectedRoute gates views by auth state and roles.
- AdminDashboard combines user management, platform tenant view, invite flow, and SessionPanel.
- SessionPanel consumes listSessions and revokeSession endpoints.
- TenantSwitcher handles multi-tenant switching with localStorage persistence.
- AcceptInvitation handles invitation acceptance flow (authenticated and unauthenticated states).

---

## 8. Configuration and Environment Variables

### 8.1 Backend variables consumed

From backend/app/auth_usermanagement/config.py:
- COGNITO_REGION
- COGNITO_USER_POOL_ID
- COGNITO_CLIENT_ID
- COGNITO_DOMAIN
- SES_REGION
- SES_SENDER_EMAIL
- FRONTEND_URL
- COOKIE_SECURE
- AUTH_NAMESPACE
- AUTH_API_PREFIX (default /auth, configurable e.g. /v1/auth)
- AUTH_COOKIE_NAME
- AUTH_COOKIE_PATH
- AUTH_CSRF_COOKIE_NAME
- AUTH_CONFIG_PATH (path to auth_config.yaml)
- AUTH_MODE (hosted_ui or custom_ui, default hosted_ui)

From backend/app/database.py:
- DATABASE_URL

From backend/app/config.py:
- CORS_ALLOWED_ORIGINS

### 8.2 Frontend variables consumed

From frontend/src/auth_usermanagement/config.js and services/cognitoClient.js:
- VITE_COGNITO_DOMAIN
- VITE_COGNITO_CLIENT_ID
- VITE_COGNITO_REDIRECT_URI
- VITE_AUTH_NAMESPACE
- VITE_AUTH_API_BASE_PATH
- VITE_AUTH_CALLBACK_PATH
- VITE_AUTH_INVITE_PATH_PREFIX
- VITE_AUTH_CSRF_COOKIE_NAME
- VITE_AUTH_MODE (hosted_ui or custom_ui, default hosted_ui)

### 9.1 Host-owned runtime

The host app is the source of truth for:
- engine
- SessionLocal
- Base
- get_db

This is enforced by backend/app/auth_usermanagement/database.py, which is a transitional compatibility layer importing from backend/app/database.py (no module-local create_engine or sessionmaker in auth module).

### 9.2 Module-owned runtime behavior

The module owns:
- auth models, schemas, API routes, security dependencies, middleware, services, and migrations.

### 9.3 Migration ownership

- Module provides migration scripts.
- Host executes them through host Alembic pipeline.

---

## 10. What Must Be Shipped to Use This Module in a Host App

### 10.1 Backend shipping unit (required)

Ship these directories/files:
- backend/app/auth_usermanagement (entire directory)
- backend/alembic/versions auth-related migration files
- backend/app/database.py equivalent host DB runtime file
- backend/app/main.py wiring (or equivalent integration in your host app entrypoint)
- backend/requirements.txt dependencies required by auth module

Minimum host wiring:
- Include auth router under configured auth prefix.
- Register tenant middleware, rate limit middleware, and security headers middleware.
- Ensure rate limiter gets host DB factory if distributed mode is required.
- Ensure get_db dependency is host-owned and shared with module dependencies.

### 10.2 Frontend shipping unit (required)

Ship:
- frontend/src/auth_usermanagement (entire directory)

Minimum host wiring:
- Wrap app with AuthProvider.
- Use ProtectedRoute for restricted pages.
- Configure callback route and invitation route.
- Provide environment variables for Cognito and auth config.

### 10.3 Infrastructure requirements

Backend:
- PostgreSQL database reachable from backend.
- DATABASE_URL configured.
- Cognito user pool + app client + domain configured.
- Cookie secure behavior matched to environment (https in production).
- Run Alembic migrations to latest head.

Frontend:
- Correct redirect URI and callback path for Cognito.
- Auth API base path matching backend route mount.

### 10.4 Operational items (recommended)

- Schedule cleanup_service.run_cleanup() via cron or Celery (nightly recommended).
- Centralized logging and monitoring.
- Backup/retention policy for audit_events table.
- RLS test execution in CI using PostgreSQL profile.

---

## 11. Backend and Frontend Flows (End-to-End)

### 11.1 Login and sync

1. Frontend opens Cognito Hosted UI with PKCE.
2. Frontend receives code on callback.
3. Frontend exchanges code for tokens.
4. Frontend stores refresh token via backend cookie endpoint.
5. Frontend registers session metadata via /auth/sessions/register.
6. Frontend calls /auth/sync to create/update local user.
7. Frontend calls /auth/me and /auth/tenants/my.

### 11.2 Refresh flow

1. Frontend calls /auth/token/refresh with X-Requested-With and X-CSRF-Token.
2. Backend validates CSRF and cookie key.
3. Backend exchanges refresh token against Cognito.
4. Backend rotates stored refresh token if Cognito returns one.
5. Frontend updates in-memory access/id tokens.

### 11.3 Invitation flow

1. Admin creates invitation via /auth/invite or /auth/tenants/{id}/invite.
2. Backend stores invitation with token_hash (SHA-256), 2-day expiry.
3. Email service attempts SES send. On failure, logs email_send_failed audit event.
4. Recipient previews via /auth/invites/{token}.
5. Recipient accepts via /auth/invites/accept.
6. Backend creates/reactivates membership with role guardrails.

### 11.4 Session management flow

1. Register session when refresh token is first acquired.
2. Rotate session when refresh token rotation occurs.
3. Revoke one session or all sessions from settings/admin UI.
4. List sessions through /auth/sessions for device visibility.

### 11.5 User suspension flow

1. Admin calls PATCH /users/{id}/suspend.
2. is_active set to false, suspended_at timestamp recorded.
3. AdminUserGlobalSignOut called on Cognito (revokes all refresh tokens).
4. Audit event user_suspended logged.
5. All subsequent API calls return 401 via get_current_user() check.

---

## 12. Test Coverage

### Backend (597 tests, 95% coverage, 6 skipped RLS tests without PostgreSQL)

- DB ownership boundary and guardrail tests
- Scope context and permission guard tests
- Cookie token service and endpoint tests
- Rate limit middleware and service tests
- Invitation service tests (including scoped invitations)
- Session service and API tests
- Tenant isolation and middleware tests
- Platform tenant and user API tests
- User management and suspension tests
- Audit service tests
- Membership backfill tests
- Config loader and config routes API tests
- Cleanup service tests (9 tests)
- JWT verifier tests
- Custom UI auth tests (login, signup, set-password, forgot-password, Cognito admin service)
- Cognito admin operations tests
- API prefix versioning test
- Auth routes API and e2e lifecycle tests
- Cross-feature integration tests
- Email service tests
- Security headers middleware tests
- Space service and space routes API tests
- Tenant detail API and TrustOS gap feature tests
- Context model tests
- Row-level security tests (PostgreSQL-only, 6 tests)
- **Real Cognito integration tests** (28 tests, gated by `RUN_COGNITO_TESTS=1`) — live user pool CRUD, JWT verification, invitation flows, full auth round-trip
- **Mock Cognito service flow tests** (43 tests) — all `cognito_admin_service` functions with mocked boto3
- **Route-level integration tests** (51 tests) — invitation, space, tenant-user, session, auth, and platform routes

### Frontend (57 tests across 10 files)

- config.test.js — AUTH_CONFIG defaults and overrides
- cognitoClient.test.js — PKCE flow, login URL, code exchange
- authApi.test.js — API client, tenant headers, CSRF
- TenantSwitcher.test.jsx — tenant switching behavior
- AcceptInvitation.test.jsx — invitation acceptance flow
- useAuth.test.jsx — hook state and logout
- UserList.test.jsx — list rendering
- AdminDashboard.test.jsx — dashboard composition

### Test commands

```bash
# Standard unit tests (SQLite)
cd backend && pytest -q tests

# Real Cognito integration tests (requires .env with valid Cognito config + AWS credentials)
RUN_COGNITO_TESTS=1 pytest -q tests/test_cognito_integration.py

# PostgreSQL RLS verification
RUN_POSTGRES_RLS_TESTS=1 DATABASE_URL=postgresql://rls_tester:pw@host:5432/db pytest -q tests/test_row_level_security.py

# Coverage report
pytest -q tests --cov=app.auth_usermanagement --cov-report=term-missing

# Frontend
cd frontend && npx vitest run
```

---

## 13. Scope and Permission System

### Three-layer hierarchy

```
platform (super_admin only)
  └── account (organization/tenant)
       └── space (sub-grouping within an account)
```

### Permission resolution

Request headers (X-Scope-Type + X-Scope-ID)
→ get_scope_context() dependency
→ Query memberships WHERE user_id + scope_type + scope_id + status=active
→ For each role: auth_config.permissions_for_role(role_name) → set of permissions
→ Guard checks: has_permission("members:manage") → bool

### auth_config.yaml roles and permissions

```yaml
version: "3.0"
roles:
  platform:
    - super_admin: [platform:configure, accounts:manage, users:suspend]
  account:
    - account_owner: [account:delete, account:read, spaces:create, members:manage, members:invite]
    - account_admin: [account:read, spaces:create, members:invite]
    - account_member: [account:read]
  space:
    - space_admin: [space:delete, space:configure, space:read, members:manage, members:invite, data:read, data:write]
    - space_member: [space:read, data:read, data:write]
    - space_viewer: [space:read, data:read]
```

### Space inheritance

When scope_type=space, parent account memberships are checked:
- account_owner / account_admin → inherits space_admin
- account_member → inherits value of inheritance.account_member_space_access (default: none)

---

## 14. Alembic Migration Chain

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

## 15. Operational: Cleanup Service

cleanup_service.run_cleanup() purges expired data. Schedule via cron or Celery.

| Data | Default Retention | Config Parameter |
|------|-------------------|-----------------|
| Expired refresh tokens | Immediate (past expires_at) | — |
| Expired/revoked invitations | 30 days | invitation_days |
| Rate-limit hit records | 24 hours | rate_limit_hours |
| Audit events | 365 days | audit_retention_days (0 = skip) |

Verified against PostgreSQL 17.6 on AWS RDS.

---

## 16. Caveats and Known Risks

1. CORS is host-configured via CORS_ALLOWED_ORIGINS. Risk is operational misconfiguration across environments.

2. tenant_middleware route skip list is explicit. Route additions must stay aligned with dependency enforcement.

3. JWKS cache is in-process (1-hour TTL). Multi-process deployments each maintain their own cache.

4. Cleanup_service handles expired data retention. Must be scheduled externally (cron/Celery).

5. Module is reusable by source inclusion. No pip package metadata exists for install/publish workflow.

6. Deprecated guards (require_role, require_min_role, TenantContext) scheduled for removal after 2026-05-20. Use require_permission() and get_scope_context() instead.

7. Owner role assignment restricted. update_membership_role() rejects account_owner assignment; ownership transfer requires a dedicated flow.

---

## 17. Change History

### Initial Release — 2026-03-18

- Core auth module with Cognito PKCE, JWT verification, multi-tenant model, invitation system, user suspension, RLS.
- Frontend module: AuthProvider, hooks, admin UI components.

### v2 Updates — 2026-03-19

- Cookie-based token refresh with CSRF double-submit pattern.
- refresh_token_store table, cookie endpoints.
- Rate limiting middleware (PostgreSQL-backed, in-memory fallback).
- Audit event system (audit_events table).
- Invitation token hashing (SHA-256).
- Session management with device tracking.
- Security headers middleware.

### v3 Updates — 2026-03-20

- Three-layer scope-based RBAC (platform / account / space) driven by auth_config.yaml.
- role_definitions and permission_grants tables populated from YAML config.
- spaces table for sub-tenant grouping.
- ScopeContext model replacing TenantContext.
- Scope-aware guards: require_permission(), require_any_permission(), require_all_permissions().
- Scope-aware middleware: X-Scope-Type/X-Scope-ID header validation.
- Scope-extended invitations: target_scope_type, target_scope_id, target_role_name.
- Membership schema replaced: scope_type, scope_id, role_name columns instead of single role string.
- Config endpoints: GET /config/roles, GET /config/permissions.
- Membership backfill migration for existing data.
- Updated RLS policies for scope-based isolation.

### Production Readiness — 2026-03-23

- Fixed datetime.utcnow() deprecation in 4 model files (replaced with datetime.now(UTC)).
- JWKS cache: added 1-hour TTL with thread-safe double-check locking and single-retry key rotation.
- Owner role restriction: update_membership_role() rejects account_owner assignment.
- Removed legacy trustos_* localStorage keys from 4 frontend files.
- Cleanup service: automated purging of expired tokens, invitations, rate-limit hits, audit events.
- SES failure visibility: email_send_failed audit event; GET /platform/invitations/failed endpoint.
- Cognito AdminUserGlobalSignOut on user suspension.
- Docker support: Dockerfile, docker-compose.yml (PostgreSQL + backend + frontend).
- Frontend test suite: 57 tests across 10 files.
- API versioning: AUTH_API_PREFIX configurable (e.g. /v1/auth).
- RLS verified on PostgreSQL 17.6 (AWS RDS) with non-superuser role.
- Cleanup service verified against real PostgreSQL data.
- 261 backend tests passing (SQLite), 262 on PostgreSQL.

### Custom UI — 2026-03-28

- Dual-mode auth via AUTH_MODE env var: "hosted_ui" (default, Cognito redirect) or "custom_ui" (app-owned forms).
- Backend: cognito_admin_service.py (Cognito Admin API proxy), custom_ui_routes.py (7 endpoints gated by AUTH_MODE).
- Endpoints: /custom/login, /custom/signup, /custom/confirm, /custom/set-password, /custom/resend-code, /custom/forgot-password, /custom/confirm-forgot-password.
- Frontend: CustomLoginForm, CustomSignupForm, InviteSetPassword, ForgotPasswordForm components; customAuthApi.js service.
- Tenant middleware updated: /auth/custom/* paths skip tenant header validation (pre-authentication endpoints).
- CSRF cookie path changed from /auth/token to / (JS must read from any page URL).
- Frontend role recognition updated for v3.0 names (account_owner, account_admin, account_member) alongside legacy names.
- Cognito requires ALLOW_USER_PASSWORD_AUTH enabled on app client for custom_ui mode.
- 475 backend tests passing (SQLite), 476 on PostgreSQL.

### Integration Tests & Coverage — 2026-03-29

- Added `test_cognito_integration.py`: 28 real Cognito integration tests hitting live user pool (gated by `RUN_COGNITO_TESTS=1`).
  - Tests: user CRUD, disable/enable, auth flows, JWT verification, invitation lifecycle, full auth round-trip via HTTP endpoints.
- Added `test_cognito_service_flows.py`: 43 mock-based unit tests for all `cognito_admin_service` functions.
- Added `test_route_integration.py`: 51 route-level integration tests covering invitation, space, tenant-user, session, auth, and platform routes.
- Coverage: 95% (2962 statements, 155 missed) across `app.auth_usermanagement`.
- 597 backend tests passing (SQLite), 6 skipped (RLS requires PostgreSQL), 28 skipped without `RUN_COGNITO_TESTS=1`.

### Code Quality & Logging — 2026-03-28

- Fixed all Pydantic v2 deprecations: migrated `class Config:` to `model_config = ConfigDict(...)` / `SettingsConfigDict(...)` across all schemas and config files.
- Fixed `datetime.utcnow()` deprecation in models and tests (replaced with timezone-aware helper).
- Added structured JSON logging via `logging_config.py` (auto-configured on module import, uses `python-json-logger`).
- Rate limiter now supports persistent PostgreSQL storage when `get_db=SessionLocal` is passed to `RateLimitMiddleware`.
- Added `python-json-logger==2.0.7` to `requirements.txt`.
- 475 backend tests passing at this point (before integration test additions).

---

## 18. Final Assessment

The codebase implements a production-ready auth/user-management module for multi-tenant FastAPI + React apps. All security controls, data retention, and tenant isolation have been verified.

Readiness strengths:
- Three-layer scope-based RBAC with YAML-driven permissions.
- Dual-mode auth: Cognito Hosted UI or Custom UI with app-owned forms.
- Cookie-based refresh with CSRF hardening.
- Session lifecycle and audit persistence.
- PostgreSQL RLS verified on real infrastructure.
- Automated cleanup for all ephemeral data.
- Comprehensive test coverage — 597 backend tests (95% coverage), 57 frontend tests.

Host-integration responsibilities:
- Provide host DB runtime ownership (engine, SessionLocal, Base, get_db).
- Execute Alembic migrations.
- Provide environment config and middleware wiring.
- Schedule cleanup service.
- Configure production infra (CORS, HTTPS cookies, monitoring).

This report reflects code behavior as of 2026-03-29.

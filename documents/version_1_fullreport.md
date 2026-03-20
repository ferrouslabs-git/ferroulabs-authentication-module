# Version 1 Full Report: Auth and User Management

Date: 2026-03-18  
Scope: backend + frontend auth_usermanagement module  
Source of truth: code only (no assumptions from planning docs)

---

## 1. Folder Structure (Start Here)

### 1.1 Backend module structure

    backend/
      app/
        auth_usermanagement/
          __init__.py
          config.py
          database.py
          api/
            __init__.py
            auth_routes.py
            invitation_routes.py
            permission_demo_routes.py
            platform_tenant_routes.py
            platform_user_routes.py
            refresh_token_routes.py
            route_helpers.py
            session_routes.py
            tenant_routes.py
            tenant_user_routes.py
          models/
            __init__.py
            audit_event.py
            invitation.py
            membership.py
            rate_limit_hit.py
            refresh_token.py
            session.py
            tenant.py
            user.py
          schemas/
            __init__.py
            invitation.py
            session.py
            tenant.py
            token.py
            user_management.py
          security/
            __init__.py
            dependencies.py
            guards.py
            jwt_verifier.py
            rate_limit_middleware.py
            security_headers_middleware.py
            tenant_context.py
            tenant_middleware.py
          services/
            __init__.py
            audit_service.py
            cookie_token_service.py
            email_service.py
            invitation_service.py
            rate_limiter_service.py
            session_service.py
            tenant_service.py
            user_management_service.py
            user_service.py

### 1.2 Backend integration and migration files that affect module behavior

    backend/
      app/
        main.py
        database.py
      alembic/
        versions/
          d3494139f54d_create_auth_tables.py
          7a454a9250b1_add_user_suspension_fields.py
          0eec64567dac_enable_row_level_security.py
          8c5f69f3b5d1_add_session_metadata_fields.py
          f1c2d3e4a5b6_add_refresh_token_store_table.py
          2a9b67c1d3ef_add_invitation_revoked_at.py
          4f2a1e9c7b10_force_rls_on_tenant_tables.py
          5b3c4d2e8f9a_add_rate_limit_hits_table.py
          6c5d7e4f8a2b_add_token_hash_to_invitations.py
          9f2e1c7a4b3d_add_audit_events_table.py

### 1.3 Frontend module structure

    frontend/
      src/
        auth_usermanagement/
          index.js
          config.js
          config.test.js
          constants/
            index.js
            permissions.js
          context/
            AuthProvider.jsx
          hooks/
            useAuth.js
            useCurrentUser.js
            useRole.js
            useTenant.js
          services/
            authApi.js
            cognitoClient.js
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
            UserList.test.jsx
          pages/
            AdminDashboard.jsx
            AdminDashboard.test.jsx
            index.js

---

## 2. Executive Summary

This module is a reusable full-stack auth and user-management system for multi-tenant apps.

What it already does in code:
- Cognito JWT authentication and user sync.
- Tenant-aware RBAC with owner/admin/member/viewer roles.
- Invitation lifecycle: create, preview, accept, revoke.
- Session lifecycle: register, rotate, list, revoke one, revoke all.
- Cookie-based refresh token flow with CSRF protection.
- Distributed rate limiting via PostgreSQL-backed hit table.
- Persistent audit events table and logging.
- Platform-admin operations for users and tenants.
- Frontend AuthProvider + hooks + admin UI components.

Current architecture style:
- Backend module plugs into host FastAPI app.
- Frontend module plugs into host React app.
- Host owns root DB runtime and app bootstrap.
- Module owns auth domain logic, routes, models, services, and UI/auth context.

---

## 3. Backend Architecture Explained

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
  - permission_demo_routes
  - invitation_routes
  - tenant_user_routes
  - session_routes
  - platform_user_routes
  - platform_tenant_routes
  - refresh_token_routes

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

### 4.2 Tenant endpoints

From tenant_routes.py:
- POST /auth/tenants
- GET /auth/tenants/my
- GET /auth/tenant-context

### 4.3 Invitation endpoints

From invitation_routes.py:
- POST /auth/invite
- POST /auth/tenants/{tenant_id}/invite
- GET /auth/invites/{token}
- DELETE /auth/tenants/{tenant_id}/invites/{token}
- POST /auth/invites/accept

### 4.4 Tenant user management endpoints

From tenant_user_routes.py:
- GET /auth/tenants/{tenant_id}/users
- PATCH /auth/tenants/{tenant_id}/users/{user_id}/role
- DELETE /auth/tenants/{tenant_id}/users/{user_id}

### 4.5 Session endpoints

From session_routes.py:
- GET /auth/sessions
- POST /auth/sessions/register
- POST /auth/sessions/{session_id}/rotate
- DELETE /auth/sessions/{session_id}
- DELETE /auth/sessions/all

### 4.6 Platform admin endpoints

From platform_user_routes.py:
- GET /auth/platform/users
- PATCH /auth/users/{user_id}/suspend
- PATCH /auth/users/{user_id}/unsuspend
- PATCH /auth/platform/users/{user_id}/promote
- PATCH /auth/platform/users/{user_id}/demote

From platform_tenant_routes.py:
- GET /auth/platform/tenants
- PATCH /auth/platform/tenants/{tenant_id}/suspend
- PATCH /auth/platform/tenants/{tenant_id}/unsuspend

### 4.7 Cookie and refresh endpoints

From refresh_token_routes.py:
- POST /auth/cookie/store-refresh
- POST /auth/token/refresh
- POST /auth/cookie/clear-refresh

### 4.8 Permission demo endpoints

From permission_demo_routes.py:
- GET /auth/admin/settings
- GET /auth/owner/danger-zone
- GET /auth/member/dashboard
- GET /auth/viewer/reports
- GET /auth/permissions/check

---

## 5. Data Model and Security-Critical Fields

### 5.1 Core tables

From models:
- users
- tenants
- memberships
- invitations
- sessions
- refresh_token_store
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
- role (owner/admin/member/viewer)
- status (active/suspended)

invitations:
- token and token_hash
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

rate_limit_hits:
- key and hit_at for distributed rate limiting

audit_events:
- action
- actor_user_id
- tenant_id
- target_type/target_id
- metadata_json

---

## 6. Security Controls (Code-Implemented)

### 6.1 Authentication and token verification

From security/jwt_verifier.py and security/dependencies.py:
- Verifies JWT signature against Cognito JWKS.
- Validates bearer token extraction.
- Resolves current user by cognito_sub.
- Rejects suspended users (is_active false).

### 6.2 Tenant isolation and role enforcement

From security/tenant_middleware.py, security/dependencies.py, security/guards.py:
- Middleware pre-checks X-Tenant-ID and bearer presence for protected tenant routes.
- get_tenant_context validates active membership in requested tenant.
- Role guards enforce minimum role for endpoints.
- Platform admin can bypass role checks where explicitly allowed.

### 6.3 Refresh token and CSRF hardening

From services/cookie_token_service.py and api/refresh_token_routes.py:
- Refresh token moved to HttpOnly cookie flow.
- Cookie is SameSite strict and path-scoped.
- Refresh requires X-Requested-With and CSRF double-submit token.

### 6.4 Session security

From services/session_service.py and api/session_routes.py:
- Stores hashed refresh token for session records.
- Supports session rotation (old revoked, new created).
- Supports per-session and global revocation.
- Exposes list endpoint for device visibility.

### 6.5 Rate limiting

From security/rate_limit_middleware.py and services/rate_limiter_service.py:
- Rate limit on auth-sensitive routes.
- Uses PostgreSQL table for distributed enforcement if DB factory provided.
- Falls back to in-memory limiter when DB factory not provided.

### 6.6 Security headers

From security/security_headers_middleware.py:
- Sets CSP, X-Frame-Options, X-Content-Type-Options, COOP/CORP, permissions policy, referrer policy.

### 6.7 Audit logging

From services/audit_service.py:
- Emits structured log events.
- Persists audit events in audit_events table when db session is passed.
- Call sites across tenant, session, invitation, and platform routes use db-backed persistence.

---

## 7. Frontend Architecture Explained

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
- useAuth, useTenant, useRole expose context and role semantics.
- ProtectedRoute gates views by auth state and roles.
- AdminDashboard combines user management, platform tenant view, invite flow, and SessionPanel.
- SessionPanel consumes listSessions and revokeSession endpoints.

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
- AUTH_API_PREFIX
- AUTH_COOKIE_NAME
- AUTH_COOKIE_PATH
- AUTH_CSRF_COOKIE_NAME

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

---

## 9. Database Ownership and Host Contract

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

This section is the direct shipping checklist requested.

### 10.1 Backend shipping unit (required)

Ship these directories/files:
- backend/app/auth_usermanagement (entire directory)
- backend/alembic/versions auth-related migration files
- backend/app/database.py equivalent host DB runtime file
- backend/app/main.py wiring (or equivalent integration in your host app entrypoint)
- backend/requirements.txt dependencies required by auth module

Minimum host wiring to ship:
- Include auth router under configured auth prefix.
- Register tenant middleware, rate limit middleware, and security headers middleware.
- Ensure rate limiter gets host DB factory if distributed mode is required.
- Ensure get_db dependency is host-owned and shared with module dependencies.

### 10.2 Frontend shipping unit (required)

Ship these directories/files:
- frontend/src/auth_usermanagement (entire directory)

Minimum host wiring to ship:
- Wrap app with AuthProvider.
- Use ProtectedRoute for restricted pages.
- Configure callback route and invitation route.
- Provide environment variables for Cognito and auth config.

### 10.3 Infra and environment to ship (required)

Backend:
- PostgreSQL database reachable from backend.
- DATABASE_URL configured.
- Cognito user pool + app client + domain configured.
- Cookie secure behavior matched to environment (https in production).
- Run Alembic migrations to latest head.

Frontend:
- Correct redirect URI and callback path for Cognito.
- Auth API base path matching backend route mount.

### 10.4 Operational items to ship (recommended)

- Centralized logging and monitoring.
- Backup/retention policy for audit_events table.
- Cleanup policy for refresh token store and old sessions.
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
2. Backend stores invitation with token and token_hash, 2-day expiry.
3. Email service attempts SES send (if configured).
4. Recipient previews via /auth/invites/{token}.
5. Recipient accepts via /auth/invites/accept.
6. Backend creates/reactivates membership with role guardrails.

### 11.4 Session management flow

1. Register session when refresh token is first acquired.
2. Rotate session when refresh token rotation occurs.
3. Revoke one session or all sessions from settings/admin UI.
4. List sessions through /auth/sessions for device visibility.

---

## 12. Test Coverage Snapshot (From Codebase)

Backend tests include:
- DB ownership boundary and guardrail tests.
- Guards and permission tests.
- Cookie token service and endpoint tests.
- Rate limit middleware tests.
- Invitation service tests.
- Session service/API tests.
- Tenant isolation/middleware tests.
- Platform tenant API tests.
- User management and suspension tests.
- Audit service tests.
- Row-level security tests (PostgreSQL-gated).

Frontend tests present:
- config.test.js
- UserList.test.jsx
- AdminDashboard.test.jsx

Observed posture:
- Backend coverage for core auth domain is broad.
- Frontend coverage exists but is lighter than backend.

---

## 13. Current Caveats and Risks Seen in Code

1) CORS is now host-configured via CORS_ALLOWED_ORIGINS.
- Risk is operational misconfiguration (missing/wrong origins) across environments, not hardcoding.

2) tenant_middleware route skip list is explicit and broad.
- Works, but route additions must stay aligned with dependency enforcement.

3) Cognito JWKS fetch is cached in-process.
- Operational strategy should account for key rotation and process restarts.

4) Session and refresh-token data retention.
- Expired rows are cleaned on access path, but a scheduled cleanup job is still advisable for production scale.

5) Auth module packaging.
- Module is reusable by source inclusion today; there is no backend package metadata for install/publish workflow in this module folder.

---

## 14. Host-App Shipping Manifest (Practical)

Use this as a release gate before integrating in a new host app.

Required backend:
- app/auth_usermanagement directory.
- host app/database runtime and get_db.
- alembic migrations applied to target DB.
- middleware + router wiring in host app startup.
- environment variables for Cognito, database, cookie behavior.

Required frontend:
- src/auth_usermanagement directory.
- AuthProvider wrapping app root.
- callback route and protected routes wired.
- Vite env variables for Cognito and auth namespace/api paths.

Required validation before ship:
- Backend tests pass (including PostgreSQL RLS test run when applicable).
- Frontend login, refresh, invite accept, role-limited route access validated.
- Session list and revoke behavior validated from UI.

---

## 15. Final Assessment

The codebase currently implements a strong Version 1 auth/user-management module with both backend and frontend integration layers. It is already functional for host reuse when wired correctly to host DB/runtime and Cognito config.

Primary readiness strengths:
- Multi-tenant RBAC and tenant context path are implemented.
- Refresh-cookie + CSRF hardening is in place.
- Session lifecycle and audit persistence are implemented.
- Platform admin operations are available.

Primary host-integration responsibilities:
- Provide host DB runtime ownership.
- Execute migrations.
- Provide environment config and app wiring.
- Configure production infra concerns (CORS, cleanup jobs, monitoring, secure deployment).

This report reflects code behavior as of this date and should be updated whenever endpoint contracts, middleware order, or migration heads change.

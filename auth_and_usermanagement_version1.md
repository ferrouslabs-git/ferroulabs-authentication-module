# Auth and User Management - Version 1 (Code-Based Evaluation)

This document is generated from source code only (backend and frontend implementation), without relying on documentation files.

## 1) What This Module Is

A reusable multi-tenant authentication and user-management module built around:
- FastAPI backend routes mounted under a configurable auth prefix (default `/auth`)
- AWS Cognito JWT verification for authentication
- Tenant-aware authorization using role guards and tenant context
- User/tenant administration for both tenant admins and platform admins
- Session + refresh-token lifecycle support (server-stored refresh token keys, HttpOnly cookies)

## 2) Core Capabilities

### Authentication and identity
- Cognito token verification (access/id token support)
- User sync from Cognito into local `users` table
- Current user profile endpoint

### Multi-tenancy and role-based access
- Tenant creation and tenant membership discovery (`/tenants`, `/tenants/my`)
- Tenant context resolution via `X-Tenant-ID` and role guards
- Role hierarchy (`owner > admin > member > viewer`)
- Platform admin bypass for tenant role checks
- PostgreSQL session-level RLS context variables are set in dependency path

### User management
- Tenant-scoped user listing
- Tenant-scoped role updates and user removal
- Platform-wide user listing
- Platform-admin account suspension/unsuspension
- Platform-admin promote/demote to platform admin
- Platform tenant list and tenant suspend/unsuspend

### Invitation workflow
- Create invite token (implicit current tenant or explicit tenant path)
- Invitation preview by token
- Invitation accept for authenticated user with email match enforcement
- Invitation revoke support
- Best-effort SES email delivery for invitation links

### Session and refresh token lifecycle
- Register session with metadata (user agent, IP, device info)
- Rotate session refresh token hash linkage
- Revoke one/all sessions
- Store refresh token server-side and expose only opaque cookie key in HttpOnly cookie
- Refresh access token via backend proxy endpoint
- Clear refresh cookie and revoke stored refresh key

### Security middleware and hardening
- Tenant precheck middleware (header/auth checks for protected auth routes)
- In-memory rate limiting for auth-sensitive routes
- Security headers middleware (CSP, frame options, no sniff, etc.)

## 3) Backend Endpoints (Default Prefix: `/auth`)

All paths below are relative to configured prefix `AUTH_API_PREFIX` (default `/auth`).

### Auth
- `GET /auth/debug-token`
- `POST /auth/sync`
- `GET /auth/me`

### Tenant
- `POST /auth/tenants`
- `GET /auth/tenants/my`
- `GET /auth/tenant-context`

### Tenant users
- `GET /auth/tenants/{tenant_id}/users`
- `PATCH /auth/tenants/{tenant_id}/users/{user_id}/role`
- `DELETE /auth/tenants/{tenant_id}/users/{user_id}`

### Invitations
- `POST /auth/invite`
- `POST /auth/tenants/{tenant_id}/invite`
- `GET /auth/invites/{token}`
- `POST /auth/invites/accept`
- `DELETE /auth/tenants/{tenant_id}/invites/{token}`

### Sessions
- `POST /auth/sessions/register`
- `POST /auth/sessions/{session_id}/rotate`
- `DELETE /auth/sessions/{session_id}`
- `DELETE /auth/sessions/all`

### Platform user administration
- `GET /auth/platform/users`
- `PATCH /auth/users/{user_id}/suspend`
- `PATCH /auth/users/{user_id}/unsuspend`
- `PATCH /auth/platform/users/{user_id}/promote`
- `PATCH /auth/platform/users/{user_id}/demote`

### Platform tenant administration
- `GET /auth/platform/tenants`
- `PATCH /auth/platform/tenants/{tenant_id}/suspend`
- `PATCH /auth/platform/tenants/{tenant_id}/unsuspend`

### Refresh token cookie/token proxy
- `POST /auth/cookie/store-refresh`
- `POST /auth/token/refresh`
- `POST /auth/cookie/clear-refresh`

### Permission demo/test routes
- `GET /auth/admin/settings`
- `GET /auth/owner/danger-zone`
- `GET /auth/member/dashboard`
- `GET /auth/viewer/reports`
- `GET /auth/permissions/check`

## 4) Frontend Components and Module Surface

## Exported from module index

### Context
- `AuthProvider`

### Hooks
- `useAuth`
- `useCurrentUser`
- `useTenant`
- `useRole`

### Components/pages
- `LoginForm`
- `ProtectedRoute`
- `TenantSwitcher`
- `RoleSelector`
- `InviteUserModal`
- `UserList`
- `AcceptInvitation`
- `ToastProvider`
- `AdminDashboard`
- `PlatformTenantPanel` (used inside dashboard)
- `ConfirmDialog` (used for destructive confirmations)

### Service APIs
- `authApi` namespace (backend endpoint wrappers)
- `cognitoClient` namespace (Hosted UI login/signup, PKCE, code exchange, logout)

### Frontend configuration
- `AUTH_CONFIG` with configurable:
  - `VITE_AUTH_NAMESPACE`
  - `VITE_AUTH_API_BASE_PATH`
  - `VITE_AUTH_CALLBACK_PATH`
  - `VITE_AUTH_INVITE_PATH_PREFIX`

## 5) Permission Matrix (Effective Behavior)

Matrix combines backend guards and frontend permission constants:

| Action | owner | admin | member | viewer | platform_admin |
|---|---|---|---|---|---|
| View tenant users (`GET /tenants/{id}/users`) | Yes | Yes | Yes | No | Yes |
| Invite users (`POST /invite`) | Yes | Yes | No | No | Yes (tenant context still needed for tenant-scoped invite flow) |
| Update tenant user role | Yes | Yes (cannot elevate to owner over owner constraints) | No | No | Yes |
| Remove tenant user | Yes | Yes | No | No | Yes |
| View platform users | No | No | No | No | Yes |
| Suspend/unsuspend user account | No | No | No | No | Yes |
| Promote/demote platform admin | No | No | No | No | Yes |
| View/suspend/unsuspend tenants platform-wide | No | No | No | No | Yes |

Notes:
- Tenant guard hierarchy is strict backend source-of-truth.
- Platform admin bypasses tenant role checks in guard layer.
- Frontend permission constants include `SUSPEND_USERS` for tenant roles, but backend enforces suspend/unsuspend as platform-admin-only.

## 6) What Is Missing for a Strong Version 1

The current module is solid for core auth + tenant user management, but these are notable gaps for a production-grade V1:

1. Durable distributed rate limiting
- Current limiter is in-memory per-process only (not Redis/distributed).

2. CSRF-strengthened cookie refresh flow
- Refresh endpoint currently relies on `X-Requested-With` header, not a full CSRF token strategy.

3. Invitation management completeness
- No list/search endpoint for active invitations.
- No resend invitation endpoint.

4. Audit persistence/reporting
- Audit events are logged to app logs, not persisted in a queryable audit table with retention policy.

5. Security operations controls
- No IP/device anomaly detection.
- No configurable account lockout / adaptive risk policy.

6. Account recovery UX/API integration coverage
- Hosted UI handles auth basics, but module-level flows for recovery/verification state are not exposed as first-class API/UI controls.

7. Operational observability
- No explicit metrics/tracing contract in code for auth latencies, refresh failures, invite acceptance funnel, and permission-denied rate.

8. Consistency gap in permission signaling
- Frontend tenant permission constant suggests suspend capability for tenant roles, but backend restricts to platform admin only; this should be aligned to avoid operator confusion.

## 7) Quick Verdict

This is a capable reusable V1 foundation for:
- Multi-tenant auth
- Role-based tenant user management
- Invite onboarding
- Platform admin controls

To harden for broader production adoption, prioritize distributed controls (rate limiting, audit storage, observability), CSRF robustness, and invitation lifecycle completeness.

## 8) Required Follow-Ups You Raised (Status + Action)

This section explicitly addresses your review points and whether each item is required in this codebase.

### 1. Refresh Token CSRF Risk
Status: Required (high priority).

Current state:
- `/auth/token/refresh` requires `X-Requested-With: XMLHttpRequest`.
- Refresh flow uses cookie transport, so header-only CSRF signaling is not sufficient as a primary control.

Action:
- Add double-submit CSRF protection:
  - Set non-HttpOnly `csrf_token` cookie.
  - Require matching `X-CSRF-Token` header on cookie-auth endpoints.
- Keep `SameSite=Strict` and `Secure` as defense-in-depth.

### 2. In-Memory Rate Limiting
Status: Required for multi-instance production.

Current state:
- Rate limiter is process-local in memory.

Action:
- Replace with Redis-backed distributed limiter.
- Prioritize strict limits on:
  - `/auth/token/refresh`
  - `/auth/sync`
  - `/auth/invites/accept`

### 3. Invitation Token Security Properties
Status: Partially compliant, partially required.

Current state:
- Randomness: strong (`token_urlsafe(32)`, effectively high entropy).
- Single-use: implemented via accepted/revoked/expired checks.
- Expiration: implemented, default currently 7 days.
- Storage: raw token currently stored in DB (not hashed).

Action:
- Required: store only token hash in DB (lookup by hash).
- Recommended: reduce TTL to 24-72h for stricter risk posture.

### 4. Audit Logs
Status: Required for enterprise readiness.

Current state:
- Structured audit events exist, but only in application logs.

Action:
- Add persistent `audit_events` table with at least:
  - `id`, `timestamp`, `actor_user_id`, `tenant_id`, `action`, `target_type`, `target_id`, `ip_address`, `metadata_json`.
- Record key events such as role changes, removals, tenant create/suspend, invite accept/revoke, session revoke.

### 5. Device Session Visibility
Status: Required for strong V1 UX/security.

Current state:
- Session model stores device metadata and supports revoke flows.
- No `GET /auth/sessions` endpoint exists.

Action:
- Add `GET /auth/sessions` for current user.
- Add UI panel for active sessions (device, user agent, last seen, revoke action).

### 6. Minor Design Improvements

Tenant switching safety:
- Status: Membership enforcement already exists (required check is present).
- Gap: explicit mismatch audit logging is still needed.

Invitation lifecycle:
- Status: Required for admin operations completeness.
- Add:
  - `GET /tenants/{id}/invites`
  - `POST /invites/{token}/resend`

Permission alignment:
- Status: Required immediately.
- Fix mismatch where frontend tenant permissions imply `SUSPEND_USERS`, while backend enforces suspend/unsuspend as platform-admin-only.

### 7. Frontend Architecture Assessment

Status: Confirmed strength.

What is solid in current implementation:
- `AuthProvider`, `useAuth`, `useTenant`, and `ProtectedRoute` form a clean auth composition model.
- Tenant-aware UI primitives (`TenantSwitcher`, `RoleSelector`, `InviteUserModal`) align with multi-tenant behavior.

Conclusion:
- Architecture direction is good; priority is now security-hardening and permission-policy consistency.

# Auth System Feature Details

Date: 2026-03-13
Project: `ferrouslabs-auth-system`
Audience: AI coding agents and developers working on this repository.

## 1) What This Auth System Is

This is a reusable multi-tenant authentication and user-management module for SaaS-style applications.

It currently provides:
- AWS Cognito authentication using Hosted UI OAuth2 authorization-code flow with PKCE on the frontend
- Backend JWT verification and authenticated user sync into the local database
- Multi-tenant membership and role management
- Invitation-based onboarding with email delivery support
- Session revocation support and account suspension controls
- Admin-facing React components for tenant user management

Primary stack:
- Backend: FastAPI + SQLAlchemy + Alembic
- Database: PostgreSQL with row-level security on tenant-scoped tables
- Frontend: React + Vite
- Identity: AWS Cognito
- Email delivery: AWS SES (with graceful fallback if SES is not configured)

## 2) Intent (Why It Exists)

The goal is to provide a production-oriented auth foundation where:
- Users authenticate with Cognito but are still represented locally for app-specific authorization
- Tenant isolation is enforced at both request/middleware level and database policy level
- Owners and admins can safely manage tenant membership
- Invitations work end-to-end for joining tenants
- The module can be dropped into a demo app or evolved into a reusable starter package

## 3) Scope Boundaries

In scope:
- Authentication, token verification, user sync, and current-user lookup
- Tenant creation and tenant membership lookup
- Role-based authorization across `owner`, `admin`, `member`, and `viewer`
- Invitation lifecycle and invitation acceptance
- Tenant user management, session revocation, and platform-admin suspension controls
- Frontend auth context, Cognito client helpers, tenant switcher, and admin user-management UI

Out of scope in the current codebase:
- Enterprise SSO federation beyond the current Cognito Hosted UI setup
- A dedicated audit-events database table or audit analytics UI
- Full infrastructure packaging for all AWS resources
- Fine-grained permission tables beyond the current role/permission mapping in code

## 4) Core Concepts

- User: A local application user record keyed to a Cognito `sub`.
- Tenant: The top-level organizational boundary for multi-tenant isolation.
- Membership: The join record connecting a user to a tenant with a tenant-scoped role and status.
- Roles: `owner`, `admin`, `member`, `viewer`, plus platform-admin override on the user record.
- Invitation: A time-limited token that authorizes a specific email address to join a tenant.
- Session: A persisted refresh-token hash used for logout and revocation workflows.
- Tenant context: Request-scoped auth state derived from `Authorization` and `X-Tenant-ID` headers.

## 5) Feature Inventory (Current)

### 5.1 Cognito Authentication and User Sync

Status: Implemented

Capabilities:
- Frontend starts Cognito Hosted UI login/signup using OAuth2 authorization-code flow with PKCE
- Frontend exchanges auth codes for tokens and refreshes access tokens before expiry
- Backend verifies Cognito JWTs
- Backend syncs authenticated Cognito users into the local `users` table
- Backend exposes authenticated profile lookup via `/auth/me`

Implementation pointers:
- `backend/app/auth_usermanagement/security/jwt_verifier.py`
- `backend/app/auth_usermanagement/api/__init__.py`
- `backend/app/auth_usermanagement/services/user_service.py`
- `frontend/src/auth_usermanagement/services/cognitoClient.js`
- `frontend/src/auth_usermanagement/context/AuthProvider.jsx`

### 5.2 Tenant Lifecycle and Tenant Context

Status: Implemented

Capabilities:
- Authenticated users can create tenants
- Tenant creators are automatically assigned the `owner` role
- Users can list their tenant memberships
- Middleware requires `X-Tenant-ID` for tenant-scoped routes
- Middleware validates active membership before allowing tenant-scoped access
- Middleware sets PostgreSQL session variables used by row-level security policies

Implementation pointers:
- `backend/app/auth_usermanagement/services/tenant_service.py`
- `backend/app/auth_usermanagement/security/tenant_middleware.py`
- `backend/app/auth_usermanagement/security/tenant_context.py`
- `backend/app/auth_usermanagement/api/__init__.py`

### 5.3 Authorization Model and Permission Checks

Status: Implemented

Capabilities:
- Backend role hierarchy supports `owner`, `admin`, `member`, and `viewer`
- Guard dependencies enforce owner-only, admin-and-up, member-and-up, and viewer-and-up access
- Permission-check endpoint demonstrates the current permission vocabulary in code
- Platform admins bypass tenant-role checks where intended
- Frontend exposes permission constants for user-management UI decisions

Implementation pointers:
- `backend/app/auth_usermanagement/security/guards.py`
- `backend/app/auth_usermanagement/security/dependencies.py`
- `frontend/src/auth_usermanagement/constants/permissions.js`

### 5.4 Invitations and Onboarding

Status: Implemented end-to-end

Capabilities:
- Admins and owners can create tenant invitations
- Invitations store email, role, token, creator, and expiry
- Invitation preview endpoint supports pre-accept screens
- Invitation acceptance validates expiry, prior acceptance, and invited-email match
- Existing memberships are reactivated on acceptance and can be upgraded to a stronger invited role
- Invitation email sending is integrated through the email service

Implementation pointers:
- `backend/app/auth_usermanagement/services/invitation_service.py`
- `backend/app/auth_usermanagement/services/email_service.py`
- `backend/app/auth_usermanagement/api/__init__.py`
- `frontend/src/auth_usermanagement/components/AcceptInvitation.jsx`
- `frontend/src/auth_usermanagement/services/authApi.js`

### 5.5 Tenant User Management

Status: Implemented with safeguards

Capabilities:
- Members and above can list active tenant users
- Admins and owners can update tenant user roles
- Admins and owners can remove users from a tenant by marking memberships as `removed`
- Service logic prevents deleting or demoting the last tenant owner
- Frontend user-management UI supports search, filter, sort, pagination, confirmation dialogs, retry flows, toast feedback, and mobile-friendly rendering

Implementation pointers:
- `backend/app/auth_usermanagement/services/user_management_service.py`
- `backend/app/auth_usermanagement/api/__init__.py`
- `frontend/src/auth_usermanagement/components/UserList.jsx`
- `frontend/src/auth_usermanagement/components/InviteUserModal.jsx`
- `frontend/src/auth_usermanagement/components/ConfirmDialog.jsx`
- `frontend/src/auth_usermanagement/components/Toast.jsx`

### 5.6 Session Safety and Account Suspension

Status: Implemented

Capabilities:
- Frontend performs best-effort revoke-all-sessions during logout
- Backend supports revoking one session or all active sessions for the current user
- Sessions are stored as hashed refresh tokens with revocation timestamps
- Platform admins can suspend and unsuspend user accounts
- Suspension state is persisted on the user record using `is_active` and `suspended_at`

Implementation pointers:
- `backend/app/auth_usermanagement/services/session_service.py`
- `backend/app/auth_usermanagement/models/session.py`
- `backend/app/auth_usermanagement/api/__init__.py`
- `frontend/src/auth_usermanagement/context/AuthProvider.jsx`

### 5.7 Tenant Isolation and Database Security

Status: Implemented

Capabilities:
- PostgreSQL row-level security is enabled on `memberships` and `invitations`
- Policies allow access when `tenant_id` matches `app.current_tenant_id`
- Platform admins can bypass tenant RLS through `app.is_platform_admin`
- Session revocation routes are intentionally user-scoped rather than tenant-scoped

Implementation pointers:
- `backend/alembic/versions/0eec64567dac_enable_row_level_security.py`
- `backend/app/auth_usermanagement/security/tenant_middleware.py`

### 5.8 Audit Logging

Status: Implemented to application logs

Capabilities:
- Tenant creation, invitation lifecycle, role updates, removals, suspension, and session revocation events are logged
- Audit payloads are structured JSON written through the application logger
- There is currently no dedicated `audit_events` database table

Implementation pointers:
- `backend/app/auth_usermanagement/services/audit_service.py`
- `backend/app/auth_usermanagement/api/__init__.py`

## 6) Implemented API Surface

Current backend auth routes include:
- `GET /auth/debug-token`
- `POST /auth/sync`
- `GET /auth/me`
- `POST /auth/tenants`
- `GET /auth/tenants/my`
- `GET /auth/tenant-context`
- `GET /auth/admin/settings`
- `GET /auth/owner/danger-zone`
- `GET /auth/member/dashboard`
- `GET /auth/viewer/reports`
- `GET /auth/permissions/check`
- `POST /auth/invite`
- `POST /auth/tenants/{tenant_id}/invite`
- `GET /auth/invites/{token}`
- `POST /auth/invites/accept`
- `GET /auth/tenants/{tenant_id}/users`
- `PATCH /auth/tenants/{tenant_id}/users/{user_id}/role`
- `DELETE /auth/tenants/{tenant_id}/users/{user_id}`
- `DELETE /auth/sessions/all`
- `DELETE /auth/sessions/{session_id}`
- `PATCH /auth/users/{user_id}/suspend`
- `PATCH /auth/users/{user_id}/unsuspend`

## 7) Runtime Configuration

Required backend environment values:
- `COGNITO_REGION`
- `COGNITO_USER_POOL_ID`
- `COGNITO_CLIENT_ID`
- `DATABASE_URL`
- `SES_REGION`
- `SES_SENDER_EMAIL`
- `FRONTEND_URL`

Frontend environment values used by the React auth module:
- `VITE_COGNITO_DOMAIN`
- `VITE_COGNITO_CLIENT_ID`
- `VITE_COGNITO_REDIRECT_URI` (optional, defaults to `{window.location.origin}/callback`)

Current local defaults visible in code:
- Cognito region default: `eu-west-1`
- Backend frontend URL default: `http://localhost:5173`
- Backend database URL default: `postgresql://postgres:postgres@localhost:5432/trustos`

## 8) How AI Coding Agents Should Work on This Module

When adding or changing features:
1. Keep backend authorization rules and frontend permission checks aligned.
2. Preserve the distinction between tenant-scoped routes and user-scoped routes.
3. Do not bypass tenant middleware or RLS assumptions when adding new tenant data.
4. Reuse the existing services, guards, and auth API helpers before introducing new patterns.
5. Preserve safety checks around last-owner removal and invitation email matching.
6. Treat audit logging as log-based today unless a real audit table is introduced.

Minimum verification checklist:
- `frontend`: build succeeds
- `backend`: tests pass
- Cognito sign-in and `/auth/sync` still work
- invitation preview and acceptance still work
- tenant user management still works for owner/admin/member/viewer behavior
- session revocation and suspension paths still behave as expected

## 9) Suggested Next Feature Areas

- Enterprise SSO federation with Cognito-backed SAML/OIDC integrations
- Dedicated audit persistence and admin audit views
- Stronger session/device tracking tied to refresh-token issuance
- Production hardening for database SSL, secrets, and operational failover
- Extraction of the frontend auth package into a cleaner reusable module boundary

## 10) Database Tables and Schemas

This section reflects the effective auth schema after these migrations:
- `d3494139f54d_create_auth_tables.py`
- `7a454a9250b1_add_user_suspension_fields.py`
- `0eec64567dac_enable_row_level_security.py`

Note:
- Column types below are the SQLAlchemy/PostgreSQL types used by the auth module.
- Roles, plans, and statuses are currently validated in application code rather than enforced with database enums.

### 10.1 `tenants`

Purpose:
- Stores tenant or organization records.

Columns:
- `id UUID PRIMARY KEY`
- `name VARCHAR(255) NOT NULL`
- `plan VARCHAR(50) DEFAULT 'free'`
- `status VARCHAR(20) DEFAULT 'active'`
- `created_at TIMESTAMP NOT NULL`
- `updated_at TIMESTAMP NOT NULL`

Relationships and constraints:
- Referenced by `memberships.tenant_id`
- Referenced by `invitations.tenant_id`

### 10.2 `users`

Purpose:
- Stores the local representation of Cognito users.

Columns:
- `id UUID PRIMARY KEY`
- `cognito_sub VARCHAR(255) NOT NULL UNIQUE`
- `email VARCHAR(255) NOT NULL UNIQUE`
- `name VARCHAR(255) NULL`
- `is_platform_admin BOOLEAN DEFAULT false`
- `is_active BOOLEAN NOT NULL DEFAULT true`
- `suspended_at TIMESTAMP NULL`
- `created_at TIMESTAMP NOT NULL`
- `updated_at TIMESTAMP NOT NULL`

Indexes:
- Unique index on `cognito_sub`
- Unique index on `email`

Relationships and constraints:
- Referenced by `memberships.user_id`
- Referenced by `sessions.user_id`
- Referenced by `invitations.created_by`

### 10.3 `memberships`

Purpose:
- Joins users to tenants and stores tenant-scoped role and membership status.

Columns:
- `id UUID PRIMARY KEY`
- `user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE`
- `tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE`
- `role VARCHAR(20) NOT NULL`
- `status VARCHAR(20) DEFAULT 'active'`
- `created_at TIMESTAMP NOT NULL`

Indexes:
- Index on `user_id`
- Index on `tenant_id`

Constraints:
- Unique constraint `unique_user_tenant` on `(user_id, tenant_id)`

RLS:
- Row-level security enabled
- Policy `memberships_tenant_isolation` allows rows where `tenant_id::text = current_setting('app.current_tenant_id', true)` or `current_setting('app.is_platform_admin', true) = 'true'`

### 10.4 `invitations`

Purpose:
- Stores invitation tokens and onboarding state for tenant join flows.

Columns:
- `id UUID PRIMARY KEY`
- `tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE`
- `email VARCHAR(255) NOT NULL`
- `role VARCHAR(20) NOT NULL`
- `token VARCHAR(255) NOT NULL UNIQUE`
- `expires_at TIMESTAMP NOT NULL`
- `accepted_at TIMESTAMP NULL`
- `created_by UUID NULL REFERENCES users(id) ON DELETE SET NULL`
- `created_at TIMESTAMP NOT NULL`

Indexes:
- Index on `tenant_id`
- Index on `email`
- Unique index on `token`

RLS:
- Row-level security enabled
- Policy `invitations_tenant_isolation` allows rows where `tenant_id::text = current_setting('app.current_tenant_id', true)` or `current_setting('app.is_platform_admin', true) = 'true'`

### 10.5 `sessions`

Purpose:
- Stores refresh-token hashes and revocation state for logout/session-safety workflows.

Columns:
- `id UUID PRIMARY KEY`
- `user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE`
- `refresh_token_hash VARCHAR(255) NOT NULL`
- `created_at TIMESTAMP NOT NULL`
- `revoked_at TIMESTAMP NULL`

Indexes:
- Index on `user_id`

RLS:
- No row-level security policy is currently applied because the table is treated as user-scoped rather than tenant-scoped.

## 11) One-Line Summary

This module is a reusable multi-tenant auth foundation with Cognito login, local user sync, tenant-aware role enforcement, invitation onboarding, session revocation, account suspension, and PostgreSQL-backed tenant isolation.

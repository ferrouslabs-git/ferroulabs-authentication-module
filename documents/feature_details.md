# Auth System Feature Details

Date: 2026-03-08
Project: `ferrouslabs-auth-system`
Audience: AI coding agents and developers working on this repository.

## 1) What This Auth System Is

This is a multi-tenant authentication and user management module built for SaaS-style apps.

It provides:
- Cognito-based authentication (OAuth2 code flow + JWT validation)
- Tenant-aware user membership and role management
- Invitation-based onboarding
- Session and account safety controls
- Admin UI components for managing users

Primary stack:
- Backend: FastAPI + SQLAlchemy + Alembic
- Database: PostgreSQL (with row-level security policies)
- Frontend: React + Vite
- Identity: AWS Cognito
- Email delivery: AWS SES

## 2) Intent (Why It Exists)

The intent is to give apps a reusable, production-oriented auth foundation where:
- Users can securely sign in and maintain sessions
- Access is isolated per tenant
- Admins can manage tenant users safely
- Invitations and onboarding work end-to-end
- The module can be reused in a small app demo or packaged template

## 3) Scope Boundaries

In scope:
- Authentication, authorization, tenant membership, invitation lifecycle
- Admin user-management UX (invite/remove/role/suspend)
- Security controls (RLS, token refresh, suspension checks)

Out of scope (current state):
- Enterprise SSO federation (SAML/OIDC IdP integration)
- Full design-system-level UI refactor
- Full infra-as-code packaging for all AWS resources

## 4) Core Concepts

- User: Identity principal authenticated via Cognito.
- Tenant: Logical organization boundary.
- Membership: User-to-tenant mapping with role.
- Role: Permission level within a tenant (`admin`, `member`) plus optional platform-admin override.
- Invitation: Time-limited token allowing a user to join a tenant.
- Session safety: Token validation/refresh and revocation-compatible behavior.

## 5) Feature Inventory (Current)

### 5.1 Authentication and Tokens

Status: Implemented

Capabilities:
- Cognito JWT verification in backend
- Frontend token handling with refresh before expiry
- Safe fallback behavior on refresh/auth failures

Implementation pointers:
- `backend/app/auth_usermanagement/security/jwt_verifier.py`
- `frontend/src/auth_usermanagement/services/cognitoClient.js`
- `frontend/src/auth_usermanagement/context/AuthProvider.jsx`

### 5.2 Tenant Isolation and Security

Status: Implemented

Capabilities:
- PostgreSQL RLS policies enabled for tenant-scoped tables
- Middleware sets tenant context/session variables
- Platform-admin bypass where intended

Implementation pointers:
- `backend/alembic/versions/0eec64567dac_enable_row_level_security.py`
- `backend/app/auth_usermanagement/security/tenant_middleware.py`

### 5.3 Invitations and Onboarding

Status: Implemented end-to-end

Capabilities:
- Create invitation token and persist invitation state
- Send invitation email via SES
- Accept invitation flow in frontend with edge-case handling
- Join tenant and activate membership

Implementation pointers:
- `backend/app/auth_usermanagement/services/invitation_service.py`
- `backend/app/auth_usermanagement/services/email_service.py`
- `frontend/src/auth_usermanagement/components/AcceptInvitation.jsx`

### 5.4 Account Suspension Controls

Status: Implemented

Capabilities:
- Suspend/unsuspend user account
- Enforce active-user checks in auth-protected behavior
- Admin controls for suspension actions

Implementation pointers:
- `backend/app/auth_usermanagement/services/user_management_service.py`
- `frontend/src/auth_usermanagement/components/UserList.jsx`

### 5.5 Admin User Management UI

Status: Implemented with hardening improvements

Capabilities:
- List tenant users
- Change role (with safeguards)
- Remove user (with confirmation)
- Suspend/unsuspend (platform admin)
- Toast feedback for success/error
- Retry failed operations
- Search/filter/sort/pagination
- Mobile-friendly card view

Implementation pointers:
- `frontend/src/auth_usermanagement/components/UserList.jsx`
- `frontend/src/auth_usermanagement/components/InviteUserModal.jsx`
- `frontend/src/auth_usermanagement/components/ConfirmDialog.jsx`
- `frontend/src/auth_usermanagement/components/Toast.jsx`

### 5.6 Permission Vocabulary and Error Handling

Status: Implemented

Capabilities:
- Shared permission constants and role-permission mapping
- Consistent contextual success/error messages

Implementation pointers:
- `frontend/src/auth_usermanagement/constants/permissions.js`
- `frontend/src/auth_usermanagement/utils/errorHandling.js`

## 6) Runtime Configuration

Required environment values (backend):
- `COGNITO_REGION`
- `COGNITO_USER_POOL_ID`
- `COGNITO_CLIENT_ID`
- `DATABASE_URL`
- `SES_REGION`
- `SES_SENDER_EMAIL`
- `FRONTEND_URL`

Current local sample (from active setup):
- Cognito region: `eu-west-1`
- Frontend URL: `http://localhost:5173`

## 7) How AI Coding Agents Should Work on This Module

When adding or changing features:
1. Keep backend authorization and frontend permission checks aligned.
2. Preserve tenant isolation assumptions (middleware + RLS).
3. Prefer extending shared utilities instead of adding one-off logic.
4. Add user-safe UX for destructive actions (confirm + clear feedback).
5. Validate with both frontend build and backend tests.

Minimum verification checklist:
- `frontend`: build succeeds
- `backend`: tests pass
- invitation flow still works
- tenant user management still works for admin and non-admin users

## 8) Suggested Next Feature Areas

- Enterprise SSO federation with Cognito (SAML/OIDC)
- RDS production migration hardening (SSL, secrets, failover)
- Better admin analytics/audit views
- Design polish and component extraction (reduce inline styles)

## 9) One-Line Summary

This module is a reusable multi-tenant auth and user-management foundation with real Cognito auth, real invitation email delivery, database-level tenant isolation, and hardened admin workflows.

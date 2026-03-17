# Portability Guideline: Moving This Auth/User Management Module Into a Real App

This guide is based on the current implementation and focuses on what the host app must own versus what the module provides.

## 1) Copy Scope

Copy these folders into your target backend app:
- `backend/app/auth_usermanagement`
- `backend/alembic/versions` entries related to auth/user-management tables and RLS policies

Copy frontend module into target frontend app:
- `frontend/src/auth_usermanagement`

## 2) Host Backend Ownership Requirements

The host app must own DB runtime objects and expose:
- `app.database.engine`
- `app.database.SessionLocal`
- `app.database.Base`
- `app.database.get_db`

The auth module imports DB runtime from host integration points (`app.database`).
Do not create a second engine/session/base inside module runtime.

## 3) Backend Integration Steps

1. Install backend dependencies
- FastAPI, SQLAlchemy, Alembic, python-jose, requests, boto3, pydantic-settings, psycopg2-binary

2. Wire route mounting
- Import module router and include it under configured prefix:
  - `app.include_router(auth_router, prefix=settings.auth_api_prefix, tags=["auth"])`

3. Add middleware stack
- `TenantContextMiddleware(auth_prefix=settings.auth_api_prefix)`
- `RateLimitMiddleware(auth_prefix=settings.auth_api_prefix)`
- `SecurityHeadersMiddleware`

4. Configure CORS for your frontend origins
- Must allow credentials if using cookie refresh flow (`allow_credentials=True`)

5. Run migrations through host Alembic pipeline
- Apply auth-related migration files in host migration ownership flow
- Use PostgreSQL for final tenant isolation verification (RLS behavior)

6. Confirm JWT setup
- Cognito region, user pool id, client id, domain configured
- Token verification path can reach Cognito JWKS URL

7. Confirm refresh cookie behavior
- Set `COOKIE_SECURE` correctly per environment
- Ensure `AUTH_API_PREFIX` and `AUTH_COOKIE_PATH` align with reverse proxy path routing

## 4) Backend Environment Variables

Minimum required:
- `DATABASE_URL` (host app)
- `COGNITO_REGION`
- `COGNITO_USER_POOL_ID`
- `COGNITO_CLIENT_ID`
- `COGNITO_DOMAIN`

Recommended/auth module settings:
- `AUTH_NAMESPACE` (default `authum`)
- `AUTH_API_PREFIX` (default `/auth`)
- `AUTH_COOKIE_NAME` (optional override)
- `AUTH_COOKIE_PATH` (optional override)
- `COOKIE_SECURE` (`true` for HTTPS envs)
- `FRONTEND_URL` (invite-link base)
- `SES_REGION` and `SES_SENDER_EMAIL` (if invitation email sending is needed)

## 5) Frontend Integration Steps

1. Copy module source
- Include `src/auth_usermanagement` in target app

2. Install frontend dependencies
- React, react-router-dom, axios (plus your existing stack)

3. Wrap app with provider
- Add `AuthProvider` high in tree

4. Add routes
- Callback route at configured callback path
- Invite route using configured invite prefix
- Protected admin route using `ProtectedRoute`

5. Connect UI entry points
- Sign in / sign up triggers from `cognitoClient`
- Admin dashboard route for user management

6. Configure Vite/frontend env vars
- `VITE_AUTH_NAMESPACE`
- `VITE_AUTH_API_BASE_PATH` (must match backend auth prefix)
- `VITE_AUTH_CALLBACK_PATH`
- `VITE_AUTH_INVITE_PATH_PREFIX`
- `VITE_COGNITO_DOMAIN`
- `VITE_COGNITO_CLIENT_ID`
- Optional: `VITE_COGNITO_REDIRECT_URI`

## 6) Tenant Context and Header Contract

For tenant-scoped endpoints, frontend/backend contract requires:
- `Authorization: Bearer <access token>`
- `X-Tenant-ID: <tenant uuid>`

Some routes are intentionally tenant-agnostic and bypass tenant header requirement:
- `/sync`, `/debug-token`, `/me`, `/tenants`, `/tenants/my`
- `/invites/*`
- `/sessions*`
- `/cookie/*`, `/token/refresh`
- `/platform/*`

## 7) Production Hardening Checklist During Port

1. Replace in-memory rate limiter with Redis/distributed limiter.
2. Add CSRF token strategy for cookie-refresh endpoint.
3. Make audit logs durable (DB or SIEM sink with retention).
4. Ensure strict HTTPS + secure cookie settings in non-local envs.
5. Add observability metrics for auth, invite, and token refresh lifecycle.
6. Validate all RLS paths against PostgreSQL, not SQLite-only.

## 8) Smoke Test Flow After Port

1. User signs in through Cognito Hosted UI and returns to callback.
2. Frontend exchanges code, stores refresh cookie via backend.
3. Backend `/sync` creates/updates local user.
4. Tenant is created or selected.
5. Admin opens user management and can list/update tenant users.
6. Invitation is sent, previewed, and accepted by invited user.
7. Session revoke and token refresh endpoints behave correctly.
8. Platform admin paths are accessible only to platform admins.

## 9) Known Integration Pitfalls

- Prefix mismatch between frontend `VITE_AUTH_API_BASE_PATH` and backend `AUTH_API_PREFIX`
- Missing `allow_credentials` in CORS causing refresh cookie flow to fail
- Setting `COOKIE_SECURE=true` on local HTTP environments
- Reverse proxy path rewriting that breaks cookie path scoping
- Running only SQLite tests for tenant isolation instead of PostgreSQL RLS verification

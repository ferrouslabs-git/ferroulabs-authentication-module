# Module-Based Payment & Entitlement Gap Analysis

Date: 2026-03-12
Project: `ferrouslabs-auth-system`
Audience: Developers planning billing and feature-gating integration.

## 1) Context

The app has four distinct product modules. A user arrives from a module-specific landing page,
signs up, pays for that module, and immediately gains access to its features. Later they can
purchase additional modules independently. This document maps what the current auth/user-management
system already provides, what auth-adjacent gaps exist, and what entirely separate concerns still
need to be built.

---

## 2) Current Auth System Capabilities

These features already exist and are relevant to the multi-module payment model.

| Capability | Where it lives | Notes |
|---|---|---|
| Cognito-based identity (PKCE flow) | `backend/app/auth_usermanagement/security/jwt_verifier.py` | One identity regardless of which module they came from |
| User sync from Cognito to local DB | `backend/app/auth_usermanagement/api/__init__.py` (`POST /sync`) | Creates `users` row on first login |
| Multi-tenant membership + roles | `backend/app/auth_usermanagement/models/membership.py` | `owner / admin / member / viewer` hierarchy |
| Tenant isolation middleware + Postgres RLS | `backend/app/auth_usermanagement/security/tenant_middleware.py` | Sets `app.current_tenant_id` session var |
| Role-based guards (`require_admin`, etc.) | `backend/app/auth_usermanagement/security/guards.py` | Role hierarchy enforced on every request |
| Permission helper (`check_permission`) | `backend/app/auth_usermanagement/security/guards.py` | Currently role-mapped, no entitlement layer yet |
| Invitation lifecycle | `backend/app/auth_usermanagement/api/__init__.py` | Token-based invite, accept, preview |
| Session revocation | `backend/app/auth_usermanagement/api/__init__.py` | Revoke single or all sessions |
| User suspension / unsuspension | `backend/app/auth_usermanagement/api/__init__.py` | Platform-admin only |
| Tenant `plan` field | `backend/app/auth_usermanagement/models/tenant.py` | Single string (`free / pro / enterprise`), not per-module |
| Frontend `ProtectedRoute` | `frontend/src/auth_usermanagement/components/ProtectedRoute.jsx` | Guards authenticated pages |
| Frontend role/permission helpers | `frontend/src/auth_usermanagement/constants/permissions.js` | Role-to-permission mapping |
| Hosted signup URL generation | `frontend/src/auth_usermanagement/services/cognitoClient.js` | No module attribution passed yet |

---

## 3) Auth/User-Management Gaps (Must Add to This Module)

These are missing from the auth module but are **directly required** to gate features by module payment.

### 3.1 Module Entitlement Model

**Problem:** The only billing dimension is a single tenant-level `plan` string. There is no way to
record "user X has paid for module A but not module B."

**What to add:**
- A `user_module_entitlements` (or `tenant_module_entitlements`) table.
  - Columns: `id`, `user_id` (or `tenant_id`), `module_id`, `status` (`active / cancelled / expired`),
    `granted_at`, `expires_at` (nullable for lifetime), `payment_reference`.
- Decide scope: **per-user** (individual purchase) vs **per-tenant** (anyone in the org gets it).
  Both cases are valid; the schema should support whichever you choose.
- Alembic migration for the new table.

### 3.2 Entitlement-Aware Authorization Guard

**Problem:** `check_permission` in `guards.py` is a pure role-to-permission map. It has no
awareness of whether the user/tenant has paid for a given module.

**What to add:**
- A FastAPI dependency `require_module_access("module_id")` that:
  1. Reads the current user (or tenant) from context.
  2. Queries the entitlement table.
  3. Returns `403` if no active entitlement is found.
- This can live alongside the existing role guards or wrap them.

### 3.3 Entitlement Check in `TenantContext`

**Problem:** `TenantContext` only carries `user_id`, `tenant_id`, `role`, `is_platform_admin`.
Downstream handlers cannot cheaply inspect what modules are active.

**What to add:**
- Optionally extend `TenantContext` with `active_modules: list[str]`, populated by the middleware
  from the entitlement table so handlers don't need a second DB look-up each time.

### 3.4 Landing Page / Module Attribution on Signup

**Problem:** `getHostedSignupUrl()` sends users to Cognito with no indication of which module
brought them. After signup, the backend has no way to know which payment page to redirect to.

**What to add:**
- Pass a `state` parameter through the OAuth2 authorization URL encoding the source module slug
  (e.g., `state=module_a`).
- In the callback handler, read and validate the `state` value (must be an allowlisted slug to
  prevent open-redirect abuse), then redirect the user to the correct payment page.

### 3.5 Post-Payment Entitlement Activation Endpoint

**Problem:** No endpoint exists to activate a module for a user after a successful payment.

**What to add:**
- `POST /auth/entitlements` — called by the billing webhook or a payment success callback.
  - Payload: `user_id`, `module_id`, `payment_reference`.
  - Creates or updates the entitlement record to `active`.
  - Requires either a verified webhook signature or platform-admin privileges to call directly.

### 3.6 Frontend Entitlement-Aware Routing

**Problem:** `ProtectedRoute` only checks `isAuthenticated`. It doesn't know which modules are
unlocked.

**What to add:**
- A `<ModuleRoute module="module_a">` wrapper (or extended `ProtectedRoute`) that reads entitlements
  from user state and redirects to the payment page if the module is not active.
- An `useEntitlements()` hook that fetches and caches the user's active module list.

---

## 4) Required Features Outside Auth/User-Management

These are entirely separate concerns. They depend on the auth system but live in their own
service/module.

### 4.1 Billing Provider Integration

- Choose and integrate a payment processor: Stripe, Paddle, Lemon Squeezy, etc.
- Product/price catalog: one product per module (+ optional tiers if needed).
- Checkout session creation endpoint: backend calls billing API, returns checkout URL to frontend.
- Secure webhook endpoint: verifies provider signature and triggers entitlement activation.
- Subscription lifecycle: renewal, failed payment, grace period, cancellation, refund.
- Store billing records: `orders`, `invoices`, `payment_events` tables.

### 4.2 Module Catalog

- A definition of the four modules (ID, name, description, price, landing page URL).
- Used by the payment pages, checkout creation, and entitlement checks.
- Can be a simple DB table or a config file initially.

### 4.3 Module-Specific Landing Pages and Payment Pages

- Four landing pages, each with a unique URL that passes module context forward.
- Four payment/pricing pages, each showing the correct price and plan.
- Post-payment success and failure pages per module.
- Attribution: landing page must carry the module identifier all the way through
  signup → callback → payment.

### 4.4 Feature Flag / UI Gating

- Frontend components showing/hiding features based on entitlements.
- API endpoints returning `403` (via the `require_module_access` guard) when entitlement is absent.
- Clear UX for "locked" features: upgrade prompt, redirect to pricing page, etc.

### 4.5 Analytics and Attribution

- Conversion tracking: which landing page → which module purchased.
- Funnel visibility: landing → signup → payment started → payment completed.
- Source attribution stored on the entitlement record for reporting.

### 4.6 Admin and Support Tooling

- Platform-admin view of user entitlements.
- Manual grant / revoke / extend entitlement (for support / refunds / trials).
- Billing event log for troubleshooting.

---

## 5) Implementation Order (Suggested)

| Priority | Item | Depends on |
|---|---|---|
| 1 | Module entitlement DB table + migration | Auth DB already set up |
| 2 | `POST /auth/entitlements` activation endpoint | Entitlement table |
| 3 | `require_module_access` guard | Entitlement table |
| 4 | `TenantContext.active_modules` population | Entitlement table + middleware |
| 5 | Frontend `useEntitlements()` hook + `ModuleRoute` | Backend entitlement endpoint |
| 6 | Cognito `state` attribution on signup URL | Frontend cognitoClient.js |
| 7 | Billing provider integration (Stripe/Paddle) | Module catalog, entitlement endpoint |
| 8 | Checkout session creation + webhook handler | Billing provider |
| 9 | Module-specific landing/pricing/payment pages | Checkout session creation |
| 10 | Analytics attribution storage | Entitlement model |
| 11 | Admin entitlement management UI | All of the above |

---

## 6) Key Decision: Entitlement Scope

Before building the entitlement table, decide:

- **Per-user:** Each individual pays for modules. Better for consumer-style products or
  individual licenses. Lower friction for solo users. More complex if team sharing is needed later.
- **Per-tenant:** One person pays and everyone in the org gets the module. Better for B2B teams.
  Simpler if you expect users to be organized into companies.
- **Hybrid:** Individual purchase but with the option to extend to the whole tenant. Most flexible
  but adds complexity.

This decision affects the `user_module_entitlements` table schema directly.
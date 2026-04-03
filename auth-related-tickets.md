# GrowthGorilla Auth-Related Tickets

> Scope: Auth infrastructure, signup and login journeys, SSO, onboarding, referral system, billing integration seams, entitlements, and test harness.
>
> Out of scope (future epics): Splash pages, wheel-of-fortune pages. Replaced by mock test harness pages until those features are built.
>
> SSO note: Google and Microsoft auth are configured once at the Cognito level and shared across all 4 modules. There are no per-module auth tickets — one user identity works across all modules.

---

## Epic Index

| Epic | Prefix | Description |
|---|---|---|
| Infrastructure | INFRA | Cognito, SSO provider setup, deployment environments |
| Host App Foundation | FOUND | App scaffold, DB runtime, schema, roles |
| Signup Journey | SIGNUP | Account creation, confirmation, attribution |
| Login Journey | LOGIN | Password and SSO login, post-login pipeline |
| Onboarding | ONB | Onboarding state machine, UX wizard |
| Referral System | REF | Invite creation, referral lifecycle |
| Billing Integration Seams | BIS | Webhook skeleton, entitlement interface, billing refs |
| Entitlements | ENT | Module access grants and guards |
| Test Harness | TEST | Mock pages and automated test coverage |

---

## Reused Module Capabilities (Done, Integration Only)

These items are already provided by `auth_usermanagement` and are kept as tickets for integration clarity. They are excluded from build estimation totals.

| Ticket | Status | Estimation Policy | Integration Notes |
|---|---|---|---|
| SIGNUP-01 | Done in module | Excluded | Reuse `POST /auth/sync` and `sync_user_from_cognito`; only add host `user_profiles` hook |
| SIGNUP-03 | Done in module | Excluded | Reuse `CustomSignupForm` in host route |
| LOGIN-01 | Done in module core | Excluded | Reuse token verification and sync; add host onboarding and entitlements composition only |
| LOGIN-02 | Done in module | Excluded | Reuse cookie and session endpoints; host wiring/config only |
| LOGIN-03 | Done in module core | Excluded | Reuse `CustomLoginForm`; add host SSO entry buttons/routing |
| LOGIN-05 | Done in module | Excluded | Reuse set-password endpoint and invited-user password flow |
| LOGIN-06 | Done in module | Excluded | Reuse forgot-password endpoints and existing UI flow |

---

## EPIC: Infrastructure

---

### INFRA-01 — Configure Cognito User Pool and App Clients

**Team:** DevOps / Backend
**Size:** M

**Description:**
Create one Cognito user pool and one app client per environment (dev, staging, prod). This is the shared identity pool for all users regardless of which module they use or how they sign up.

**Acceptance Criteria:**
- [ ] One Cognito user pool exists and is active.
- [ ] One app client created per environment (dev/staging/prod).
- [ ] `ALLOW_USER_PASSWORD_AUTH` enabled on all clients (required for custom UI login).
- [ ] Token durations configured: Access 60 min, ID 60 min, Refresh 30 days.
- [ ] No client secret generated (public PKCE client).
- [ ] Callback URLs registered for all frontend environments.
- [ ] Sign-out URLs registered for all frontend environments.
- [ ] Environment variables documented and templated in `.env.example`.

**Dependencies:** None

---

### INFRA-02 — Configure Google SSO Federation in Cognito

**Team:** DevOps / Backend
**Size:** S

**Description:**
Wire Google OAuth2 as a federated identity provider inside the existing Cognito user pool. Users signing in with Google will receive the same Cognito JWT as email/password users. No per-module setup needed — one federation covers all modules.

**Acceptance Criteria:**
- [ ] Google Cloud project and OAuth client created with correct redirect URI (`<cognito-domain>/oauth2/idpresponse`).
- [ ] Google identity provider added to Cognito user pool.
- [ ] Attribute mapping configured: `email` → `email`, `name` → `name`.
- [ ] Google provider enabled on all app clients.
- [ ] Manual test: clicking "Continue with Google" on login page completes auth and returns valid Cognito JWT.

**Dependencies:** INFRA-01

---

### INFRA-03 — Configure Microsoft SSO Federation in Cognito

**Team:** DevOps / Backend
**Size:** S

**Description:**
Wire Microsoft Azure AD as an OIDC federated identity provider inside Cognito. Same shared setup as Google — no per-module configuration.

**Acceptance Criteria:**
- [ ] Azure AD app registration created with OIDC redirect URI pointing to Cognito.
- [ ] Microsoft OIDC provider added to Cognito user pool with correct issuer URL.
- [ ] Attribute mapping configured: `email` → `email`, `name` → `name`.
- [ ] Microsoft provider enabled on all app clients.
- [ ] Manual test: clicking "Continue with Microsoft" completes auth and returns valid Cognito JWT.

**Dependencies:** INFRA-01

---

## EPIC: Host App Foundation

---

### FOUND-01 — Scaffold Host App (database, config, main)

**Team:** Backend
**Size:** M

**Description:**
Create the host app skeleton following the auth module's integration contract. Host app owns `database.py`, `config.py`, and `main.py`. Mount the auth module router and register middleware.

**Acceptance Criteria:**
- [ ] `app/database.py` created: `engine`, `SessionLocal`, `Base`, `get_db`.
- [ ] `app/config.py` created: CORS settings, host-level env vars.
- [ ] `app/main.py` created: mounts auth module router, registers `RateLimitMiddleware`, `SecurityHeadersMiddleware`, `TenantContextMiddleware`.
- [ ] `GET /health` endpoint returns `{"status": "ok"}`.
- [ ] `GET /auth/debug-token` returns valid response when a valid Cognito JWT is provided.
- [ ] App starts without errors in dev environment.

**Dependencies:** INFRA-01

---

### FOUND-02 — Host Database Schema and Migrations

**Team:** Backend
**Size:** L

**Description:**
Create all host-owned tables and Alembic migrations. Covers the full data model for users, onboarding, referrals, credits, entitlements, and billing integration seams. Products/pricing are billing-owned and excluded.

**Tables to create:**
- `user_profiles` — extension of module `users` table (one-to-one, FK to `users.id`)
- `onboarding_progress` — tracks step completion per user
- `referrals` — inviter/invitee pair with lifecycle status
- `referral_reward_events` — idempotent reward issuance log
- `credit_ledger` — credits grant/debit with source event
- `entitlements` — user access per module (written by billing events)
- `billing_references` — `external_customer_id`, `external_subscription_id`, `last_payment_event_id` per user
- `payment_events` — raw incoming webhook log with idempotency key
- `acquisition_sessions` — anonymous pre-auth tracking (used by future splash/funnel epic)
- `signup_attribution_links` — attaches pre-auth acquisition data to authenticated user_id

**Acceptance Criteria:**
- [ ] All tables above created with correct columns, constraints, and FK references.
- [ ] All FKs to auth module tables (`users.id`) use `UUID` with `ondelete=SET NULL` or `CASCADE` as appropriate.
- [ ] Alembic migration file(s) created and run cleanly against a fresh database.
- [ ] `alembic upgrade head` succeeds with no errors.
- [ ] `alembic downgrade -1` succeeds without data loss on empty DB.

**Dependencies:** FOUND-01

---

### FOUND-03 — B2C Role and Access Model Configuration

**Team:** Backend
**Size:** S

**Description:**
Configure `auth_config.yaml` for B2C single-user model. One superadmin (platform owner). Standard end-user role. Disable or de-emphasize multi-tenant UX paths not relevant to B2C.

**Acceptance Criteria:**
- [ ] `auth_config.yaml` updated: space layer disabled, account layer kept (used as user profile scope).
- [ ] Platform admin role defined and assigned to app owner account.
- [ ] Standard `user` role defined for all end users.
- [ ] Config endpoint (`GET /auth/config/roles`) returns correct role and permission definitions.
- [ ] No tenant/space UX surfaces exposed in API that would confuse a B2C user.

**Dependencies:** FOUND-01

---

## EPIC: Signup Journey

---

### SIGNUP-01 — Backend: User Sync and Profile Creation on First Auth

**Team:** Backend
**Size:** M
**Status:** Module-provided baseline (done), host integration required
**Estimation:** Excluded from build totals (module-provided; integration only)

**Description:**
The auth sync baseline is already implemented in the module. Host app work is to integrate the existing sync path and extend it to create a `user_profiles` row on first auth. This remains idempotent and safe to call on every login.

**Acceptance Criteria:**
- [ ] `POST /auth/sync` (or equivalent sync endpoint from auth module) creates local user record on first call.
- [ ] Subsequent calls are idempotent — no duplicate records created.
- [ ] `user_profiles` row created automatically on first sync.
- [ ] User's `cognito_sub` is stored and used as the stable link between Cognito and the local DB.
- [ ] Works for email/password signup, Google SSO, and Microsoft SSO.

**Dependencies:** FOUND-02

---

### SIGNUP-02 — Backend: Signup Attribution Linking

**Team:** Backend
**Size:** S

**Description:**
After a user authenticates, the host app must link any pre-auth acquisition data (referral code, campaign context) to their new `user_id`. This is a host-owned step that runs once per new user.

**Acceptance Criteria:**
- [ ] `POST /growth/signup/link-attribution` endpoint accepts `{ referral_code, campaign_id }` and authenticated user context.
- [ ] Creates `signup_attribution_links` record linking user_id to acquisition data.
- [ ] If a valid `referral_code` is present and maps to an open referral, sets `referrals.status = 'signed_up'` and records `invitee_user_id`.
- [ ] Idempotent — calling twice for the same user is safe.
- [ ] Returns `{ linked: true }`.

**Dependencies:** FOUND-02, SIGNUP-01

---

### SIGNUP-03 — Frontend: Signup Page

**Team:** Frontend
**Size:** M
**Status:** Module-provided baseline (done), host integration required
**Estimation:** Excluded from build totals (module-provided; integration only)

**Description:**
The core signup UI already exists in the module (`CustomSignupForm`). Host app work is route composition, styling alignment, and integration with post-confirm auto-login and attribution.

**Acceptance Criteria:**
- [ ] Email + password + confirm password fields with client-side validation (min 8 chars, match check).
- [ ] Submit calls `POST /auth/custom/signup`.
- [ ] If `needs_confirmation: true`, transitions to confirmation code entry UX.
- [ ] Confirmation code submit calls `POST /auth/custom/confirm`.
- [ ] Resend code link calls `POST /auth/custom/resend-code`.
- [ ] On confirmation success, automatically calls `POST /auth/custom/login` (see LOGIN-01).
- [ ] Errors from backend displayed inline (invalid email, weak password, already exists).
- [ ] Loading states on all async actions.

**Dependencies:** INFRA-01, LOGIN-01

---

### SIGNUP-04 — Frontend: Post-Signup Auto-Login Transition

**Team:** Frontend
**Size:** S

**Description:**
After email confirmation, the user should be seamlessly logged in without returning to the login page. This screen handles the invisible transition: triggers login, establishes session, calls attribution endpoint, then redirects.

**Acceptance Criteria:**
- [ ] After `confirm` success, automatically calls `login` with stored credentials.
- [ ] On login success: stores refresh cookie (via `POST /auth/cookie/store-refresh`), registers session.
- [ ] Calls `POST /growth/signup/link-attribution` before redirecting.
- [ ] Redirects to onboarding step 1 on success.
- [ ] If auto-login fails, shows a "go to login" fallback link (does not strand the user).

**Dependencies:** SIGNUP-03, LOGIN-02, SIGNUP-02, ONB-01

---

## EPIC: Login Journey

---

### LOGIN-01 — Backend: Post-Login Pipeline

**Team:** Backend
**Size:** M
**Status:** Module-provided baseline (done), host integration required
**Estimation:** Excluded from build totals (module-provided; integration only)

**Description:**
Core token verification and user sync are already implemented in the module. Host app work is composing onboarding state + entitlements into a shared post-login context response.

**Acceptance Criteria:**
- [ ] Token verified via auth module `verify_token_async`.
- [ ] User sync runs (creates or fetches local user record).
- [ ] Loads onboarding state for the user.
- [ ] Loads entitlement list for the user.
- [ ] Returns session context response: `{ user, onboarding_state, entitlements }`.
- [ ] Works for all three auth methods (no method-specific branching in this pipeline).

**Dependencies:** FOUND-02, SIGNUP-01, ONB-01, ENT-01

---

### LOGIN-02 — Backend: Refresh Cookie and Session Registration

**Team:** Backend
**Size:** S
**Status:** Module-provided baseline (done), host integration required
**Estimation:** Excluded from build totals (module-provided; integration only)

**Description:**
Ensure refresh-token cookie storage and session registration work correctly in the host app context. These use existing auth module endpoints but must be wired into the host's post-login flow.

**Acceptance Criteria:**
- [ ] `POST /auth/cookie/store-refresh` stores refresh token in HttpOnly cookie correctly under host app config.
- [ ] `POST /auth/sessions/register` creates a session record.
- [ ] Cookie `Secure` flag enforced in production, relaxed in dev.
- [ ] Token refresh via cookie path (`POST /auth/cookie/refresh`) works end-to-end.

**Dependencies:** FOUND-01

---

### LOGIN-03 — Frontend: Login Page (Password + Google + Microsoft)

**Team:** Frontend
**Size:** M
**Status:** Module-provided baseline (done), host integration required
**Estimation:** Excluded from build totals (module-provided; integration only)

**Description:**
The core password login UI already exists in the module (`CustomLoginForm`). Host app work is composing the unified login page with Google/Microsoft SSO entry buttons and host-specific routing.

**Acceptance Criteria:**
- [ ] Email + password form submits to `POST /auth/custom/login`.
- [ ] "Continue with Google" button initiates Cognito hosted UI redirect with Google provider param.
- [ ] "Continue with Microsoft" button initiates Cognito hosted UI redirect with Microsoft provider param.
- [ ] On password login challenge `NEW_PASSWORD_REQUIRED`, routes to set-password page (see LOGIN-04).
- [ ] On success, runs post-login transition (store cookie, register session, load context, redirect).
- [ ] Inline error display (wrong password, unconfirmed account, account disabled).
- [ ] "Forgot password" link navigates to password reset flow.

**Dependencies:** INFRA-01, INFRA-02, INFRA-03, LOGIN-01, LOGIN-02

---

### LOGIN-04 — Frontend: SSO Callback Handler

**Team:** Frontend
**Size:** M

**Description:**
Handle the OAuth2 redirect callback from Cognito after Google or Microsoft SSO. Exchange the authorization code for tokens and run the same post-login pipeline as password login.

**Acceptance Criteria:**
- [ ] `/callback` route handles `?code=` query param from Cognito redirect.
- [ ] Exchanges code for tokens via Cognito token endpoint.
- [ ] Runs same post-login pipeline: store cookie, register session, load context.
- [ ] Detects new vs returning user and routes accordingly (new → onboarding, returning → dashboard or post-login router).
- [ ] Handles errors (invalid code, provider mismatch) with user-friendly message.

**Dependencies:** INFRA-02, INFRA-03, LOGIN-01, LOGIN-02

---

### LOGIN-05 — Frontend: Set Password Page (Invited User Challenge)

**Team:** Frontend
**Size:** S
**Status:** Module-provided baseline (done), host integration required
**Estimation:** Excluded from build totals (module-provided; integration only)

**Description:**
The endpoint and core flow are already provided by the module. Host app work is wiring the route and transition behavior for `NEW_PASSWORD_REQUIRED`.

**Acceptance Criteria:**
- [ ] Email pre-filled (read-only) from login step.
- [ ] New password + confirm password fields (min 8 chars, match check).
- [ ] Submits to `POST /auth/custom/set-password` with `{ email, new_password, session }`.
- [ ] On success, immediately runs post-login pipeline and redirects.
- [ ] Handles invalid/expired session with clear error and "go back to login" link.

**Dependencies:** LOGIN-03

---

### LOGIN-06 — Frontend: Forgot Password and Reset Flow

**Team:** Frontend
**Size:** S
**Status:** Module-provided baseline (done), host integration required
**Estimation:** Excluded from build totals (module-provided; integration only)

**Description:**
The two-step forgot-password flow is already provided by module endpoints/components. Host app work is route composition, copy/styling alignment, and navigation handling.

**Acceptance Criteria:**
- [ ] Step 1: email input, submits to `POST /auth/custom/forgot-password`, shows neutral success message regardless of whether email exists (no enumeration).
- [ ] Step 2: code + new password + confirm password, submits to `POST /auth/custom/confirm-forgot-password`.
- [ ] On success, redirects to login page with success toast.
- [ ] Resend option available on step 2.

**Dependencies:** LOGIN-03

---

### LOGIN-07 — Frontend: Post-Login Router

**Team:** Frontend
**Size:** S

**Description:**
After any successful login (password or SSO), apply the redirect policy based on user state.

**Acceptance Criteria:**
- [ ] If `onboarding_state.completed = false` → redirect to `/onboarding`.
- [ ] If onboarding complete and no entitlements for requested module → redirect to pricing/paywall placeholder.
- [ ] If onboarding complete and entitled → redirect to module dashboard.
- [ ] Router is a single reusable function called by all login paths (password, Google, Microsoft, auto-login after signup).

**Dependencies:** LOGIN-01, ONB-01, ENT-01

---

## EPIC: Onboarding

---

### ONB-01 — Backend: Onboarding State Machine

**Team:** Backend
**Size:** M

**Description:**
Implement the onboarding progress model. Track which steps a user has completed, what the current step is, and when onboarding was fully completed.

**Acceptance Criteria:**
- [ ] `GET /onboarding/state` returns `{ current_step, completed_steps: [], completed_at }` for authenticated user.
- [ ] `POST /onboarding/advance` advances user to next step, records timestamp.
- [ ] `POST /onboarding/complete` marks onboarding as finished, sets `completed_at`.
- [ ] State is created automatically on first user sync (all new users start at step 1).
- [ ] Calling advance/complete on an already-completed onboarding is idempotent (no error).

**Dependencies:** FOUND-02, SIGNUP-01

---

### ONB-02 — Frontend: Onboarding Wizard

**Team:** Frontend
**Size:** L

**Description:**
Multi-step onboarding UI. Step count and content TBD with product team, but the component shell must support step progression, resume from any step, and completion redirect.

**Acceptance Criteria:**
- [ ] Loads current onboarding state on mount via `GET /onboarding/state`.
- [ ] Resumes at `current_step` if user returns mid-onboarding.
- [ ] Each step advance calls `POST /onboarding/advance`.
- [ ] Final step calls `POST /onboarding/complete` then routes to module dashboard or paywall.
- [ ] Progress indicator visible (e.g. step 2 of 4).
- [ ] Back navigation supported where allowed.
- [ ] Step content is component-slotted — individual step UX can be filled in without changing the wizard frame.

**Dependencies:** ONB-01, LOGIN-07

---

## EPIC: Referral System

---

### REF-01 — Backend: Referral Invite Creation

**Team:** Backend
**Size:** M

**Description:**
Implement referral invite creation. Authenticated user generates a unique invite link that encodes a referral code. When the invitee signs up using this code, the link is attributed.

**Acceptance Criteria:**
- [ ] `POST /referrals/invite` creates a referral record with status `created` and a unique `referral_code`.
- [ ] Returns `{ referral_code, invite_url }` where `invite_url` includes the code as a query param.
- [ ] One user can have multiple open referrals.
- [ ] Self-referral is blocked (invitee email cannot match inviter email at attribution time).
- [ ] Referral record stores: `inviter_user_id`, `referral_code`, `created_at`, `status`, `invitee_user_id` (null until signup).

**Dependencies:** FOUND-02

---

### REF-02 — Backend: Referral Lifecycle Management

**Team:** Backend
**Size:** M

**Description:**
Handle referral status transitions from `created` through to `reward_granted` or `rejected`. Attribution at signup is handled in SIGNUP-02. This ticket covers the remaining transitions.

**Lifecycle:**
`created` → `clicked` (when link is visited) → `signed_up` (SIGNUP-02) → `paid` (BIS-02) → `reward_granted` / `rejected`

**Acceptance Criteria:**
- [ ] `GET /referrals/status` returns list of referrals for authenticated inviter with current statuses.
- [ ] `referrals.status` transitions are recorded with timestamps.
- [ ] Referral marked `clicked` when invite link is visited (endpoint or middleware touch).
- [ ] `rejected` status applied when fraud check fails at reward evaluation time.
- [ ] Referral records are read-only from the inviter's perspective (no manual status editing).

**Dependencies:** REF-01, SIGNUP-02

---

### REF-03 — Backend: Credit Ledger and Balance

**Team:** Backend
**Size:** M

**Description:**
Implement the credit ledger. Credits are granted idempotently when a referral reward is triggered. Credits can also be granted by admins or promos (future). Balance is a derived sum of all credit_ledger rows.

**Acceptance Criteria:**
- [ ] `GET /me/credits` returns `{ balance, currency: "credits" }`.
- [ ] `GET /me/credits/ledger` returns list of credit transactions with reason, amount, source_event_id, created_at.
- [ ] Credit grant inserted idempotently using `source_event_id` as unique key — duplicate calls are ignored.
- [ ] Credit debit supported (for future redemption use) via internal service function only.
- [ ] Admin can grant credits via platform admin API.

**Dependencies:** FOUND-02

---

### REF-04 — Frontend: Referral Center

**Team:** Frontend
**Size:** M

**Description:**
UI for users to view their referral invite link, share it, and see the status and rewards from past referrals.

**Acceptance Criteria:**
- [ ] Displays generated invite link with copy-to-clipboard button.
- [ ] "Generate new invite" button calls `POST /referrals/invite` and refreshes link.
- [ ] Table or list of past referrals: invitee email (if available), status, date, reward amount.
- [ ] Displays current credit balance and a link to the full credit ledger.
- [ ] Empty state shown when no referrals exist yet.

**Dependencies:** REF-01, REF-02, REF-03

---

## EPIC: Billing Integration Seams

---

### BIS-01 — Backend: Payment Webhook Receiver Skeleton

**Team:** Backend
**Size:** M

**Description:**
Build the webhook endpoint that receives payment lifecycle events from the billing provider (e.g. Stripe). This ticket only covers the infrastructure seam: signature verification, idempotency logging, and event routing. Actual billing logic and product catalog are billing-team responsibility.

**Acceptance Criteria:**
- [ ] `POST /webhooks/payments` endpoint registered.
- [ ] Provider webhook signature verified (HMAC). Unverified requests return 401.
- [ ] Incoming event logged to `payment_events` table with idempotency key before any processing.
- [ ] Duplicate events (same idempotency key) return 200 immediately without reprocessing.
- [ ] Event type `payment_succeeded` dispatches to reward evaluator (see BIS-02).
- [ ] All other event types logged and acknowledged with 200 (no-op for now).
- [ ] No pricing, subscription, or invoice logic in this endpoint.

**Dependencies:** FOUND-02

---

### BIS-02 — Backend: Referral Reward Trigger on Payment Event

**Team:** Backend
**Size:** M

**Description:**
When a `payment_succeeded` event is received, evaluate whether the paying user has an eligible open referral and trigger a credit grant to the inviter if so.

> **Design decision required before implementation:** Confirm which exact event qualifies (first payment, first settled invoice, post-refund window). See open design decisions in the plan doc.

**Acceptance Criteria:**
- [ ] On `payment_succeeded` event: look up `invitee_user_id` → check `referrals` for a `signed_up` referral.
- [ ] If eligible: transition referral to `paid`, then evaluate reward conditions.
- [ ] Anti-self-referral check applied.
- [ ] Fraud heuristic check applied (configurable rules).
- [ ] If all conditions pass: insert `referral_reward_events` with idempotency key, insert credit grant in `credit_ledger`, transition referral to `reward_granted`.
- [ ] If any condition fails: transition referral to `rejected`, log reason.
- [ ] Entire evaluation is atomic and idempotent — replaying the same payment event is safe.

**Dependencies:** BIS-01, REF-02, REF-03

---

### BIS-03 — Backend: Entitlement Grant on Payment Event

**Team:** Backend
**Size:** S

**Description:**
When a qualifying payment event is received for a module purchase, grant the user an entitlement for that module. This bridges the billing event to the host app's access control system.

**Acceptance Criteria:**
- [ ] On `payment_succeeded` or `subscription_activated` event: identify the purchased product/module.
- [ ] Upsert `entitlements` row for `(user_id, module_id)`.
- [ ] Entitlement grant is idempotent.
- [ ] `billing_references` table updated with `external_customer_id` and `external_subscription_id`.
- [ ] Module access available immediately on next `GET /me/entitlements` call.

**Dependencies:** BIS-01, ENT-01

---

## EPIC: Entitlements

---

### ENT-01 — Backend: Entitlements Read Endpoint

**Team:** Backend
**Size:** S

**Description:**
Implement the entitlements read endpoint. At this stage, the table is seeded manually or by BIS-03. This ticket delivers the read surface so the frontend and route gating can work end-to-end in tests.

**Acceptance Criteria:**
- [ ] `GET /me/entitlements` returns `[ { module_id, module_name, granted_at, source } ]` for authenticated user.
- [ ] Returns empty list for users with no entitlements (no 404).
- [ ] Result is used by the post-login router (LOGIN-07) to determine redirect.
- [ ] Admin can manually grant entitlements via platform admin API (for testing and promos).

**Dependencies:** FOUND-02

---

### ENT-02 — Backend: Entitlement Guard Middleware / Dependency

**Team:** Backend
**Size:** S

**Description:**
Implement a reusable FastAPI dependency that enforces module entitlement on protected routes. Similar to the auth module's `require_permission`, but checks module entitlement.

**Acceptance Criteria:**
- [ ] `require_entitlement("module_id")` dependency can be added to any route.
- [ ] Returns 403 with clear message if user does not have the entitlement.
- [ ] Returns user context and entitlement metadata if check passes.
- [ ] Works with existing `get_current_user` dependency chain.

**Dependencies:** ENT-01

---

## EPIC: Test Harness

---

### TEST-01 — Mock Signup Entry Page

**Team:** Frontend + Backend
**Size:** S

**Description:**
A minimal placeholder page at `/signup` that allows direct signup without a splash page or wheel-of-fortune context. This is the test harness entry point. It will be replaced by the real splash/wheel funnel epic when that work begins.

**Acceptance Criteria:**
- [ ] `GET /signup` renders the standard signup form.
- [ ] No splash or wheel context is required; attribution fields are optional and default to null.
- [ ] The full signup → confirm → auto-login → onboarding flow completes end-to-end from this page.
- [ ] Post-launch: this route can be replaced or redirected without changing the signup form component.

**Dependencies:** SIGNUP-03

---

### TEST-02 — Auth Flow Integration Tests (Signup → Login → Onboarding)

**Team:** Backend + QA
**Size:** M

**Description:**
Automated tests covering the full new-user journey end-to-end using test doubles for Cognito.

**Acceptance Criteria:**
- [ ] Signup → confirm → auto-login → attribution link → onboarding state created — all assertions pass.
- [ ] Returning login with valid token → loads user profile, onboarding state, entitlements.
- [ ] Token refresh path tested.
- [ ] Logout and session revocation tested.
- [ ] Invalid/expired token returns 401.
- [ ] Unconfirmed user attempting login returns correct error.

**Dependencies:** SIGNUP-02, SIGNUP-03, SIGNUP-04, LOGIN-01, LOGIN-02, ONB-01

---

### TEST-03 — SSO Callback Integration Tests

**Team:** Backend + QA
**Size:** S

**Description:**
Automated tests covering the OAuth2 callback path for Google and Microsoft logins.

**Acceptance Criteria:**
- [ ] Valid callback code → token exchange → user sync → session creation — all pass.
- [ ] New SSO user gets profile and onboarding state created automatically.
- [ ] Returning SSO user loads existing profile without creating duplicates.
- [ ] Expired or invalid code returns 400 with clear error.

**Dependencies:** LOGIN-04, SIGNUP-01

---

### TEST-04 — Referral and Reward Tests

**Team:** Backend + QA
**Size:** M

**Description:**
Automated tests for the referral lifecycle and credit reward flow.

**Acceptance Criteria:**
- [ ] Invite creation → attribution at signup → payment event → reward granted — full flow passes.
- [ ] Duplicate payment webhook does not double-grant credits.
- [ ] Self-referral is rejected.
- [ ] Fraud-flagged referral transitions to `rejected`.
- [ ] Credit ledger balance is correct after multiple grants.

**Dependencies:** REF-01, REF-02, REF-03, BIS-01, BIS-02

---

### TEST-05 — Entitlement Gating Tests

**Team:** Backend + QA
**Size:** S

**Description:**
Automated tests for module access control.

**Acceptance Criteria:**
- [ ] User with entitlement can access protected module route.
- [ ] User without entitlement gets 403.
- [ ] Admin-granted entitlement takes effect immediately.
- [ ] Entitlement granted via payment event is reflected in `GET /me/entitlements`.

**Dependencies:** ENT-01, ENT-02, BIS-03

---

## Ticket Summary

| ID | Title | Team | Size | Phase |
|---|---|---|---|---|
| INFRA-01 | Cognito User Pool and App Clients | DevOps/BE | M | 1 |
| INFRA-02 | Google SSO Federation | DevOps/BE | S | 1 |
| INFRA-03 | Microsoft SSO Federation | DevOps/BE | S | 1 |
| FOUND-01 | Host App Scaffold | BE | M | 1 |
| FOUND-02 | Host Database Schema and Migrations | BE | L | 1 |
| FOUND-03 | B2C Role and Access Model | BE | S | 1 |
| SIGNUP-01 | User Sync and Profile Creation | BE | M | 2 |
| SIGNUP-02 | Signup Attribution Linking | BE | S | 2 |
| SIGNUP-03 | Signup Page | FE | M | 2 |
| SIGNUP-04 | Post-Signup Auto-Login Transition | FE | S | 2 |
| LOGIN-01 | Post-Login Pipeline | BE | M | 2 |
| LOGIN-02 | Refresh Cookie and Session Registration | BE | S | 2 |
| LOGIN-03 | Login Page (Password + Google + Microsoft) | FE | M | 2 |
| LOGIN-04 | SSO Callback Handler | FE | M | 2 |
| LOGIN-05 | Set Password Page | FE | S | 2 |
| LOGIN-06 | Forgot Password Flow | FE | S | 2 |
| LOGIN-07 | Post-Login Router | FE | S | 2 |
| ONB-01 | Onboarding State Machine | BE | M | 3 |
| ONB-02 | Onboarding Wizard | FE | L | 3 |
| REF-01 | Referral Invite Creation | BE | M | 3 |
| REF-02 | Referral Lifecycle Management | BE | M | 3 |
| REF-03 | Credit Ledger and Balance | BE | M | 3 |
| REF-04 | Referral Center UI | FE | M | 3 |
| BIS-01 | Payment Webhook Skeleton | BE | M | 4 |
| BIS-02 | Referral Reward Trigger | BE | M | 4 |
| BIS-03 | Entitlement Grant on Payment Event | BE | S | 4 |
| ENT-01 | Entitlements Read Endpoint | BE | S | 2 |
| ENT-02 | Entitlement Guard Middleware | BE | S | 2 |
| TEST-01 | Mock Signup Entry Page | FE/BE | S | 2 |
| TEST-02 | Auth Flow Integration Tests | BE/QA | M | 2 |
| TEST-03 | SSO Callback Integration Tests | BE/QA | S | 2 |
| TEST-04 | Referral and Reward Tests | BE/QA | M | 4 |
| TEST-05 | Entitlement Gating Tests | BE/QA | S | 2 |

**Total tickets tracked: 33**

**Estimation-included tickets: 26**

**Estimation-excluded tickets: 7 (module-provided integration tickets)**

---

## Size Key

| Size | Rough effort |
|---|---|
| S | < 1 day |
| M | 1–3 days |
| L | 3–5 days |
| XL | 1 week+ |

---

## Estimated Build Effort (Excluding Module-Provided Tickets)

Assumptions for experienced dev with agent pairing:
- S: 1 to 3 hours
- M: 4 to 8 hours
- L: 12 to 20 hours

Included ticket mix:
- S x 12
- M x 12
- L x 2

Estimated total (implementation only, excludes module-provided integration tickets):
- Low: 84 hours
- High: 172 hours

---

## Open Design Decisions (Must Resolve Before Phase 4)

- [ ] **Reward qualifying event:** Which exact billing event triggers referral reward — first payment, first settled invoice, or post-refund window? *(Blocks BIS-02)*
- [ ] **Reward scope:** Does one invitee trigger one reward total (first purchase) or one reward per module purchased? *(Blocks BIS-02 schema)*
- [ ] **Entitlement source of truth:** Does billing service push entitlements to host app, or does host app query billing on demand? *(Affects BIS-03 write path)*
- [ ] **Onboarding steps:** How many steps and do they vary by selected module interest? *(Blocks ONB-02 content)*

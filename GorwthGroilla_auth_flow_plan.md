# GrowthGorilla Host App Auth Flow Plan

## 1. Purpose

This plan defines how the new GrowthGorilla host app should implement a full B2C auth and growth journey using the reusable `auth_usermanagement` module as the shared auth core.

Principle:
- Keep reusable auth logic in the module.
- Implement app-specific growth, referral, payment, onboarding, and module-entitlement logic in the host app.

---

## 2. Requirements Summary

Business requirements captured:
- B2C app with single users (no tenant hierarchy for product behavior).
- One app owner (superadmin/platform admin).
- User invite mode with referral reward: inviter gets free credit after invitee signs up and pays.
- Login methods: email/password + Google + Microsoft SSO.
- Onboarding stage after signup.
- 4 purchasable modules in one app account.
- 20 splash pages leading to wheel-of-fortune offer page, then to variant-specific signup pages.
- All signup variants use the same Cognito user pool.

---

## 3. Solution Boundaries

## Reusable module responsibilities (already available)
- Cognito auth integration (hosted UI and custom UI).
- JWT verification and session sync patterns.
- Custom auth endpoints for login/signup/confirm/password reset.
- Invitation primitives and user-management baseline.
- Security middleware and guards.

## Host app responsibilities (to build)
- Funnel attribution and splash-page tracking.
- Wheel-of-fortune offer generation and claim handling.
- Signup page variant routing.
- Referral program logic and credit ledger.
- Payment integration and reward trigger logic.
- Onboarding state machine.
- Product/module entitlements for 4 modules.
- B2C-specific role setup and route policies.

---

## 4. Target End-to-End Auth and Growth Flow

## Anonymous acquisition flow
1. User lands on splash page `S1..S20`.
2. Host app stores acquisition context:
   - splash_id
   - campaign_id / utm params
   - ref code (if any)
   - session id or anonymous cookie id
3. User enters wheel-of-fortune page.
4. Wheel assigns an offer (discount/benefit) with deterministic or controlled randomness.
5. Host app persists offer claim against anonymous session.
6. User is directed to a signup variant page (`/signup/vA`, `/signup/vB`, etc.) based on splash source.

## Signup journey
1. Signup page submits to module custom signup flow (`/auth/custom/signup`) or hosted UI equivalent.
2. If confirmation is required, user completes confirm flow (`/auth/custom/confirm` + optional resend).
3. After successful signup confirmation, frontend immediately initiates login.
4. Login response returns Cognito tokens.
5. Frontend runs session establishment:
   - store refresh token in secure HttpOnly cookie via backend endpoint.
   - register backend session.
6. Backend syncs/creates local user profile if not present.
7. Host app links pre-auth attribution data to the authenticated user.
8. Host app creates onboarding state for this new user.
9. User is redirected to onboarding start.

## Login after signup (required behavior)
- New user should not remain in a dead-end "signup complete" state.
- After signup confirmation:
  - run login immediately (email/password or SSO callback completion),
  - establish refresh cookie + backend session,
  - complete user sync,
  - redirect to onboarding step 1 (or module starter page if onboarding already complete).

## Returning login journey
1. User selects login method:
   - email/password
   - Google SSO
   - Microsoft SSO
2. Tokens are obtained from same Cognito user pool.
3. Backend verifies token and loads user profile + entitlements.
4. App applies post-login router:
   - if onboarding incomplete -> continue onboarding,
   - else if paywall required -> pricing/checkout,
   - else -> primary dashboard/module home.

## Invite and referral reward flow
1. Existing user creates invite in host app.
2. Invitee signs up via invite link.
3. Payment webhook confirms qualifying purchase.
4. Reward engine validates referral criteria.
5. Inviter receives credit transaction (idempotent grant).
6. Credit balance updates and audit record is stored.

---

## 5. Host App Architecture Actions

## A. Environment and Cognito configuration

> **Custom UI and Cognito app clients:**
> Using `AUTH_MODE=custom_ui` removes Cognito-hosted login pages but does **not** remove the need for a Cognito app client — the backend still uses the app client's `client_id` to call Cognito auth APIs, and Google/Microsoft federation is also wired through the app client.
>
> **How many clients:** One user pool + one app client per deployment environment (dev / staging / prod). You do **not** need four clients for four modules — all modules share one identity. A second app client is only warranted if you add a genuinely separate surface (e.g., a native mobile app with different callback URLs).

- [ ] Configure one Cognito user pool for all signup variants.
- [ ] Create one app client per environment (dev / staging / prod). Enable `ALLOW_USER_PASSWORD_AUTH` on each (required for custom UI password login).
- [ ] Configure Google OAuth federation inside Cognito (set redirect URI to Cognito's `/oauth2/idpresponse`).
- [ ] Configure Microsoft/Azure AD OIDC federation inside Cognito.
- [ ] Enable Google and Microsoft identity providers on the app client.
- [ ] Set callback URLs for all frontend environments (required even in custom UI mode for SSO redirect).
- [ ] Set sign-out URLs for all frontend environments.
- [ ] Validate token claims (`iss`, `aud`/`client_id`) against host env.

## B. Role and access model for B2C
- [ ] Define platform owner account as superadmin.
- [ ] Define standard end-user role(s).
- [ ] Disable or minimize tenant/space-facing UX paths not needed by B2C behavior.
- [ ] Keep security guards and permission checks for admin APIs.

## C. Data model implementation (host-owned tables)

**Auth/growth tables — build now:**
- [ ] `acquisition_sessions` (anonymous pre-auth tracking).
- [ ] `splash_visits` (which splash started the journey).
- [ ] `wheel_offers` (offer metadata, odds, validity).
- [ ] `wheel_claims` (what user/session won and redeemed).
- [ ] `signup_variants` (variant mapping and config).
- [ ] `signup_attribution_links` (attach pre-auth data to user_id after signup).
- [ ] `onboarding_progress` (step state, completion timestamps).
- [ ] `referrals` (inviter, invitee, status lifecycle).
- [ ] `referral_reward_events` (idempotent reward issuance events).
- [ ] `credit_ledger` (credits grant/debit with reason and source event).

**Build now as integration seams (billing events will feed these):**
- [ ] `entitlements` (user access per module — populated by billing events; needs to exist now so onboarding and route gating work end-to-end in tests).
- [ ] `billing_references` (stores `external_customer_id`, `external_subscription_id`, `last_payment_event_id` per user — thin table owned by host app, written by webhook receiver).
- [ ] `payment_events` (raw incoming webhook log with idempotency key — owned by host app; actual commerce data stays in billing service).

**Billing and Subscription responsibility (do not build now):**
- Pricing plans, plan tiers, trial logic.
- Subscription lifecycle (create, upgrade, downgrade, cancel, renew).
- Invoices, taxes, proration, refunds, dunning/retry logic.
- Billing portal and payment method management.
- Billing ticket/support workflows.
- Full financial reconciliation and audit trail.
- The `products` table — pricing and product catalog are billing-owned.

## D. API layer (host-owned endpoints)

**Build now:**
- [ ] Funnel endpoints:
  - [ ] `POST /growth/session/start`
  - [ ] `POST /growth/wheel/spin`
  - [ ] `POST /growth/wheel/claim`
- [ ] Signup attribution endpoint:
  - [ ] `POST /growth/signup/link-attribution`
- [ ] Onboarding endpoints:
  - [ ] `GET /onboarding/state`
  - [ ] `POST /onboarding/advance`
  - [ ] `POST /onboarding/complete`
- [ ] Entitlement read endpoint (populated later by billing events — stub now so route gating compiles):
  - [ ] `GET /me/entitlements`
- [ ] Referral endpoints:
  - [ ] `POST /referrals/invite`
  - [ ] `GET /referrals/status`
- [ ] Credits endpoints:
  - [ ] `GET /me/credits`
  - [ ] `GET /me/credits/ledger`
- [ ] Payment webhook skeleton — build now (signature verification + idempotency key logging + reward trigger hook):
  - [ ] `POST /webhooks/payments`

**Billing and Subscription responsibility (do not build now):**
- Checkout session initiation endpoint.
- Subscription management endpoints (upgrade, cancel, portal redirect).
- Invoice and billing history endpoints.
- Payment method management endpoints.

## E. Frontend flow implementation
- [ ] Build 20 splash page routes and analytics tagging.
- [ ] Build wheel-of-fortune page and claim UX.
- [ ] Build signup variant pages with shared form components.
- [ ] Build login page with 3 methods (password, Google, Microsoft).
- [ ] Build post-signup auto-login transition screen.
- [ ] Build onboarding wizard and resume behavior.
- [ ] Build module switcher and entitlement-aware navigation.
- [ ] Build referral center (invite link, history, earned credits).

---

## 6. Detailed Signup Journey Implementation Plan

## Step SG-1: Pre-auth context capture
- [ ] On splash entry, create acquisition session record.
- [ ] Store UTM/ref/splash/wheel context in signed cookie + DB record.
- [ ] Add TTL and tamper protection for context token.

## Step SG-2: Variant routing
- [ ] Define mapping table from splash_id to signup_variant.
- [ ] Route to correct signup page.
- [ ] Include variant id in signup submit payload metadata.

## Step SG-3: Account creation
- [ ] Call module endpoint `/auth/custom/signup`.
- [ ] Handle `needs_confirmation` branch.
- [ ] Expose resend-confirmation UX.

## Step SG-4: Confirmation
- [ ] Submit code to `/auth/custom/confirm`.
- [ ] Handle expired/invalid code with retry UX.

## Step SG-5: Immediate login after signup
- [ ] Trigger `/auth/custom/login` automatically once confirmation succeeds.
- [ ] On success, call host session endpoints to store refresh cookie and register session.
- [ ] Ensure token/session setup is atomic (rollback local state on failure).

## Step SG-6: Post-auth linking
- [ ] Link acquisition + wheel + variant data to authenticated user.
- [ ] Persist referred_by metadata if referral token exists.

## Step SG-7: Redirect policy
- [ ] If onboarding incomplete -> onboarding step 1.
- [ ] Else -> module dashboard or pricing page based on entitlements.

---

## 7. Detailed Login Journey Implementation Plan

## Password login
- [ ] Use `/auth/custom/login`.
- [ ] If challenge `NEW_PASSWORD_REQUIRED`, route to set-password flow.
- [ ] On authenticated response, create cookie/session and load profile.

## Google login
- [ ] Configure Cognito hosted button for Google provider.
- [ ] Handle callback and token exchange.
- [ ] Run same post-login pipeline (session + profile + redirect rules).

## Microsoft login
- [ ] Configure Cognito OIDC provider for Microsoft/Azure AD.
- [ ] Handle callback and token exchange.
- [ ] Run same post-login pipeline.

## Shared post-login pipeline
- [ ] Verify token and sync user identity.
- [ ] Fetch onboarding state.
- [ ] Fetch entitlements.
- [ ] Apply redirect policy.
- [ ] Emit analytics event `login_success` with method and campaign context.

---

## 8. Referral + Payment Reward Plan

## Referral lifecycle states
- [ ] `created`
- [ ] `clicked`
- [ ] `signed_up`
- [ ] `paid` ← transition triggered by billing event, not built here
- [ ] `reward_granted`
- [ ] `rejected`

## Reward conditions (auth/growth responsibility)
- [ ] Invitee must be distinct account (anti-self-referral).
- [ ] Invitee must have a qualifying billing event linked to their user_id (exact qualifying event TBD — see open design decisions).
- [ ] Reward is granted once per qualifying invite (idempotent key).
- [ ] Fraud heuristics: same-device / same-IP / duplicate email patterns.

## Payment webhook integration — build now (skeleton)
- [ ] Register `POST /webhooks/payments` endpoint.
- [ ] Verify payload signature (provider-specific HMAC verification).
- [ ] Log raw event to `payment_events` with idempotency key — reject duplicate keys immediately.
- [ ] Map event to `user_id` via `billing_references.external_customer_id`.
- [ ] Publish internal `payment_succeeded` domain event (in-process or queue) → reward evaluator consumes it.
- [ ] Do NOT implement pricing, invoice, or subscription logic here.

> **Billing and Subscription responsibility:** Payment source-of-truth, subscription state, refund processing, tax, and financial reconciliation are owned by the billing feature. The webhook skeleton above is the integration seam only.

## Credit issuance (auth/growth responsibility)
- [ ] On qualifying billing event: evaluate referral eligibility.
- [ ] Insert `referral_reward_events` with idempotency key.
- [ ] Insert `credit_ledger` grant row if not already granted.
- [ ] Recompute cached credit balance.
- [ ] Notify inviter (email/in-app notification).

---

## 9. Onboarding and Entitlements Plan

## Onboarding model
- [ ] Define ordered steps with optional branching per module interest.
- [ ] Track `current_step`, `completed_steps`, `completed_at`.
- [ ] Support resume and skip rules where allowed.

## Entitlements model
- [ ] One user can own multiple module entitlements.
- [ ] Entitlement source can be purchase, promo, referral reward, or admin grant.
- [ ] Middleware/guards should enforce module access per route.

## Route gating policy
- [ ] Not authenticated -> login/signup.
- [ ] Authenticated, onboarding incomplete -> onboarding.
- [ ] Authenticated, onboarding complete, no entitlement for target module -> paywall/pricing.
- [ ] Authenticated, entitled -> module route.

---

## 10. Security and Compliance Actions

- [ ] Enforce secure cookies in production.
- [ ] Add CSRF protections where cookie-auth endpoints are used.
- [ ] Rate limit auth and referral endpoints.
- [ ] Validate referral tokens and campaign context signatures.
- [ ] Avoid email/user enumeration in forgot-password and invite checks.
- [ ] Add audit logs for admin, referral, credit, and entitlement changes.
- [ ] Add data retention policy for acquisition tracking data.

---

## 11. Analytics and Observability Plan

- [ ] Event taxonomy:
  - [ ] splash_view
  - [ ] wheel_spin
  - [ ] wheel_claim
  - [ ] signup_started
  - [ ] signup_confirmed
  - [ ] login_success
  - [ ] onboarding_completed
  - [ ] referral_created
  - [ ] referral_paid
  - [ ] referral_reward_granted
  - [ ] module_purchased
- [ ] Build conversion funnel dashboards per splash variant.
- [ ] Track auth success/failure by login method.
- [ ] Track reward cost and referral ROI.

---

## 12. Delivery Phases

## Phase 1: Foundations
- [ ] Cognito + SSO config complete.
- [ ] B2C role model configured.
- [ ] Core host schema migrations created.

## Phase 2: Auth and journey core
- [ ] Signup variant routing and forms.
- [ ] Post-signup immediate login path.
- [ ] Shared post-login redirect policy.

## Phase 3: Growth mechanics
- [ ] Splash and wheel tracking + claims.
- [ ] Referral lifecycle and invite links.

## Phase 4: Commerce and rewards
- [ ] Payment webhook integration.
- [ ] Reward engine and credit ledger.
- [ ] Module entitlements and paywall integration.

## Phase 5: Hardening and launch
- [ ] End-to-end tests and abuse tests.
- [ ] Monitoring/alerting dashboards.
- [ ] Runbook and rollback plan.

---

## 13. Testing Matrix (Must Pass Before Launch)

## Auth tests
- [ ] Signup + confirm + immediate login success.
- [ ] Signup retry and invalid confirmation code handling.
- [ ] Password login success/failure.
- [ ] Google login callback success/failure.
- [ ] Microsoft login callback success/failure.
- [ ] Token refresh and logout behavior.

## Journey tests
- [ ] All 20 splash pages map to intended signup variants.
- [ ] Wheel offer persistence from anonymous to authenticated state.
- [ ] Post-login redirect correctness by onboarding and entitlement state.

## Referral and payment tests
- [ ] Invite link attribution from click to signup.
- [ ] Reward grant on first qualifying payment.
- [ ] Duplicate webhook does not double-grant credits.
- [ ] Fraud/edge cases are rejected correctly.

## Entitlement tests
- [ ] Purchase unlocks target module.
- [ ] User can own multiple module entitlements.
- [ ] Access denied for non-entitled module routes.

---

## 14. Open Design Decisions

**Decide early — these affect the data model or integration seam design:**
- [ ] What exact billing event qualifies a referral reward — payment intent success, first settled invoice, or post-refund window? *(Affects webhook receiver logic and `referral_reward_events` schema.)*
- [ ] Does one invitee trigger one reward (first purchase only) or one reward per module purchased? *(Affects `referral_reward_events` primary key design.)*
- [ ] Who is the source of truth for module entitlements — billing service pushes to host app, or host app queries billing on demand? *(Affects `entitlements` table write path and caching.)*
- [ ] Should onboarding vary by signup variant or by selected module interest? *(Affects `onboarding_progress` step schema.)*

**Can be deferred — do not affect data model or seam design:**
- [ ] Referral reward amount: fixed credits vs tiered by product price.
- [ ] Can wheel offers stack with referral or campaign discounts.
- [ ] Specific fraud thresholds and manual review criteria.

---

## 15. Execution Checklist (Condensed)

- [ ] Finalize auth architecture and host/module boundaries.
- [ ] Implement host schema and migrations.
- [ ] Implement signup and login journeys end-to-end.
- [ ] Implement attribution and wheel flows.
- [ ] Implement referral and credit engine.
- [ ] Implement payment webhooks and entitlements.
- [ ] Implement onboarding and route gating.
- [ ] Complete integration tests, security tests, and launch readiness review.

---

## 16. Final Notes

- This plan keeps the reusable auth module generic and reusable across apps.
- All GrowthGorilla-specific behavior is intentionally host-owned.
- Any future module changes should be accepted only if they are generic enough to benefit multiple host applications.

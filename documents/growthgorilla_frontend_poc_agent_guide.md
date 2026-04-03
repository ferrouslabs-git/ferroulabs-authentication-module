# GrowthGorilla Frontend POC - Agent Build Guide

Purpose: provide an execution-ready guide an AI coding agent can follow to build a frontend-only GrowthGorilla POC on branch `feat/growthgorilla-frontend-poc-auth`.

Scope lock:
- Frontend only (`frontend/`)
- No backend code edits
- Build auth entry experience with mock growth funnel
- Include 8 splash mock pages + 1 mock wheel page
- Implement two mock flows:
  - Direct auth flow: login/forgot-password OR signup -> payment page
  - Splash funnel flow: splash -> wheel -> signup -> payment page
- Defer invite, referral rewards, billing backend integration, and real payment processing

Primary source docs used:
- `GorwthGroilla_auth_flow_plan.md`
- `auth-related-tickets.md`

---

## 1. POC Outcomes

By end of this POC, user should be able to:
- Land on one of 8 splash pages.
- Click through to wheel page.
- Spin wheel and receive one of 3 mock offers:
  - `1 month free`
  - `$20 off`
  - `20% off full modules`
- Use direct auth flow:
  - login page supports normal login and forgot-password mode
  - signup redirects to payment page
- Use splash funnel flow:
  - splash -> wheel -> signup -> payment page
- Land on payment page and see carried context where relevant:
  - splash id
  - module target
  - offer

Payment pages are mock only (buttons have no backend action).

---

## 2. Implementation Rules (Hard)

- Do not edit anything under `backend/`.
- Reuse existing module auth UI and hooks from `frontend/src/auth_usermanagement`.
- Do not create new backend API contracts for the POC.
- Keep all growth/funnel data in frontend state/session storage.
- If auth fails, retain funnel context and let user retry.

---

## 3. Route Map To Implement

Add/adjust routes in frontend app shell:

- `/` -> redirect to `/splash/S1` (or a simple selector page linking to S1..S8)
- `/splash/:splashId` -> mock splash page
- `/wheel` -> mock wheel spin page
- `/signup` -> signup screen (module form embedded)
- `/login` -> login page with forgot-password mode toggle
- `/payment/basic` -> mock payment page for direct signup flow
- `/payment/offer` -> mock payment page for splash+wheel flow

Optional helper route:
- `/debug/funnel` -> inspect current funnel context JSON

---

## 4. Splash-to-Module Mapping (8 pages -> 4 modules)

Use deterministic mapping:

- `S1`, `S2` -> `module_a`
- `S3`, `S4` -> `module_b`
- `S5`, `S6` -> `module_c`
- `S7`, `S8` -> `module_d`

Display a module-specific message on each splash page.

---

## 5. Funnel Context Contract (Frontend Only)

Define one payload object persisted in `sessionStorage`:

```json
{
  "splashId": "S1",
  "moduleTarget": "module_a",
  "offer": {
    "code": "ONE_MONTH_FREE",
    "label": "1 month free"
  },
  "capturedAt": "ISO-8601 timestamp"
}
```

Storage key:
- `gg_funnel_context_v1`

Rules:
- Set `splashId` + `moduleTarget` when entering splash route.
- Set `offer` only after wheel spin.
- Preserve context across `/signup`, `/payment/offer`.
- Clear context only when user explicitly restarts journey.

---

## 6. Wheel Logic (Mock)

Offer catalog:
- `ONE_MONTH_FREE` -> `1 month free`
- `TWENTY_DOLLARS_OFF` -> `$20 off`
- `TWENTY_PERCENT_OFF_FULL` -> `20% off full modules`

Selection policy (POC):
- Uniform random selection via `Math.random()`.
- One spin per session by default.
- Show result card and CTA: "Continue to Signup".

No payment, coupon redemption, or backend persistence in this phase.

---

## 7. Auth Integration Strategy

Reuse module components/services:
- `CustomSignupForm`
- `CustomLoginForm`
- `ForgotPasswordForm`
- existing `AuthProvider` and `useAuth()` where needed

### Flow A: Direct Auth

1. User lands on `/login`.
2. User can either:
  - login directly, or
  - switch to forgot-password mode on the same page.
3. User can also go to `/signup` from login.
4. On signup confirmed, route to `/payment/basic`.

### Flow B: Splash Funnel

1. User lands on `/splash/:splashId`.
2. User proceeds to `/wheel` and spins.
3. Offer is saved in session context.
4. User continues to `/signup`.
5. On signup confirmed, route to `/payment/offer`.
6. Payment page shows splash/module/offer context.

Payment pages are display-only in this POC. Any CTA should be no-op.

---

## 8. Mobile-First UI Guidance (Phone Web View)

This POC is a web app, but primary review is on phone-sized viewports.

Requirements:

- Design for `360px` to `430px` width first.
- Keep all auth and payment screens in a centered mobile frame (`max-width: 420px`).
- Use large tap targets (`min-height: 44px`) for buttons/inputs.
- Keep one-column layout only for all flow pages.
- Avoid side-by-side blocks in payment UI.
- Keep key CTA visible without horizontal scroll.
- Use placeholder blocks for product/payment images where needed.

Suggested visual structure per page:

- Header strip with product badge/logo placeholder
- Primary title
- Form/content area
- Single primary CTA row
- Optional secondary text links

---

## 9. Suggested File Plan (Frontend)

Create under `frontend/src/mockapp/growthgorilla/`:

- `routes/GrowthGorillaApp.jsx` (route composition)
- `pages/SplashPage.jsx`
- `pages/WheelPage.jsx`
- `pages/SignupPage.jsx`
- `pages/LoginPage.jsx`
- `pages/PaymentBasicPage.jsx`
- `pages/PaymentOfferPage.jsx`
- `components/FunnelBanner.jsx`
- `state/funnelContext.js` (get/set/clear helpers)
- `constants/splashMap.js`
- `constants/offers.js`

Edit existing:
- `frontend/src/App.jsx` -> mount new route tree (or replace current shell for POC)

Keep existing auth module files unchanged.

---

## 10. Minimal Acceptance Checklist

- [ ] User can navigate all splash pages `S1` to `S8`.
- [ ] Correct module mapping shown for each splash id.
- [ ] Wheel spins and selects one of 3 offers.
- [ ] Direct flow works: `/login` -> login/forgot-password OR `/signup`.
- [ ] Signup in direct flow routes to `/payment/basic`.
- [ ] Splash funnel flow works: splash -> wheel -> signup -> `/payment/offer`.
- [ ] Offer persists through splash funnel and appears on `/payment/offer`.
- [ ] Signup flow works with existing custom auth endpoints.
- [ ] Payment pages are UI-only: no backend actions are triggered.
- [ ] Pages render cleanly in phone viewport (360x800) with no horizontal overflow.
- [ ] No backend file changes in git diff.

---

## 11. Agent Execution Order

1. Create funnel constants + storage helpers.
2. Build splash page and module mapping.
3. Build wheel page and offer persistence.
4. Build login page with forgot-password mode.
5. Build signup page routing to payment pages by flow context.
6. Build two payment pages (`basic`, `offer`) with mobile-first layout and no-op CTA.
6. Wire routes.
7. Run frontend dev server and test full flow manually.
8. Verify git diff contains only `frontend/` changes.

---

## 12. Manual Test Script

Flow A (direct auth):
1. Open `/login`.
2. Verify login UI is visible.
3. Switch to forgot-password mode and verify form state.
4. Go to `/signup`, complete mock signup.
5. Verify redirect to `/payment/basic`.

Flow B (splash funnel):
1. Open `/splash/S3`.
2. Verify module target shows `module_b`.
3. Continue to wheel, spin, note offer.
4. Continue to signup, create/confirm account.
5. Verify redirect to `/payment/offer`.
6. Verify payment page shows S3 + module_b + selected offer.

---

## 13. Explicitly Deferred

Do not implement now:
- Invite flow UX
- Referral tracking and reward issuance
- Billing checkout and payment collection
- Entitlement backend integration
- Real splash analytics pipeline
- Wheel odds tuning/AB testing infra

These are phase-2+ items after auth funnel POC validation.

---

## 14. Definition of Done for This Branch

POC is done when:
- Frontend-only branch demonstrates end-to-end mocked growth funnel + real auth entry/exit.
- Team can test both mock flows:
  - direct login/signup -> payment basic
  - splash -> wheel -> signup -> payment offer
- Code is isolated and can be merged or discarded without backend impact.

---

## 15. Current Working Flow (As Implemented)

This section documents the current expected behavior in the POC branch.

### Entry and Route Selection

- `/` shows a simple flow selector page.
- `Normal Route` leads to direct auth flow.
- `Splash Route` leads to splash funnel flow.

### Flow A: Direct Auth

1. User opens `/login`.
2. User can:
   - login normally, or
   - use forgot-password mode.
3. User can move to `/signup`.
4. On successful signup confirmation, user is routed to direct mock payment page (`/payment/basic`).

### Flow B: Splash Funnel

1. User opens `/splash/:splashId`.
2. User continues to `/wheel` and spins for an offer.
3. Offer is stored in `sessionStorage` under `gg_funnel_context_v1`.
4. User continues to `/signup`.
5. On successful signup confirmation, user is routed to offer mock payment page (`/payment/offer`).
6. Offer payment page displays splash/module/offer context from funnel storage.

### Payment Pages (Current POC Rule)

- Payment pages are mock-only.
- Buttons are no-op and do not call real checkout or billing APIs.
- No entitlement activation happens in this POC phase.

---

## 16. What Host App Should Build Next (Post-POC)

Once UX is accepted, move from mock flow to host-owned implementation in phases.

### A. Route and UX Hardening

- Keep dual entry model (`normal` and `splash`) if product still needs both.
- Keep mobile-first layout patterns from this POC.
- Replace placeholder payment UI with real pricing/paywall screens owned by host app.

### B. Persist Funnel Data in Host Backend

Replace session-only funnel context with host persistence:

- `acquisition_sessions`
- `splash_visits`
- `wheel_claims`
- `signup_attribution_links`

Implement host endpoints:

- `POST /growth/session/start`
- `POST /growth/wheel/spin`
- `POST /growth/wheel/claim`
- `POST /growth/signup/link-attribution`

### C. Replace Mock Payment with Real Integration Seam

- Keep payment source-of-truth in billing domain.
- Host app should implement only integration seam routes and idempotent event handling.
- Replace no-op payment buttons with:
  - checkout initiation route call (host/billing boundary), or
  - billing redirect flow.

### D. Post-Payment Routing and Access

- After qualifying payment, write/update host `entitlements` records.
- Apply redirect policy:
  - onboarding incomplete -> onboarding
  - no entitlement for requested module -> pricing/paywall
  - entitled -> module home

### E. Operational Readiness

- Add analytics events for both entry flows (`login_start`, `signup_start`, `wheel_spin`, `payment_start`, `payment_success`).
- Add abuse/rate-limit controls on auth and growth endpoints.
- Add integration tests covering both flows end-to-end (normal and splash).

This keeps the module reusable while moving GrowthGorilla-specific business behavior into host-owned code where it belongs.

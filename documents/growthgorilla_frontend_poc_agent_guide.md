# GrowthGorilla Frontend POC - Agent Build Guide

Purpose: provide an execution-ready guide an AI coding agent can follow to build a frontend-only GrowthGorilla POC on branch `feat/growthgorilla-frontend-poc-auth`.

Scope lock:
- Frontend only (`frontend/`)
- No backend code edits
- Build auth entry experience with mock growth funnel
- Include 8 splash mock pages + 1 mock wheel page
- Implement signup/login/callback/onboarding/dashboard flow
- Defer invite, referral rewards, billing, payment pages

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
- Continue to signup/login.
- Complete auth via existing `auth_usermanagement` components/endpoints.
- Reach onboarding/dashboard and see carried context:
  - splash id
  - module target
  - offer

No payment flow or entitlement purchase is required in this POC.

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
- `/login` -> login screen (module form + SSO buttons)
- `/callback` -> SSO callback completion page
- `/onboarding` -> mock onboarding page (POC)
- `/dashboard` -> mock dashboard page showing carried offer/module context

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
- Preserve context across `/signup`, `/login`, `/callback`.
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
- existing `AuthProvider` and `useAuth()`
- existing callback behavior at `/callback`

Expected flow:
1. From wheel -> `/signup` (or `/login`).
2. On signup confirmed, move to login step automatically or navigate to `/login`.
3. On authenticated state, route to `/onboarding` first.
4. On onboarding complete action, route to `/dashboard`.
5. Both onboarding and dashboard display funnel context if present.

SSO behavior:
- Keep Google/Microsoft entries in login UI.
- `/callback` should complete session as already supported by module context.

---

## 8. Suggested File Plan (Frontend)

Create under `frontend/src/mockapp/growthgorilla/`:

- `routes/GrowthGorillaApp.jsx` (route composition)
- `pages/SplashPage.jsx`
- `pages/WheelPage.jsx`
- `pages/SignupPage.jsx`
- `pages/LoginPage.jsx`
- `pages/OnboardingPage.jsx`
- `pages/DashboardPage.jsx`
- `components/FunnelBanner.jsx`
- `state/funnelContext.js` (get/set/clear helpers)
- `constants/splashMap.js`
- `constants/offers.js`

Edit existing:
- `frontend/src/App.jsx` -> mount new route tree (or replace current shell for POC)

Keep existing auth module files unchanged.

---

## 9. Minimal Acceptance Checklist

- [ ] User can navigate all splash pages `S1` to `S8`.
- [ ] Correct module mapping shown for each splash id.
- [ ] Wheel spins and selects one of 3 offers.
- [ ] Offer persists through signup/login and appears after auth.
- [ ] Signup flow works with existing custom auth endpoints.
- [ ] Login flow works for password path.
- [ ] Callback route does not break the journey.
- [ ] Onboarding page is reachable post-auth.
- [ ] Dashboard shows `splashId`, `moduleTarget`, and `offer`.
- [ ] No backend file changes in git diff.

---

## 10. Agent Execution Order

1. Create funnel constants + storage helpers.
2. Build splash page and module mapping.
3. Build wheel page and offer persistence.
4. Build signup/login wrapper pages around module components.
5. Build onboarding/dashboard pages displaying carried context.
6. Wire routes.
7. Run frontend dev server and test full flow manually.
8. Verify git diff contains only `frontend/` changes.

---

## 11. Manual Test Script

1. Open `/splash/S3`.
2. Verify module target shows `module_b`.
3. Continue to wheel, spin, note offer.
4. Continue to signup, create/confirm account (or use login).
5. After auth, verify redirect to onboarding.
6. Continue to dashboard.
7. Verify funnel summary still visible (S3 + module_b + chosen offer).
8. Hard refresh dashboard and verify sessionStorage-backed context remains.

---

## 12. Explicitly Deferred

Do not implement now:
- Invite flow UX
- Referral tracking and reward issuance
- Billing checkout and payment collection
- Entitlement backend integration
- Real splash analytics pipeline
- Wheel odds tuning/AB testing infra

These are phase-2+ items after auth funnel POC validation.

---

## 13. Definition of Done for This Branch

POC is done when:
- Frontend-only branch demonstrates end-to-end mocked growth funnel + real auth entry/exit.
- Team can test acquisition -> auth -> onboarding -> dashboard flow with carried offer metadata.
- Code is isolated and can be merged or discarded without backend impact.

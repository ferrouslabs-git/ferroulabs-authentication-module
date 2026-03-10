# Priority 5 Breakdown: Refactor for Portability (Headless + Themed UI)

Date: 2026-03-10
Project: `ferrouslabs-auth-system`
Scope: Break down Priority 5 into implementation steps based on current code structure.

## Current State (Observed in Code)

- `frontend/src/auth_usermanagement/index.js` exports both headless logic and UI components together.
- `frontend/src/auth_usermanagement/context/AuthProvider.jsx` combines state, token storage, Cognito redirect behavior, sync bootstrap, and timer logic in one provider.
- `frontend/src/auth_usermanagement/services/authApi.js` has hardcoded API base path (`/auth`) and request conventions.
- `frontend/src/auth_usermanagement/services/cognitoClient.js` directly reads env vars and uses browser globals (`window`, `sessionStorage`, `localStorage`).
- UI components (for example `pages/AdminDashboard.jsx`, `components/UserList.jsx`) contain significant inline styles and business decisions.
- App integration is currently direct (`frontend/src/main.jsx` and `frontend/src/App.jsx`) and assumes one app shell/router pattern.

This means portability is possible, but the module is currently tightly coupled to one host app and one presentation approach.

---

## Step 1: Define the Module Contract (Before Refactor)

What to do:
- Write a clear public contract for the module: what host apps can import and what is internal.
- Split contract into two surfaces: `headless` and `default-ui`.

Decisions you need to make:
- Which exports are officially supported for external apps?
- Do you want semantic versioning guarantees for these exports now or later?
- What should remain internal/private (subject to change)?

Output:
- A short contract section listing stable exports and internal-only modules.

---

## Step 2: Separate Headless Exports from UI Exports

What to do:
- Refactor `frontend/src/auth_usermanagement/index.js` into explicit export groups.
- Create separate entry points (example: `headless/index.js`, `ui/index.js`) or at minimum named grouped exports.

Decisions you need to make:
- Do you want two entry files or one entry with namespaced exports?
- Should host apps be allowed to import deep internal paths, or only top-level entry points?

Output:
- Headless import path works without importing any visual component.
- UI import path works as optional layer.

---

## Step 3: Isolate Runtime Configuration

What to do:
- Move env/config resolution into a single config module.
- Ensure services depend on injected config (or centralized validated config) instead of scattered direct env usage.

Decisions you need to make:
- Config strategy: compile-time env only, runtime object injection, or hybrid?
- Which values are required vs optional?
- How strict should startup validation be (fail hard vs warn)?

Output:
- One source of truth for Cognito/API config.
- Clear error messages if required config is missing.

---

## Step 4: Split AuthProvider Responsibilities

What to do:
- Decompose `AuthProvider` into focused units:
  - token storage/session persistence
  - OAuth callback parsing + exchange
  - bootstrap sync/me/tenants loading
  - token refresh scheduler
  - logout orchestration

Decisions you need to make:
- Keep one provider with internal helpers, or introduce multiple providers/hooks?
- How much browser-specific behavior should remain inside provider vs adapters?
- Should redirect behavior be hardcoded or host-configurable?

Output:
- Smaller auth units that are easier to reuse and test.

---

## Step 5: Decouple API Client from App Assumptions

What to do:
- Refactor `authApi.js` so base URL, timeout, and header conventions are configurable.
- Keep default values matching current behavior.

Decisions you need to make:
- Should host app pass a preconfigured HTTP client, or should module own Axios instance?
- Do you want request/response interceptors exposed to host app?
- How should tenant header behavior be overridden (automatic vs explicit)?

Output:
- API service can run in another app/env without editing module source.

---

## Step 6: Define Authorization and Role Model Boundaries

What to do:
- Align front-end permission checks with backend role reality.
- Ensure role source is explicit (tenant role vs platform admin flag).

Decisions you need to make:
- Is permission model fully frontend-derived or always backend-authoritative?
- Should UI hide inaccessible actions or show disabled-with-reason?
- Which permissions are tenant-scoped vs global (platform) scoped?

Output:
- One documented permission map used consistently across hooks/components.

---

## Step 7: Move Visual Styling to Theme Tokens

What to do:
- Replace inline style-heavy components (`AdminDashboard`, `UserList`, shell-level styles) with a tokenized styling system (CSS modules, CSS variables, or styled components).
- Keep a default theme package/layer.

Decisions you need to make:
- Styling approach: CSS modules vs styled-components vs utility classes?
- Token format: JS theme object, CSS variables, or both?
- Dark mode support now or later?

Output:
- UI components can be re-themed without touching auth logic.

---

## Step 8: Add Extension Points in UI Components

What to do:
- Add controlled extension props to reusable components (for example `className`, `slotProps`, `renderX` callbacks).
- Keep defaults intact.

Decisions you need to make:
- Preferred extension model: slots, render props, or override components map?
- How much override freedom is allowed before support burden increases?

Output:
- Host app can customize UI without forking module files.

---

## Step 9: Decouple Routing Integration

What to do:
- Remove assumptions that module controls app routing structure.
- Provide route-ready components/hooks that host app wires into its own router.

Decisions you need to make:
- Should module ship route definitions, route helpers, or route-agnostic primitives only?
- Which redirect paths remain defaults, and which must be host-supplied?

Output:
- Module works in multiple app routing structures.

---

## Step 10: Build a Second Integration Target (Validation)

What to do:
- Create a second demo shell/app using the same headless module with a different visual style.
- Validate core flows: sign-in, callback sync, role checks, invite acceptance, sign-out.

Decisions you need to make:
- Is second integration a separate app folder or a second shell in same frontend app?
- Which flows are mandatory pass criteria for portability sign-off?

Output:
- Proof that portability is real, not just conceptual.

---

## Step 11: Testing and Regression Guardrails

What to do:
- Add tests around headless units and critical auth/session edges.
- Add smoke tests for default UI layer.

Decisions you need to make:
- Test depth: unit only vs unit + integration + e2e?
- Which auth scenarios are required gates (token refresh, expired tokens, tenant switching, logout failure)?

Output:
- Refactor confidence and reduced breakage risk for host apps.

---

## Step 12: Documentation for Adopters

What to do:
- Publish concise docs for host apps:
  - required providers
  - required env/config
  - headless usage examples
  - optional UI usage + theming overrides

Decisions you need to make:
- Who is the first adopter audience (internal team vs external consumers)?
- How strict should migration guidance be from current implementation?

Output:
- Another app can adopt module with minimal back-and-forth.

---

## Suggested Execution Order (Low-Risk)

1. Step 1 (contract)
2. Step 2 (exports separation)
3. Step 3 (config centralization)
4. Step 5 (API decoupling)
5. Step 4 (AuthProvider decomposition)
6. Step 6 (permission boundary cleanup)
7. Step 7 + Step 8 (styling and extension points)
8. Step 9 (routing decoupling)
9. Step 10 (second integration validation)
10. Step 11 + Step 12 (tests and docs)

---

## Exit Criteria for Priority 5

Priority 5 is complete when all are true:
- Headless auth/usermanagement logic works without importing default UI components.
- Default UI is optional and themeable.
- At least one second integration runs with different visual language and no forked business logic.
- Public API surface is documented and stable.
- Core auth/authorization flows pass regression tests.

# Current Stage Priority To-Do

Date: 2026-03-08
Project: `ferrouslabs-auth-system`
Purpose: Actionable to-do list and planning document for next implementation phase.

## Recommended Priority Order

1. Move database to actual RDS Postgres
2. Admin panels for user management (functional completeness)
3. Mock small app with real auth/user management
4. Make admin pages pretty + add UX features
5. Refactor module for portability (headless + themed UI)
6. Add SSO

---

## 1) Move Database to Actual RDS Postgres

### Why This Is First
Foundational infrastructure change that reduces migration risk and avoids rework later.

### To-Do Checklist
- [ ] Create RDS Postgres instance (dev/staging), security group, and subnet group.
- [ ] Enable SSL, backups, parameter group, and monitoring.
- [ ] Update backend `DATABASE_URL` to RDS endpoint.
- [ ] Run Alembic migrations against RDS.
- [ ] Smoke test auth flows: login, invite, accept invite, suspend/unsuspend.
- [ ] Add secrets handling (AWS Secrets Manager or SSM) and remove hardcoded creds.

### Done Criteria
- API uses RDS in non-local environment.
- Migrations are clean and repeatable.
- Core auth and invitation flows pass smoke tests.

---

## 2) Admin Panels for User Management

### Why This Is Second
Gives operational control and validates role/permission model in real workflows.

### To-Do Checklist
- [ ] Finalize admin pages for tenant users, roles, suspension, removal, and invitations.
- [ ] Ensure permission checks match in frontend and backend (`admin`, `platform_admin`, etc).
- [ ] Add audit-friendly feedback (toasts, confirmations, clear error states, retry).
- [ ] Add list usability: search, sort, filters, pagination.
- [ ] Run end-to-end scenarios across multiple users and tenants.

### Done Criteria
- Admin can manage users safely across tenants.
- Unauthorized actions are blocked in both UI and API.
- E2E role-based flows pass.

---

## 3) Mock Small App with Real Auth and User Management

### Why This Is Third
Fastest way to prove real integration before investing in advanced features.

### To-Do Checklist
- [ ] Build a tiny demo app with 2-3 authenticated pages.
- [ ] Use real login/session and role-based route protection.
- [ ] Connect user/tenant context from auth module.
- [ ] Add 1-2 sample domain actions per role.
- [ ] Demo full flow: invite -> accept invite -> login -> role-limited actions.

### Done Criteria
- Demo app proves end-to-end auth + authorization behavior.
- Role restrictions are visibly enforced in UI and backend.

---

## 4) Make Admin Pages Pretty + Add UX Features

### Why This Is Fourth
Polish is most valuable once core behavior and permissions are stable.

### To-Do Checklist
- [ ] Pick a clear design direction (colors, typography, spacing, components).
- [ ] Replace inline styles with reusable CSS modules or styled components.
- [ ] Improve layout hierarchy, empty/loading/error states, responsive behavior.
- [ ] Add quality-of-life features: bulk actions, saved filters, quick actions.
- [ ] Run accessibility pass: keyboard nav, labels, contrast, focus states.

### Done Criteria
- Admin pages look consistent, responsive, and production-ready.
- UX and accessibility quality clearly improved.

---

## 5) Refactor Module for Portability (Headless + Themed UI)

### Why This Is Fifth
Critical for reuse in other apps with different design systems and branding.

### To-Do Checklist
- [ ] Separate headless logic (hooks/services/state) from presentational UI components.
- [ ] Replace inline styles with CSS modules, theme tokens, or styled-system primitives.
- [ ] Define component extension points (`className`, slots, render props, variant props).
- [ ] Keep a default UI implementation for fast adoption while allowing full overrides.
- [ ] Validate by integrating the module into a second demo app with different styling.

### Done Criteria
- Auth and user-management logic can run without bundled UI components.
- A second app can apply a different visual style without forking module logic.
- Default UI remains available as an optional starter layer.

---

## 6) Add SSO

### Why This Is Sixth
High integration complexity; best after core auth, admin workflows, and module portability are stable.

### To-Do Checklist
- [ ] Choose SSO providers (Google Workspace, Azure AD, Okta, etc).
- [ ] Configure Cognito federation (SAML/OIDC) and callback/logout URLs.
- [ ] Map IdP claims to app roles and tenant membership rules.
- [ ] Define first-login provisioning and account-linking strategy.
- [ ] Test edge cases: email mismatch, deprovisioning, role changes, logout.
- [ ] Add optional admin controls for tenant-level SSO enablement.

### Done Criteria
- At least one IdP works end-to-end.
- Claims mapping and role assignment are deterministic.
- Failure paths are tested and documented.

---

## Suggested Next Action

Start immediately with Priority 1 (RDS migration), then execute Priority 2 and 3 as the next milestone.

## Optional Follow-Up

Create a practical 2-week day-by-day execution plan for Priorities 1-3.

# Prioritized Next Steps

Plain-English execution order for finishing the auth and user management module with the best impact first.

## Priority 0 (Do First: Security + Reliability)

1. Add session revocation endpoints and connect frontend logout to revocation.
2. Add account suspension checks (`is_active`, `suspended_at`) into auth flow.
3. Implement frontend token refresh before expiry with safe logout fallback.
4. Add and enforce DB RLS policies for tenant isolation.

Why first:
- These reduce real production risk immediately (session misuse, suspended users, stale tokens, tenant leak risk).

## Priority 1 (Finish Core Collaboration Flow)

1. Complete SES setup in AWS (verified sender/domain, prod access).
2. Validate invitation flow end-to-end in real environment.
3. Harden invitation failure handling and observability.

Why now:
- Team onboarding/invites are core to multi-user SaaS adoption.

## Priority 2 (Module API Consistency)

1. Add formal `switchTenant` API surface.
2. Standardize tenant list naming (`listTenants` vs `listMyTenants`).
3. Lock one module path convention (`src/features/...` recommended for long-term scale).
4. Document Hosted UI mode clearly.

Why now:
- Prevents integration drift across future apps and keeps module reusable.

## Priority 3 (Admin UI Hardening)

1. Enforce permission checks inside `InviteUserModal` and `UserList`.
2. Add `UserList` search/sort.
3. Remove inline styles and keep components fully headless.
4. Standardize permission vocabulary (`invite_users`, `remove_users`, etc.).

Why now:
- Improves UX and reduces accidental misuse in consuming apps.

## Priority 4 (Testing Expansion)

1. Add unit tests for audit and rate-limit logic.
2. Add integration tests for session revocation.
3. Add tenant isolation tests with RLS active.
4. Add focused component/integration tests for admin visibility and forbidden actions.

Why now:
- Locks in behavior before packaging and template rollout.

## Priority 5 (Packaging + Template)

1. Build dedicated template repository structure.
2. Add IaC modules (Cognito, RDS, SES, optional Redis).
3. Add module READMEs and template quick start docs.
4. Validate by creating a second app from template and documenting setup gaps.

Why last:
- Packaging is most valuable after security, flow completeness, and test confidence are in place.

## Suggested Milestone Order

- Milestone A: Security hardening complete.
- Milestone B: Invitation flow production-ready.
- Milestone C: API contract and UI consistency locked.
- Milestone D: Test matrix complete.
- Milestone E: Reusable template published.

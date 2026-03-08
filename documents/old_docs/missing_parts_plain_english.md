# Missing Parts (Plain English)

This list is based on `auth_plan.md` and focuses only on items still marked incomplete.

## Auth And Identity

- Map Cognito `cognito:username` into the backend token schema so username is always available in a predictable field.
- Keep token verification behavior unchanged while adding this mapping.

## Invitations And Email

- Finish AWS SES setup (verify sender/domain and production access).
- Fully complete and validate invitation flows:
  - Invite a user to a tenant.
  - Read invitation details by token.
  - Accept invitation and create/reactivate membership.
- Ensure invitation email delivery is wired end-to-end in real environments.

## Frontend Auth Module API

- Add a formal `switchTenant` API surface in the auth module.
- Standardize naming so tenant list calls use one consistent name (`listTenants` or `listMyTenants`).
- Decide and standardize module folder convention:
  - `src/auth_usermanagement/` or
  - `src/features/auth_usermanagement/`
- Add clear docs that this module uses Cognito Hosted UI mode, so people do not reintroduce local password auth.

## Admin UI Hardening

- Enforce role/permission checks inside components (not only in parent containers).
- Add search and sorting in `UserList`.
- Reduce inline styles and keep components headless and style-agnostic.
- Standardize UI permission names and role mapping.
- Add tests for admin-only visibility and blocked actions.

## Backend Security Gaps

- Add session revocation endpoints (single session and all sessions).
- Connect frontend logout to backend session revocation.
- Add account suspension (`is_active`, `suspended_at`, suspend endpoint, auth checks).
- Implement automatic token refresh in frontend before token expiry.
- Add DB-level RLS policies and test cross-tenant isolation with RLS enabled.
- Add database-backed audit table and audit query endpoint.

## Testing Gaps

- Add tests for audit service behavior.
- Add tests for rate limiting behavior.
- Add integration tests for session revocation flow.
- Add E2E/integration tests proving RLS blocks cross-tenant access.

## Packaging And Template Gaps

- Build the reusable SaaS template repository structure.
- Add IaC (Terraform/CDK) for Cognito, RDS, SES (and planned Redis).
- Add template docs (quick start, setup, migration, production checklist).
- Add module-level READMEs for backend and frontend auth modules.
- Validate template reusability by bootstrapping a second project from the template.

## Deployment Readiness Gaps

- Complete pre-production checklist items still open:
  - env configuration
  - SES production readiness
  - CORS restrictions
  - monitoring/alerts
  - backup/DR readiness
- Complete template production-ready checklist items (CI/CD, Docker consistency, ops docs).

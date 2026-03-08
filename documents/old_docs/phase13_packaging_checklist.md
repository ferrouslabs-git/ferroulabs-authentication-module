# Phase 13 Packaging Checklist

Date: 2026-03-08

## Goal
Prepare the auth/user-management module for reuse across projects with minimal setup.

## Completed in this repo
- Backend and frontend auth module structure is in place under:
  - `backend/app/auth_usermanagement`
  - `frontend/src/auth_usermanagement`
- Backend hardening middleware added (security headers, auth rate limiting).
- Audit logging hooks added to sensitive endpoints.
- Frontend Cognito client now supports env-driven configuration.
- `test-phase12.ps1` supports auth code exchange via `-AuthCode`.

## Reuse packaging requirements
- Keep module public API stable:
  - Frontend exports from `frontend/src/auth_usermanagement/index.js`
  - Backend router mounted from `backend/app/auth_usermanagement/api/__init__.py`
- Externalize environment-specific config:
  - Frontend Vite vars in `frontend/.env.example`
  - Backend vars in root `.env.example`
- Document run commands and test commands:
  - trustos conda runtime for backend
  - Phase scripts including phase 12

## Remaining validation before declaring complete
- Positive admin/owner audit path validation:
  - Run `test-phase12.ps1` with a user that has `admin` or `owner` role in target tenant.
  - Confirm `AUDIT` entries for sensitive events in backend logs.
- Optional persistence hardening:
  - Forward `trustos.audit` logs to a persistent sink (database table or external log store).

## Recommended handoff bundle
- Copy directories:
  - `backend/app/auth_usermanagement/`
  - `frontend/src/auth_usermanagement/`
- Copy/update env templates:
  - `.env.example`
  - `frontend/.env.example`
- Include scripts:
  - `test-phase6.ps1` through `test-phase12.ps1`

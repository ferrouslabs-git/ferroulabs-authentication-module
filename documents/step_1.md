# Step 1 - Close Item 1 (Tenant Context + API Isolation)

## Objective
Complete the highest-priority follow-up after Step 0 by verifying tenant isolation through real API requests and documenting the request lifecycle used for RLS-safe execution.

## Completed on 2026-03-15

1. Added API-level tenant isolation regression tests.
- File: [backend/tests/test_tenant_isolation_api.py](backend/tests/test_tenant_isolation_api.py)
- Coverage:
  - member can access own tenant via GET /auth/tenant-context
  - user is blocked from cross-tenant access (403) via GET /auth/tenant-context

2. Hardened dependency flow for non-Postgres test environments.
- File: [backend/app/auth_usermanagement/security/dependencies.py](backend/app/auth_usermanagement/security/dependencies.py)
- Change:
  - PostgreSQL RLS SET LOCAL statements now run only when dialect is PostgreSQL.
  - Avoids SQLite test failures while preserving Postgres RLS behavior.

3. Documented tenant request lifecycle.
- File: [docs/auth_rules.md](docs/auth_rules.md)
- Added: Tenant Request Lifecycle (RLS-Safe) section and guardrail against alternate validation paths.

## Verification Evidence
- `pytest -q tests/test_tenant_isolation_api.py -rs` -> 2 passed
- `pytest -q tests/test_tenant_middleware.py -rs` -> 4 passed
- `pytest -q tests -rs` -> 34 passed
- `RUN_POSTGRES_RLS_TESTS=1` with PostgreSQL `DATABASE_URL` and `pytest -q tests/test_row_level_security.py -rs` -> 4 passed

## Next Priority
Move to Item 2 (session lifecycle completeness):
- create session on login/token exchange
- validate + rotate refresh token hash on refresh
- revoke old session on rotation
- extend API/frontend integration tests for session lifecycle

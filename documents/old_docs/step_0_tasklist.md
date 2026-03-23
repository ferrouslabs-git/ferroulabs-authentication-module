# Step 0 Tasklist - Host DB Ownership Unification

This checklist executes Step 0 from [documents/step_0.md](documents/step_0.md) and adds a comprehensive test plan per item.

## Item 1 - Freeze DB Ownership Contract
- [x] Update boundary documentation in [docs/auth_rules.md](docs/auth_rules.md) with host-owned DB runtime contract.
- [x] Add or update Host Integration Contract section in module docs (host owns DB/config/migrations execution; module owns auth domain behavior).
- [x] Add an architecture note that this repo host is an integration harness and not future production host ownership for consumers.

Tests to write or update:
- [x] Docs consistency check: verify all docs reference host-owned DB as single source of truth.
- [x] Architecture review checklist test: confirm no contradictory statements across [documents/step_0.md](documents/step_0.md), [documents/version_1_eval.md](documents/version_1_eval.md), and [docs/auth_rules.md](docs/auth_rules.md).

## Item 2 - Unify DB Runtime Source
- [x] Refactor [backend/app/auth_usermanagement/database.py](backend/app/auth_usermanagement/database.py) to stop creating engine, SessionLocal, and Base.
- [x] Make auth DB module consume host DB runtime from [backend/app/database.py](backend/app/database.py) (directly or thin transitional re-export only).
- [x] Remove duplicate DATABASE_URL runtime ownership from auth DB path.

Tests to write or update:
- [x] Import-path smoke test: importing [backend/app/auth_usermanagement/database.py](backend/app/auth_usermanagement/database.py) does not create a second engine/session/base.
- [x] Runtime singleton test: host DB objects are the only runtime DB objects used by auth code.
- [x] Regression test for startup: app startup still succeeds with middleware and router registration.

## Item 3 - Rebind Models to Host Base
- [x] Update auth model imports in:
- [backend/app/auth_usermanagement/models/user.py](backend/app/auth_usermanagement/models/user.py)
- [backend/app/auth_usermanagement/models/tenant.py](backend/app/auth_usermanagement/models/tenant.py)
- [backend/app/auth_usermanagement/models/membership.py](backend/app/auth_usermanagement/models/membership.py)
- [backend/app/auth_usermanagement/models/invitation.py](backend/app/auth_usermanagement/models/invitation.py)
- [backend/app/auth_usermanagement/models/session.py](backend/app/auth_usermanagement/models/session.py)
- [x] Confirm model metadata resolves through host Base and remains visible to migration/runtime code paths.

Tests to write or update:
- [x] Metadata registration test: all auth tables are present in unified metadata.
- [x] Migration discovery test: auth model tables are discoverable by host migration environment.
- [x] CRUD sanity tests for each auth model through unified session path.

## Item 4 - Rewire Dependencies and Routers to One get_db
- [x] Update [backend/app/auth_usermanagement/security/dependencies.py](backend/app/auth_usermanagement/security/dependencies.py) so get_db resolves through host DB source.
- [x] Update [backend/app/auth_usermanagement/api/__init__.py](backend/app/auth_usermanagement/api/__init__.py) so all Depends(get_db) uses the same unified path.
- [x] Confirm there are no alternate DB dependency functions in auth routes.

Tests to write or update:
- [x] Dependency contract test: every auth route DB dependency resolves to host get_db.
- [x] Auth flow integration tests: sync, me, tenant list, invite, user management still work after dependency rewiring.
- [x] Error-path tests: invalid token, missing tenant header, and unauthorized role still return expected statuses and payloads.

## Item 5 - Remove Direct SessionLocal Usage in Middleware
- [x] Refactor [backend/app/auth_usermanagement/security/tenant_middleware.py](backend/app/auth_usermanagement/security/tenant_middleware.py) to remove direct SessionLocal() instantiation.
- [x] Align middleware DB/session usage with the same request-scoped session strategy used by endpoint handlers.
- [x] Remove commit-for-context behavior used only for tenant context session variables.

Tests to write or update:
- [x] Middleware session-path test: middleware and handler share coherent request DB/session strategy.
- [x] Tenant isolation integration test: tenant A cannot access tenant B data through API endpoints.
- [x] Platform admin bypass test: admin bypass rules still function under unified session strategy.
- [x] Existing middleware tests update in [backend/tests/test_tenant_middleware.py](backend/tests/test_tenant_middleware.py).

## Item 6 - Confirm Host App Wiring
- [x] Verify [backend/app/main.py](backend/app/main.py) still registers middleware and router correctly.
- [x] Verify endpoint behavior remains unchanged for public routes and protected auth routes.

Tests to write or update:
- [x] App boot test: app creates successfully with all middleware.
- [x] Route contract regression: endpoint paths and status code behavior remain stable.
- [x] Health/root endpoint sanity tests.

## Item 7 - Validate Migration and Discovery Assumptions
- [x] Verify host migration environment in [backend/alembic/env.py](backend/alembic/env.py) still discovers auth tables after import changes.
- [x] Verify migration history remains valid and no duplicate table/runtime ownership assumptions are introduced.

Tests to write or update:
- [x] Fresh DB migration test: full upgrade to head succeeds.
- [x] Seeded DB migration test: incremental upgrade from previous revision succeeds.
- [x] Optional downgrade safety check for latest auth-related revisions.
- [x] Post-migration schema assertion for auth tables and key constraints.

## Item 8 - Test and Regression Pass
- [x] Update existing tests impacted by DB import/session changes.
- [x] Add missing integration coverage for tenant context and auth flows under unified DB path.
- [x] Ensure RLS-specific test strategy is aligned with Postgres execution path.

Tests to write or update:
- [x] Update [backend/tests/test_row_level_security.py](backend/tests/test_row_level_security.py) for executable Postgres path.
- [x] Update [backend/tests/test_tenant_middleware.py](backend/tests/test_tenant_middleware.py) for unified session behavior.
- [x] Update [backend/tests/test_session_service.py](backend/tests/test_session_service.py) if any session lifecycle behavior shifts due to DB path changes.
- [x] Full backend regression run across auth-related tests.

## Item 9 - Cleanup Pass
- [x] Remove dead comments and docs that imply auth owns runtime DB objects.
- [x] Remove any duplicate DATABASE_URL ownership from auth module runtime configuration.
- [x] Ensure codebase no longer contains duplicate DB runtime creation patterns in reusable modules.

Tests to write or update:
- [x] Static grep gate in CI: block create_engine, sessionmaker, declarative_base in reusable module paths unless explicitly exempted.
- [x] Instruction compliance review against [.github/copilot-instructions.md](.github/copilot-instructions.md).
- [x] Final smoke regression: backend starts, key auth flows pass, and no duplicate DB runtime path remains.

## Item 10 - Copilot Guardrails Update
- [x] Update [.github/copilot-instructions.md](.github/copilot-instructions.md) with explicit host/module DB ownership boundaries.
- [x] Add review-gate wording to block PRs that reintroduce DB runtime ownership inside reusable modules.
- [x] Add migration execution ownership rule (host executes, modules contribute assets).

Tests to write or update:
- [x] Instruction lint/review checklist in PR template or review process.
- [x] Periodic rule-audit task to verify no boundary regressions are introduced by AI-assisted edits.

## Completion Gate
- [x] All checklist items complete.
- [x] All updated/new tests pass.
- [x] No duplicate DB runtime ownership remains in reusable module paths.
- [x] Step 0 acceptance criteria in [documents/step_0.md](documents/step_0.md) are fully satisfied.





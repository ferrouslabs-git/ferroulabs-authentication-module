# Step 0 - Execute Item 11 (Host-Owned Database Boundary)

## Objective
Make the host app the single owner of database runtime objects and stop the reusable auth module from acting like a second database owner.

Target boundary after this step:
- Host owns engine, SessionLocal, Base, and request DB dependency.
- Auth module consumes host DB objects and does not create its own engine/session/base.

## Status
Step 0 is complete as of 2026-03-15.

Verification evidence:
- PostgreSQL migration smoke completed (auth tables and RLS policies verified).
- PostgreSQL RLS suite completed under explicit opt-in mode.
- Maintained backend suite passed with Postgres RLS mode enabled:
	- Command: `RUN_POSTGRES_RLS_TESTS=1` with PostgreSQL `DATABASE_URL` and `pytest -q tests -rs`
	- Result: 32 passed, 0 failed.

## Decision Log (Confirmed)
1. Database ownership is host-only.
- [backend/app/database.py](backend/app/database.py) is the single runtime owner of engine, SessionLocal, Base, and get_db.
- Auth module must not create its own engine/session/base.

2. Import policy is direct host DB consumption.
- Auth code imports DB objects from [backend/app/database.py](backend/app/database.py).
- No separate auth DB runtime path is allowed going forward.

3. Config ownership is host-only for shared runtime settings.
- Host owns shared app configuration including DATABASE_URL.
- Auth config keeps only module-specific settings.

4. Migration execution ownership remains with host app.
- In this repo, host Alembic remains source of truth for execution.
- In future consumer apps, host app executes migrations.

5. Current host in this repo is treated as integration harness.
- Purpose: prove reusable component works end-to-end in this repository.
- In later real host apps, that host will own runtime wiring/config/migration execution.

## Codebase Review Findings (Why Step 0 Is Needed)
1. Host DB runtime exists:
- [backend/app/database.py](backend/app/database.py)

2. Auth module also creates independent DB runtime:
- [backend/app/auth_usermanagement/database.py](backend/app/auth_usermanagement/database.py)

3. Auth models currently bind to auth-local Base:
- [backend/app/auth_usermanagement/models/user.py](backend/app/auth_usermanagement/models/user.py)
- [backend/app/auth_usermanagement/models/tenant.py](backend/app/auth_usermanagement/models/tenant.py)
- [backend/app/auth_usermanagement/models/membership.py](backend/app/auth_usermanagement/models/membership.py)
- [backend/app/auth_usermanagement/models/invitation.py](backend/app/auth_usermanagement/models/invitation.py)
- [backend/app/auth_usermanagement/models/session.py](backend/app/auth_usermanagement/models/session.py)

4. Auth dependencies/routes currently use auth-local get_db:
- [backend/app/auth_usermanagement/security/dependencies.py](backend/app/auth_usermanagement/security/dependencies.py)
- [backend/app/auth_usermanagement/api/__init__.py](backend/app/auth_usermanagement/api/__init__.py)

5. Tenant middleware currently creates a separate DB session directly with SessionLocal:
- [backend/app/auth_usermanagement/security/tenant_middleware.py](backend/app/auth_usermanagement/security/tenant_middleware.py)

## Execution Checklist (Step 0)
1. Freeze DB ownership contract
- Update docs to state host DB runtime ownership explicitly.
- Add a short architecture note in [docs/auth_rules.md](docs/auth_rules.md).

2. Unify DB runtime source
- Refactor [backend/app/auth_usermanagement/database.py](backend/app/auth_usermanagement/database.py):
- Remove engine/session/base creation logic.
- Replace with host DB consumption from [backend/app/database.py](backend/app/database.py).
- If needed for temporary compatibility, keep only lightweight re-exports and no runtime ownership.

3. Rebind models to host Base path
- Update imports in all auth model files so Base resolves through host-owned DB path (directly or wrapper).

4. Rewire dependencies and routers to one get_db
- Update [backend/app/auth_usermanagement/security/dependencies.py](backend/app/auth_usermanagement/security/dependencies.py) to use unified get_db source.
- Update [backend/app/auth_usermanagement/api/__init__.py](backend/app/auth_usermanagement/api/__init__.py) to ensure all DB dependencies use that same source.

5. Remove direct SessionLocal usage in middleware
- Update [backend/app/auth_usermanagement/security/tenant_middleware.py](backend/app/auth_usermanagement/security/tenant_middleware.py):
- Stop creating a separate session with SessionLocal().
- Use request-scoped DB path compatible with endpoint dependency path.
- Remove commit-for-context behavior that can break request transaction assumptions.

6. Confirm host app wiring still works
- Verify [backend/app/main.py](backend/app/main.py) middleware/router stack still initializes correctly.

7. Validate migration/model discovery assumptions
- Verify host migration configuration still sees auth models after import path changes.
- Recheck [backend/alembic/env.py](backend/alembic/env.py) integration assumptions.

8. Test and regression pass
- Update/add tests in:
- [backend/tests/test_tenant_middleware.py](backend/tests/test_tenant_middleware.py)
- [backend/tests/test_row_level_security.py](backend/tests/test_row_level_security.py)
- Any affected auth service/API tests under [backend/tests](backend/tests)

9. Cleanup pass
- Remove dead code/comments implying auth module owns engine/session.
- Remove duplicate configuration ownership for DATABASE_URL from auth config and centralize it in host config.

## Acceptance Criteria (Step 0 Done)
1. Only host DB layer creates engine/session/base.
2. No auth middleware or service creates independent SessionLocal from auth-local database module.
3. All auth models and dependencies resolve DB objects through the unified host-owned path.
4. Tenant middleware and route handlers operate with one coherent request DB/session strategy.
5. Existing auth endpoints still function and tests pass.
6. Documentation reflects boundary clearly.

## Risks to Watch During Step 0
1. Silent split-session behavior persisting in middleware.
2. Circular imports while moving DB imports.
3. Alembic model discovery breaks if import roots change without env.py alignment.
4. Temporary compatibility wrappers becoming permanent and reintroducing ambiguity.
5. Any new module adding its own database.py runtime ownership and recreating split ownership.

## Copilot Rule Set Additions (Prevent Future Host/Module Mixing)
Add these rules to your Copilot instructions file (recommended location: [.github/copilot-instructions.md](.github/copilot-instructions.md)).

1. Database ownership rule:
- Never create SQLAlchemy engine, SessionLocal, or Base inside reusable modules.
- Reusable modules must import DB runtime objects from host integration points.

2. Dependency rule:
- All FastAPI Depends(get_db) usage in reusable modules must resolve to host-owned get_db (directly or approved compatibility adapter).

3. Middleware rule:
- Reusable module middleware must not instantiate new DB sessions directly with SessionLocal().
- Middleware must use request-scoped DB/session strategy approved by host architecture.

4. Configuration rule:
- Reusable modules must not own root app settings such as DATABASE_URL when running inside a host app.
- Module config files may only define module-specific settings.

5. Migration rule:
- Reusable modules can define schema/migration assets.
- Migration execution ownership remains with host app Alembic pipeline.

6. Import boundary rule:
- No duplicate DB runtime modules for the same process.
- Any compatibility adapter must be transitional only, explicitly marked, and scheduled for removal.

7. Review gate rule:
- Any PR that adds create_engine(), sessionmaker(), or declarative_base() in reusable module paths must be blocked unless explicitly approved as standalone sandbox code.

8. Documentation rule:
- Every reusable module must include a Host Integration Contract section listing what host owns vs what module owns.

## Suggested PR Sequence for Step 0
1. PR-1: Apply confirmed boundary decisions in docs and integration contract.
2. PR-2: DB/runtime unification to host ownership (database.py and imports).
3. PR-3: Middleware/session path unification for tenant context request flow.
4. PR-4: Tests, cleanup, and guardrail enforcement.

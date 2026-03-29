
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
- All files inside auth_usermanagement/ must use relative imports for DB objects (from ..database import Base/get_db).
- Only auth_usermanagement/database.py may reference 'from app.database import ...'.
- Enforced by test_db_runtime_guardrails.py::test_no_direct_host_database_imports_outside_bridge.

7. Review gate rule:
- Any PR that adds create_engine(), sessionmaker(), or declarative_base() in reusable module paths must be blocked unless explicitly approved as standalone sandbox code.

8. Documentation rule:
- Every reusable module must include a Host Integration Contract section listing what host owns vs what module owns.

9. Tenant context ownership rule:
- Tenant membership validation and tenant context creation must happen through dependency path using host-owned get_db.
- Middleware may enforce header/auth prechecks but must not create alternate DB validation paths.

10. RLS verification rule:
- Any PR touching tenant middleware, tenant dependencies, or tenant-scoped query logic must run PostgreSQL RLS tests.
- SQLite-only test runs are insufficient for sign-off on tenant isolation changes.

11. Test command rule:
- Standard verification must include:
- `pytest -q tests`
- `RUN_COGNITO_TESTS=1` for real Cognito integration tests (when touching auth/Cognito code).
- `RUN_POSTGRES_RLS_TESTS=1` with PostgreSQL `DATABASE_URL` for tenant isolation checks.

12. No validation bypass rule:
- Do not add convenience code paths that skip tenant validation in non-test runtime.
- Any temporary test helper for tenant context must be isolated to test code only.
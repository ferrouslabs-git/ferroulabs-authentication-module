
What looks good:
1. Clear module boundary and local config/database ownership in config.py and database.py.
2. Solid RBAC guard layer and role hierarchy in guards.py.
3. Good invitation lifecycle flow (create/preview/accept) with role-upgrade safety in invitation_service.py.
4. Frontend module exports are clean and reusable from index.js.
5. A separate repository layer is not strictly necessary yet because the current services are already acting as the combined business-logic and data-access layer, which is acceptable for v1.

What is missing (or risky) for true reusable production auth:
1. RLS context is likely ineffective right now because tenant context sets DB session vars on one session in middleware, while endpoints use another session via dependency injection. Evidence: tenant_middleware.py, tenant_middleware.py, database.py.
	- What to do:
	- Ensure middleware and route handlers use the same SQLAlchemy session per request.
	- Move tenant context variable setting into the same dependency that creates the request DB session.
	- Remove commit calls used only for SET LOCAL and rely on transaction scope instead.
	- Add an integration test that proves tenant A cannot read tenant B data through actual API calls.
	- Document request lifecycle: auth, tenant resolution, DB session creation, RLS variable set, handler execution.
	- What this means in code:
	- Update [backend/app/auth_usermanagement/security/tenant_middleware.py](backend/app/auth_usermanagement/security/tenant_middleware.py) to stop creating an isolated DB session only for tenant context setup.
	- Update [backend/app/auth_usermanagement/database.py](backend/app/auth_usermanagement/database.py) and [backend/app/auth_usermanagement/security/dependencies.py](backend/app/auth_usermanagement/security/dependencies.py) so request DB session setup includes tenant-scoped DB variables.
	- Update [backend/app/auth_usermanagement/api/__init__.py](backend/app/auth_usermanagement/api/__init__.py) to consistently use the same request session path.
	- Update [backend/tests/test_row_level_security.py](backend/tests/test_row_level_security.py) and [backend/tests/test_tenant_middleware.py](backend/tests/test_tenant_middleware.py) with end-to-end tenant isolation assertions.
	- Update documentation in [docs/auth_rules.md](docs/auth_rules.md) so the RLS lifecycle is explicitly documented.
	- Plan line: Effort M | Priority P0 | Owner Backend + Security | Execution Order 1
2. Session revocation is incomplete: session model exists, revoke endpoints exist, but there is no session creation/persistence flow using refresh_token_hash. Evidence: session.py, session_service.py, __init__.py.
	- What to do:
	- Add session creation endpoint/service when login/token exchange succeeds.
	- Persist hashed refresh token with metadata (user_id, device info, ip, user agent, created_at, expires_at).
	- Validate refresh token against stored hash on refresh flow and rotate token on every refresh.
	- Revoke old session row when rotating refresh tokens.
	- Add tests for login creates session, refresh rotates session, logout revokes session, revoke-all invalidates all tokens.
	- What this means in code:
	- Update [backend/app/auth_usermanagement/models/session.py](backend/app/auth_usermanagement/models/session.py) to include missing metadata fields needed for secure session tracking.
	- Update [backend/app/auth_usermanagement/services/session_service.py](backend/app/auth_usermanagement/services/session_service.py) to handle create, rotate, validate, and revoke session lifecycle operations.
	- Update [backend/app/auth_usermanagement/api/__init__.py](backend/app/auth_usermanagement/api/__init__.py) to expose login/refresh/logout session-aware flows and wire revocation consistently.
	- Update [frontend/src/auth_usermanagement/context/AuthProvider.jsx](frontend/src/auth_usermanagement/context/AuthProvider.jsx), [frontend/src/auth_usermanagement/services/cognitoClient.js](frontend/src/auth_usermanagement/services/cognitoClient.js), and [frontend/src/auth_usermanagement/services/authApi.js](frontend/src/auth_usermanagement/services/authApi.js) so frontend refresh behavior matches backend session lifecycle.
	- Update [backend/tests/test_session_service.py](backend/tests/test_session_service.py) with full lifecycle coverage.
	- Add a new migration under [backend/alembic/versions](backend/alembic/versions) for any new session columns/constraints.
	- Plan line: Effort L | Priority P0 | Owner Backend | Execution Order 2
3. RLS tests are skipped, so tenant isolation is not actually verified in CI/local test runs. Evidence: test_row_level_security.py.
	- What to do:
	- Add a PostgreSQL test profile for CI (containerized Postgres).
	- Mark RLS tests to run in CI job with Postgres enabled.
	- Keep SQLite unit tests for speed, but add mandatory Postgres integration stage for security-critical checks.
	- Add at least one API-level RLS regression test per protected resource.
	- What this means in code:
	- Update [backend/tests/test_row_level_security.py](backend/tests/test_row_level_security.py) to remove unconditional skip and gate by runtime environment capability.
	- Update [backend/tests/conftest.py](backend/tests/conftest.py) to support a Postgres-backed test session/fixture mode.
	- Add CI workflow configuration in the repository CI pipeline to run these tests against Postgres.
	- Update [README.md](README.md) with a clear command path for running RLS tests locally and in CI.
	- Plan line: Effort M | Priority P0 | Owner Backend + DevOps | Execution Order 4
4. Rate limiting is in-memory and per-process only, so it won’t hold across multiple workers/instances. Evidence: rate_limit_middleware.py, rate_limit_middleware.py.
	- What to do:
	- Replace in-memory limiter with shared backend (Redis).
	- Implement key strategy by endpoint + actor identity (user id if authenticated, otherwise ip).
	- Add burst + sustained limits per endpoint sensitivity (login, sync, invite, accept, admin actions).
	- Return standard rate-limit headers and enforce consistent 429 response schema.
	- Add load test to validate limits across multiple instances.
	- What this means in code:
	- Update [backend/app/auth_usermanagement/security/rate_limit_middleware.py](backend/app/auth_usermanagement/security/rate_limit_middleware.py) to use shared storage instead of in-memory state.
	- Update [backend/app/auth_usermanagement/config.py](backend/app/auth_usermanagement/config.py) to include rate-limit backend and per-route limit settings.
	- Update [backend/app/main.py](backend/app/main.py) to initialize middleware with configurable limits and backend connection settings.
	- Add/update tests in [backend/tests](backend/tests) for distributed-safe limit behavior and consistent 429 responses.
	- Update operational docs in [README.md](README.md) with backend dependency and tuning instructions.
	- Plan line: Effort M | Priority P1 | Owner Backend + DevOps | Execution Order 6
5. Token storage in localStorage increases XSS blast radius for reusable auth package consumers. Evidence: AuthProvider.jsx, AuthProvider.jsx.
	- What to do:
	- Move refresh token to secure HttpOnly cookie.
	- Keep access token short-lived and preferably in memory only.
	- Add backend refresh endpoint that reads HttpOnly cookie and returns new access token.
	- Add CSRF protection for cookie-based flows.
	- Harden CSP and sanitize user-controlled rendering paths in frontend.
	- What this means in code:
	- Update [frontend/src/auth_usermanagement/context/AuthProvider.jsx](frontend/src/auth_usermanagement/context/AuthProvider.jsx) to stop persisting long-lived tokens in localStorage and rely on memory plus backend refresh flow.
	- Update [frontend/src/auth_usermanagement/services/authApi.js](frontend/src/auth_usermanagement/services/authApi.js) and [frontend/src/auth_usermanagement/services/cognitoClient.js](frontend/src/auth_usermanagement/services/cognitoClient.js) to use cookie-based refresh interactions.
	- Update [backend/app/auth_usermanagement/api/__init__.py](backend/app/auth_usermanagement/api/__init__.py) to add a secure refresh endpoint and logout cookie clearing behavior.
	- Update [backend/app/auth_usermanagement/security/security_headers_middleware.py](backend/app/auth_usermanagement/security/security_headers_middleware.py) for stricter CSP and related headers aligned with token handling.
	- Add or update CSRF validation logic under [backend/app/auth_usermanagement/security](backend/app/auth_usermanagement/security).
	- Update frontend and backend auth test coverage under [frontend/src/auth_usermanagement](frontend/src/auth_usermanagement) and [backend/tests](backend/tests).
	- Plan line: Effort L | Priority P0 | Owner Frontend + Backend + Security | Execution Order 3
6. CORS is hardcoded to localhost dev origins, which hurts plug-and-play reuse in other environments. Evidence: main.py.
	- What to do:
	- Move CORS origins into configuration (environment variable list).
	- Support dev defaults but require explicit origins in staging/production.
	- Validate and normalize origin list at startup.
	- Add tests for allowed and blocked origins.
	- What this means in code:
	- Update [backend/app/main.py](backend/app/main.py) to read allowed origins from settings instead of hardcoded values.
	- Update [backend/app/auth_usermanagement/config.py](backend/app/auth_usermanagement/config.py) to include CORS origin configuration and parsing.
	- Update environment documentation in [README.md](README.md) with origin configuration examples.
	- Add or update API tests under [backend/tests](backend/tests) for CORS allow/deny behavior.
	- Plan line: Effort S | Priority P1 | Owner Backend | Execution Order 7
7. No packaging/distribution metadata for backend module (no pyproject/setup), so reuse is copy-paste rather than versioned installable package.
	- What to do:
	- Create pyproject.toml for backend auth module.
	- Define package name, semantic version, dependencies, and optional extras.
	- Expose clear public API surface and keep internal modules private.
	- Add release workflow to build and publish package artifact.
	- Add changelog and migration notes per version.
	- What this means in code:
	- Add backend packaging metadata at repository root and/or backend module root.
	- Update [backend/app/auth_usermanagement/__init__.py](backend/app/auth_usermanagement/__init__.py) to define stable public exports and version surface.
	- Review imports across [backend/app/auth_usermanagement](backend/app/auth_usermanagement) so consumers only depend on intended public modules.
	- Update [README.md](README.md) with install-by-version instructions rather than copy-based instructions.
	- Add release automation in CI so package artifacts are built and published per tagged version.
	- Plan line: Effort M | Priority P1 | Owner Backend + DevOps | Execution Order 9
8. Email normalization is inconsistent: invitations are normalized, user sync email is not, which can create case-sensitivity/account matching issues. Evidence: invitation_service.py, user_service.py.
	- What to do:
	- Normalize email on every write path (strip + lowercase).
	- Backfill and normalize existing user emails via migration script.
	- Add DB-level constraint/index strategy compatible with case-insensitive uniqueness.
	- Add tests for mixed-case sign-in and duplicate prevention.
	- What this means in code:
	- Update [backend/app/auth_usermanagement/services/user_service.py](backend/app/auth_usermanagement/services/user_service.py) to normalize incoming email before lookup and persistence.
	- Keep normalization behavior consistent with [backend/app/auth_usermanagement/services/invitation_service.py](backend/app/auth_usermanagement/services/invitation_service.py).
	- Add a migration under [backend/alembic/versions](backend/alembic/versions) to normalize existing records and enforce case-insensitive uniqueness behavior.
	- Update or extend tests in [backend/tests/test_invitation_service.py](backend/tests/test_invitation_service.py) and add user email normalization coverage in [backend/tests](backend/tests).
	- Plan line: Effort M | Priority P1 | Owner Backend | Execution Order 5
9. API surface is concentrated in one very large router file, which will become hard to maintain/extend as a reusable module. Evidence: backend/app/auth_usermanagement/api/__init__.py.
	- What to do:
	- Split router by domain: auth, tenants, invitations, users, sessions, admin.
	- Keep shared dependencies in a common module and register sub-routers from a thin root router.
	- Introduce consistent response/error models across all sub-routers.
	- Add endpoint-level ownership docs so contributors know where to add features.
	- What this means in code:
	- This concern is primarily about [backend/app/auth_usermanagement/api/__init__.py](backend/app/auth_usermanagement/api/__init__.py), which is currently carrying too many route groups in one file.
	- Break up [backend/app/auth_usermanagement/api/__init__.py](backend/app/auth_usermanagement/api/__init__.py) into domain-focused router modules under [backend/app/auth_usermanagement/api](backend/app/auth_usermanagement/api).
	- Keep [backend/app/auth_usermanagement/security/dependencies.py](backend/app/auth_usermanagement/security/dependencies.py) and schema modules as shared dependencies for all routers.
	- Update [backend/app/main.py](backend/app/main.py) import wiring to include the new composed root router.
	- Update API tests under [backend/tests](backend/tests) so route coverage remains equivalent after refactor.
	- Update architecture docs in [docs/auth_rules.md](docs/auth_rules.md) and [README.md](README.md) to reflect new router structure.
	- Plan line: Effort M | Priority P2 | Owner Backend | Execution Order 8
10. Reusability is currently “portable by copying” rather than “reusable by install + configure” (README itself describes copied modules). Evidence: README.md.
	- What to do:
	- Define installation path: pip package for backend and npm package for frontend.
	- Provide quickstart integration guide with minimal host-app wiring.
	- Add compatibility matrix (framework versions, python/node versions).
	- Provide sample host app that consumes packages instead of copied source.
	- Add upgrade guide and deprecation policy for reusable module consumers.
	- What this means in code:
	- Update [README.md](README.md) so the primary workflow is install + configure rather than copy files.
	- Update [frontend/src/auth_usermanagement/index.js](frontend/src/auth_usermanagement/index.js) and related exports to define stable frontend package entry points.
	- Update [backend/app/auth_usermanagement/__init__.py](backend/app/auth_usermanagement/__init__.py) to present backend package entry points and integration hooks.
	- Add a dedicated integration guide in [documents/integration_guide.md](documents/integration_guide.md) with host app onboarding steps.
	- Add/maintain a sample consumer implementation under existing workspace structure so package-style integration is continuously validated.
	- Plan line: Effort L | Priority P1 | Owner Backend + Frontend + DevRel | Execution Order 10
11. Database ownership is split between the host app and the auth module, which makes the module behave like a mini-app instead of a clean reusable component. Evidence: backend/app/database.py, backend/app/auth_usermanagement/database.py.
	- What to do:
	- Make the host app the single source of truth for engine, session factory, Base, and request DB dependency.
	- Stop the auth module from creating its own independent engine and SessionLocal.
	- Refactor the auth module to consume the host DB/session objects directly, or through a thin compatibility layer.
	- Ensure auth models and auth request handling use the same DB session path as the host app.
	- Apply the same principle to config ownership: host owns root settings, auth keeps only auth-specific config needs.
	- What this means in code:
	- Update [backend/app/database.py](backend/app/database.py) so it is clearly the host-owned source of truth for engine, SessionLocal, Base, and get_db.
	- Update [backend/app/auth_usermanagement/database.py](backend/app/auth_usermanagement/database.py) so it no longer creates its own engine, session factory, or Base and instead reuses host-owned DB objects.
	- Update imports across [backend/app/auth_usermanagement](backend/app/auth_usermanagement) so services, models, dependencies, and middleware all use the host DB path consistently.
	- Review [backend/app/auth_usermanagement/config.py](backend/app/auth_usermanagement/config.py) so it does not act like a second root application config if the host already owns settings.
	- Update [backend/app/main.py](backend/app/main.py) and host migration wiring so model discovery and request wiring still work with the host-owned DB setup.
	- Add regression tests under [backend/tests](backend/tests) to confirm auth behavior still works after removing module-level DB ownership.
	- Plan line: Effort M | Priority P1 | Owner Backend | Execution Order 0 Foundation
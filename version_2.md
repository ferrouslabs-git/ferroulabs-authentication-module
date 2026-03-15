# Version 2 Plan

1. Define portability config contract [DONE]
- Define a small shared config shape for backend/frontend portability settings (namespace, routes, cookie behavior).

2. Add backend settings for auth prefix, cookie name, cookie path, and namespace [DONE]
- Extend auth module settings to accept these values from env with safe defaults.

3. Refactor backend refresh cookie service to use configurable name/path [DONE]
- Replace hardcoded cookie constants with values read from module settings.

4. Refactor backend refresh endpoints to read/write cookie via config [DONE]
- Update endpoints to use configured cookie key and path consistently for set/read/clear.

5. Add frontend module config for api base path, callback path, invite path, and key namespace [DONE]
- Add a central frontend config helper that resolves defaults and optional host overrides.

6. Replace hardcoded TrustOS localStorage/sessionStorage keys with namespaced keys [DONE]
- Build keys from configured namespace instead of fixed trustos_* strings.

7. Add backward-compatible key migration logic (read old keys once, rewrite to new keys) [DONE]
- On startup, check legacy keys, migrate values to new namespaced keys, then remove legacy keys.

8. Replace hardcoded frontend auth API baseURL with configurable path [DONE]
- Make API client base path configurable so hosts can mount auth routes at different prefixes.

9. Replace hardcoded callback route assumptions with configurable callback path [DONE]
- Remove direct /callback assumptions and rely on configurable callback route values.

10. Replace hardcoded invite redirect assumptions with configurable invite path prefix [DONE]
- Build invite redirect and safety checks from config instead of fixed /invite pattern.

11. Remove forced page reload in invitation flow and use state refresh flow [DONE]
- Replace window reload with explicit auth/tenant refresh methods to keep SPA behavior stable.

12. Add lightweight runtime adapters for browser storage/navigation defaults [DONE]
- Wrap storage and navigation calls behind small adapters so hosts can override behavior (SSR/tests/custom routers).

13. Update frontend exports so host apps can wire invitation route cleanly [DONE]
- Export invitation page/component and any helpers needed for host route registration.

14. Add backend tests for configurable cookie name/path behavior [DONE]
- Add tests to verify refresh cookie set/clear/read logic works with non-default names and paths.

15. Add frontend tests for config-driven key/path behavior [DONE]
- Add tests confirming keys/routes use config values and legacy migration works as expected.

16. Run focused test suite for cookie endpoints, auth provider flow, and guardrail tests [DONE]
- Execute targeted backend/frontend tests to verify no regressions in auth flows and guardrails.

17. Produce integration checklist for copying module into a new host app [DONE]
- Add a brief practical checklist for required host wiring (settings, routes, middleware, migrations, env).

18. Perform one end-to-end smoke pass in current repo with non-TrustOS namespace values [DONE]
- Run app/tests with alternate namespace/path values to validate portability assumptions in practice.

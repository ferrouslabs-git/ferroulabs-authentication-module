# Final Update Checklist

> Priority-ordered list of changes needed before shipping.
> Order minimizes rework — later items never force changes to earlier ones.
> Frontend and live PostgreSQL verification are last.

---

## Phase 1: Backend Code Fixes (No New Files)

These are safe, isolated edits to existing code. None depend on each other.

### 1.1 — Fix deprecated `datetime.utcnow()` calls in models

**Why:** Python 3.12+ deprecation warning. The module already has `utc_now()` helpers in other files — models should use the same pattern.

**Files:**
- `backend/app/auth_usermanagement/models/tenant.py` — `created_at` and `updated_at` defaults
- `backend/app/auth_usermanagement/models/membership.py` — `created_at` default
- `backend/app/auth_usermanagement/models/user.py` — `created_at` and `updated_at` defaults
- `backend/app/auth_usermanagement/models/role_definition.py` — `created_at` default

**Change:** Replace `datetime.utcnow` with a local `utc_now` helper (same pattern used in `session.py`, `invitation.py`, `audit_event.py`).

**Tests needed:**
- Existing tests cover these models. Run `pytest -q tests` to confirm no regressions.

---

### 1.2 — Add TTL to JWKS cache in `jwt_verifier.py`

**Why:** `@lru_cache()` on `get_jwks()` never expires. If Cognito rotates signing keys, all token verification fails until process restart.

**File:** `backend/app/auth_usermanagement/security/jwt_verifier.py`

**Change:** Replace `@lru_cache()` with a TTL-based cache (e.g., `cachetools.TTLCache` with 1-hour TTL, or a manual timestamp check). Add `cachetools` to `requirements.txt`.

**Tests needed:**
- `tests/test_jwks_cache_ttl.py` — verify cache expires after TTL and re-fetches.
- Mock `requests.get` to confirm fresh fetch occurs after TTL window.

---

### 1.3 — Replace blocking `requests.get()` with non-blocking fetch in JWT verifier

**Why:** `requests.get()` is synchronous and blocks the async event loop under load.

**File:** `backend/app/auth_usermanagement/security/jwt_verifier.py`

**Change:** Two options (pick one):
- **Option A:** Pre-fetch JWKS at app startup (synchronous is fine at startup) and cache in module-level variable. Refresh on TTL from 1.2.
- **Option B:** Switch to `httpx.AsyncClient` for the JWKS fetch. Requires making `get_jwks()` async and updating callers.

Option A is simpler and avoids cascading async changes. Recommended.

**Tests needed:**
- Update existing JWT verification tests to confirm startup-fetch works.
- Test that a failed JWKS fetch at startup raises a clear error.

**Note:** This change builds on 1.2 (same file, same cache). Do them together.

---

### 1.4 — Remove deprecated code past removal date

**Why:** `require_role()`, `require_min_role()`, `TenantContext`, `get_tenant_context()`, and `ensure_tenant_access()` are all marked "remove after 2026-05-20." Current date is 2026-03-23 — not yet past the deadline, but if shipping after May 20, these must go. If shipping before, skip this step and revisit.

**Files:**
- `backend/app/auth_usermanagement/security/guards.py` — remove everything below the `# TODO: Remove after 2026-05-20` line
- `backend/app/auth_usermanagement/security/dependencies.py` — remove `get_tenant_context()` and `_V3_TO_LEGACY_ROLE`
- `backend/app/auth_usermanagement/security/tenant_context.py` — delete file
- `backend/app/auth_usermanagement/security/__init__.py` — remove deprecated exports
- `backend/app/auth_usermanagement/api/route_helpers.py` — remove `ensure_tenant_access()`

**Tests needed:**
- Remove or update tests that reference deprecated guards (`test_guards.py` deprecated sections).
- Run full `pytest -q tests` to confirm nothing depends on removed code.

**Risk:** Medium — only do this if no external consumers still use the legacy guards.

---

### 1.5 — Restrict owner role assignment via API

**Why:** `UpdateUserRoleRequest` accepts `"owner"` as a valid role with no extra safeguard. An admin could accidentally (or deliberately) transfer ownership.

**File:** `backend/app/auth_usermanagement/services/user_management_service.py` — `update_user_role()`

**Change:** Add a check: only the current owner (or platform admin) can assign the `"owner"` role. Return 403 otherwise.

**Tests needed:**
- `tests/test_user_management_service.py` — test that admin cannot assign owner role.
- `tests/test_user_management_service.py` — test that owner can assign owner role.
- `tests/test_user_management_service.py` — test that platform admin can assign owner role.

---

### 1.6 — Remove legacy `trustos_*` storage keys from frontend config

**Why:** Brand residue from a previous project. Harmless but confusing in a client delivery.

**File:** `frontend/src/auth_usermanagement/config.js`

**Change:** Remove `LEGACY_STORAGE_KEYS` object and all references to it across the frontend module.

**Files also affected:**
- `frontend/src/auth_usermanagement/context/AuthProvider.jsx` — remove legacy key migration logic
- `frontend/src/auth_usermanagement/services/cognitoClient.js` — remove legacy PKCE key fallback
- `frontend/src/auth_usermanagement/components/AcceptInvitation.jsx` — remove legacy redirect key

**Tests needed:** None (no frontend tests exist yet; covered by Phase 4).

**Note:** Isolated to frontend — no backend impact.

---

## Phase 2: New Backend Capabilities

These add new files or services. They depend on Phase 1 being stable.

### 2.1 — Add background cleanup service for expired data

**Why:** Expired refresh tokens, stale invitations, old rate-limit hits, and audit events accumulate without bound. The opportunistic `_purge_expired_tokens()` call during requests is not sufficient.

**New file:** `backend/app/auth_usermanagement/services/cleanup_service.py`

**Responsibilities:**
- Delete expired rows from `refresh_tokens` (where `expires_at < now`)
- Delete expired/revoked invitations older than 30 days
- Delete `rate_limit_hits` older than 24 hours
- Optionally archive or trim `audit_events` older than configurable retention period

**Integration options:**
- **Simplest:** Management command (`python -m app.cleanup`) called by cron / scheduled task / CloudWatch Events
- **Alternative:** Celery beat task if the host app already uses Celery

**Tests needed:**
- `tests/test_cleanup_service.py` — seed expired records, run cleanup, verify deletion counts.
- Test that non-expired records survive cleanup.
- Test that cleanup is idempotent.

---

### 2.2 — Add SES failure visibility / retry mechanism

**Why:** Silent email failure means invitations appear sent but never arrive. No admin can see the problem.

**File:** `backend/app/auth_usermanagement/services/email_service.py`

**Change:**
- Log audit event on email failure with `email_send_failed` action.
- Add `email_status` field to invitation model tracking `pending | sent | failed`.
- Consider adding a `GET /admin/invitations/failed` endpoint for platform admins to see unsent invitations.

**Migration needed:** Add `email_status` column to `invitations` table (optional — can log to audit_events only for v1).

**Tests needed:**
- `tests/test_email_service.py` — mock SES failure, verify audit event is logged.
- Test that invitation response includes failure detail on SES error.

---

### 2.3 — Document suspended-user JWT gap

**Why:** When a user is suspended, existing JWTs remain valid until natural expiry (~1 hour). The `is_active` DB check in `get_current_user` covers API calls, but this behavior should be explicitly documented.

**No code change required** — documentation only (see Phase 5).

**Optional hardening:** Call Cognito `AdminUserGlobalSignOut` on suspension to revoke all refresh tokens. Add to `user_service.py:suspend_user()`.

**Tests needed (if adding Cognito sign-out):**
- Mock boto3 Cognito client, verify global sign-out is called on suspend.

---

## Phase 3: Deployment & Infrastructure

### 3.1 — Create Dockerfile for backend

**New file:** `backend/Dockerfile`

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 3.2 — Create docker-compose for local development

**New file:** `docker-compose.yml`

Services:
- `db` — PostgreSQL 15
- `backend` — FastAPI app
- `frontend` — Vite dev server (optional)

Include health checks and volume for DB persistence.

### 3.3 — Add API versioning prefix

**Why:** Breaking changes later will be painful without versioning.

**Change:** Update `AUTH_API_PREFIX` default from `/auth` to `/v1/auth`, or document the recommended practice for host apps.

**Impact:** This changes the API contract. All frontend `authApi.js` base paths and middleware skip-route sets update automatically via the config system, but document the change.

**Tests needed:**
- `tests/test_main_auth_prefix.py` — verify routes mount under new prefix.

**Risk:** Low if done now before any external consumers exist. Defer if clients already integrate against `/auth`.

---

## Phase 4: Frontend Fixes

### 4.1 — Add frontend test suite

**Why:** Zero automated tests for the frontend module. Critical flows are untested.

**New files:**
- `frontend/src/auth_usermanagement/__tests__/AuthProvider.test.jsx`
- `frontend/src/auth_usermanagement/__tests__/useAuth.test.js`
- `frontend/src/auth_usermanagement/__tests__/cognitoClient.test.js`
- `frontend/src/auth_usermanagement/__tests__/authApi.test.js`
- `frontend/src/auth_usermanagement/__tests__/config.test.js`
- `frontend/src/auth_usermanagement/__tests__/AcceptInvitation.test.jsx`
- `frontend/src/auth_usermanagement/__tests__/TenantSwitcher.test.jsx`

**Test coverage targets:**
- PKCE code generation and exchange
- Silent token refresh via HttpOnly cookie
- Tenant switching and localStorage persistence
- Invitation acceptance flow (authenticated and unauthenticated states)
- `isSafeInvitePath` validation
- CSRF token reading and header attachment
- Error handling (network errors, 401/403 responses)

**Setup:** Add `vitest` + `@testing-library/react` + `msw` (mock service worker) to `package.json` dev dependencies.

---

## Phase 5: Documentation

### 5.1 — Update setup_guide.md

Add sections for:
- Cleanup job setup (cron command or Celery config)
- Docker-based local development
- API versioning recommendation
- Suspended-user JWT behavior and mitigation options

### 5.2 — Add SECURITY.md

**New file:** `SECURITY.md`

Document:
- JWT validation flow and JWKS caching behavior
- CSRF double-submit cookie pattern
- RLS enforcement model and what it does/doesn't protect
- Suspended-user token gap (and how `get_current_user` mitigates it)
- Rate limiting configuration and thresholds
- Cookie security attributes (HttpOnly, Secure, SameSite=Strict, Path-scoped)
- Invitation token hashing (SHA-256)
- Audit event coverage

### 5.3 — Add CHANGELOG.md

Create a changelog covering the v3.0 RBAC migration, scope-based RLS, space support, cookie auth, and deprecated API removal timeline.

---

## Phase 6: PostgreSQL RLS Verification

**Do this last.** It requires a running PostgreSQL instance and validates everything above.

### 6.1 — Run RLS test suite against real PostgreSQL

```bash
# Create a non-superuser test role
psql -U postgres -c "CREATE ROLE rls_tester LOGIN PASSWORD 'rls_tester_pw';"
psql -U postgres -c "GRANT ALL ON DATABASE myapp TO rls_tester;"
psql -U postgres -d myapp -c "GRANT ALL ON ALL TABLES IN SCHEMA public TO rls_tester;"

# Run migrations
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/myapp alembic upgrade head

# Run RLS tests
RUN_POSTGRES_RLS_TESTS=1 \
DATABASE_URL=postgresql://rls_tester:rls_tester_pw@localhost:5432/myapp \
pytest -q tests/test_row_level_security.py -v
```

### 6.2 — Run full test suite against PostgreSQL

```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/myapp_test \
pytest -q tests -v
```

Verify all tests pass with PostgreSQL (some may behave differently than SQLite).

### 6.3 — Verify cleanup service against real data

Seed test data (expired tokens, old invitations, stale rate-limit hits), run cleanup, verify counts.

---

## Summary Table

| # | Task | Type | Risk | Dependencies |
|---|---|---|---|---|
| 1.1 | Fix `datetime.utcnow()` in models | Code fix | Low | None |
| 1.2 | Add TTL to JWKS cache | Code fix | Low | None |
| 1.3 | Fix blocking `requests.get()` in JWT verifier | Code fix | Low | 1.2 |
| 1.4 | Remove deprecated guards (if post-May-20) | Code removal | Medium | None |
| 1.5 | Restrict owner role assignment | Code fix | Low | None |
| 1.6 | Remove legacy `trustos_*` keys | Frontend fix | Low | None |
| 2.1 | Cleanup service for expired data | New service | Low | 1.1 |
| 2.2 | SES failure visibility | Enhancement | Low | None |
| 2.3 | Document JWT gap on suspension | Docs | Low | None |
| 3.1 | Dockerfile | Infra | Low | None |
| 3.2 | docker-compose | Infra | Low | 3.1 |
| 3.3 | API versioning prefix | Config | Medium | None |
| 4.1 | Frontend test suite | Tests | Low | 1.6 |
| 5.1 | Update setup_guide.md | Docs | Low | 2.1, 3.1 |
| 5.2 | SECURITY.md | Docs | Low | 1.2, 1.3 |
| 5.3 | CHANGELOG.md | Docs | Low | All code changes |
| 6.1 | RLS tests on real PostgreSQL | Verification | Low | All above |
| 6.2 | Full suite on PostgreSQL | Verification | Low | All above |
| 6.3 | Cleanup service verification | Verification | Low | 2.1, 6.1 |

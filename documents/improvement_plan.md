# Auth System — Improvement Plan

> Post-async-conversion production readiness backlog.
> Generated from a full code audit of `auth_usermanagement/` targeting a normal SaaS workload (~50 K registered users, 100-500 concurrent).

---

## How to read this document

| Priority | Meaning | When to tackle |
|----------|---------|----------------|
| **P0 – Do Soon** | Low-effort hardening that prevents real-world surprises | Next sprint / before first paying customers |
| **P1 – Plan** | Important for reliability at steady-state traffic | Within 1-2 sprints after launch |
| **P2 – Backlog** | Nice-to-have improvements for scale or observability | Revisit when usage grows or pain is felt |

---

## P0 — Do Soon

### 1. Add `pool_pre_ping` and `pool_recycle` to database engine
**File:** `backend/app/database.py`
**Why:** RDS can silently close idle connections (especially after maintenance windows). Without `pool_pre_ping` the app will serve 500s until the dead connection is recycled naturally.
**Change:**
```python
engine = create_async_engine(
    ASYNC_DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
)
```
**Effort:** 2 lines

---

### 2. Remove or gate the `/debug-token` endpoint
**File:** `backend/app/auth_usermanagement/api/auth_routes.py`
**Why:** The endpoint returns full decoded JWT claims to anyone with a valid token. Useful during development but should not ship to production.
**Options:**
- Delete the route entirely (recommended).
- Guard it behind an environment flag (`if settings.DEBUG:`).
**Effort:** Delete ≈ 5 min; env-gate ≈ 15 min

---

### 3. Hash refresh tokens before storing
**File:** `backend/app/auth_usermanagement/services/cookie_token_service.py`
**Model:** `backend/app/auth_usermanagement/models/refresh_token.py`
**Why:** `RefreshTokenStore.refresh_token` is saved as plaintext. A database leak would expose live Cognito refresh tokens. The `Session` model already hashes its token — apply the same pattern here.
**Change:**
- Hash with SHA-256 on write (`store_refresh_token`).
- Hash the incoming cookie key's associated token on read to compare.
- *Note:* since the token is looked up by `cookie_key` (opaque), we only need a one-way hash — no need for bcrypt.
**Effort:** ~30 min + migration for column rename clarity

---

### 4. Rate limiter: fail-open logging
**File:** `backend/app/auth_usermanagement/services/rate_limiter_service.py` (line ~112)
**Why:** The `PostgresRateLimiter.is_rate_limited` catch-all `except Exception: return False` silently swallows DB errors. Failing open is the right default, but without a log line the operator has no idea the limiter is broken.
**Change:**
```python
except Exception:
    logger.exception("Rate limiter DB error — failing open for key=%s", key)
    return False
```
**Effort:** 1 line

---

## P1 — Plan

### 5. Schedule the cleanup service
**File:** `backend/app/auth_usermanagement/services/cleanup_service.py`
**Why:** `run_full_cleanup()` exists but is only callable manually. Expired tokens, stale invitations, and old rate-limit hits will accumulate. Wire it into a scheduler (APScheduler, Celery beat, or a CloudWatch-triggered Lambda).
**Effort:** ~1 hr to integrate APScheduler; varies for Lambda

---

### 6. Cap concurrent sessions per user
**File:** `backend/app/auth_usermanagement/services/session_service.py`
**Why:** Without a cap, a leaked credential can generate unlimited sessions. Add a constant (e.g., `MAX_SESSIONS_PER_USER = 10`) and revoke the oldest when exceeded.
**Effort:** ~30 min

---

### 7. Token rotation atomicity guard
**File:** `backend/app/auth_usermanagement/services/cookie_token_service.py`
**Why:** When Cognito returns a new refresh token during rotation, the old DB row is deleted and a new one inserted in two separate statements without a savepoint. If the insert fails the user loses their session. Wrap the swap in a nested transaction or a single `INSERT … ON CONFLICT` upsert.
**Effort:** ~30 min

---

### 8. Cleanup stale sessions on login
**File:** `backend/app/auth_usermanagement/services/session_service.py`
**Why:** Expired sessions sit in the database until manual cleanup runs. Opportunistically revoke or delete a user's expired sessions each time they create a new one.
**Effort:** ~20 min

---

## P2 — Backlog

### 9. Per-user / per-IP rate limiting key
**File:** `backend/app/auth_usermanagement/security/rate_limit_middleware.py`
**Why:** Current key is derived from the route path only, meaning all users share one bucket. Fine at low traffic, but at scale a single heavy user could exhaust the limit for everyone.
**When:** When you consistently see >50 req/s on auth endpoints.

---

### 10. Add compound database indexes for hot queries
**Tables:** `sessions`, `invitations`, `rate_limit_hits`
**Why:** As table sizes grow, lookups by `(user_id, revoked_at)`, `(email, tenant_id, status)`, and `(key, hit_at)` benefit from composite indexes.
**When:** When query latency or CPU on RDS climbs.

---

### 11. Pagination on list endpoints
**Routes:** `GET /tenants`, `GET /spaces`, admin user lists
**Why:** Currently returns all rows. Safe at low volume but will degrade. Add `limit`/`offset` or cursor-based pagination.
**When:** Any single tenant exceeds ~500 rows in a list.

---

### 12. Structured JSON logging
**All services**
**Why:** Plain `logging.info()` strings are hard to search in CloudWatch. Switch to `structlog` or `python-json-logger` so every log line carries `tenant_id`, `user_id`, `request_id`.
**When:** When you start relying on CloudWatch for debugging.

---

### 13. Async Cognito SDK calls
**Files:** `cognito_admin_service.py`, `cognito_service.py`
**Why:** Boto3 is synchronous; the services currently wrap calls in `asyncio.to_thread()`. This works but each call occupies a thread-pool slot. Consider `aioboto3` or `aiobotocore` if Cognito calls become a bottleneck.
**When:** When you profile and see thread-pool contention.

---

## Already Passing ✅

| Area | Status |
|------|--------|
| Async conversion (all services) | Fully async, properly awaited |
| JWT/JWKS concurrency (cache, locks) | Fixed — atomic snapshot, eager lock, long-lived client |
| User deletion cascade order | Correct (Cognito → sessions → memberships → anonymize → delete) |
| Error message sanitisation | No implementation details leaked |
| Tenant middleware architecture | Header pre-check only; DB validation in dependency layer |
| Import boundary / DB ownership rules | Enforced by `test_db_runtime_guardrails.py` |
| Test suite health | 589 passed, 34 skipped, 0 failures |

---

## Checklist (copy into your tracker)

```
[x] P0-1  pool_pre_ping + pool_recycle
[x] P0-2  Gate /debug-token behind AUTH_DEBUG env
[x] P0-3  Refresh token security: opaque cookie_key boundary (hash reverted — Cognito needs raw token)
[x] P0-4  Add logging to rate limiter fail-open path
[ ] P1-5  Schedule cleanup service
[ ] P1-6  Cap sessions per user
[ ] P1-7  Token rotation atomicity
[ ] P1-8  Cleanup stale sessions on login
[ ] P2-9  Per-user rate limit keys
[ ] P2-10 Compound indexes
[ ] P2-11 Pagination on list endpoints
[ ] P2-12 Structured JSON logging
[ ] P2-13 Async Cognito SDK (aioboto3)
```

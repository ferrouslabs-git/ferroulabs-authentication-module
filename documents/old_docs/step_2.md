# Step 2 – Session Lifecycle (Item 2 from version_1_eval.md)

## Goal
Give every login a server-side session record backed by a hashed refresh token so that sessions can be validated, rotated, and revoked — not just deleted in bulk.

---

## Done ✅

### Backend

| What | File | Detail |
|------|------|--------|
| Session model extended | `app/auth_usermanagement/models/session.py` | Added `user_agent`, `ip_address`, `device_info`, `expires_at` columns |
| Session service functions | `app/auth_usermanagement/services/session_service.py` | `create_user_session`, `validate_refresh_session`, `rotate_user_session` — all hash the token with SHA-256 before storing |
| Request/response schemas | `app/auth_usermanagement/schemas/session.py` | `SessionRegisterRequest`, `SessionRotateRequest`, `SessionResponse` |
| Schema exports | `app/auth_usermanagement/schemas/__init__.py` | New session schemas exported from package |
| API endpoints | `app/auth_usermanagement/api/__init__.py` | `POST /auth/sessions/register`, `POST /auth/sessions/{session_id}/rotate` |
| Alembic migration | `alembic/versions/8c5f69f3b5d1_add_session_metadata_fields.py` | Adds 4 columns; applied to Postgres dev DB (`alembic current` → `8c5f69f3b5d1`) |
| Unit tests | `tests/test_session_service.py` | 9 tests pass — create, validate (accept/reject), rotate (success/fail) |
| API integration test | `tests/test_session_api.py` | register → rotate → re-rotate with consumed token → 404 |

**Test results at completion:** `pytest -q tests -rs` → **41 passed**

---

## Left to Do ❌

### Frontend

#### 1. Add API helper functions — `authApi.js`

Two functions are missing entirely:

```js
// Call after a successful Cognito token exchange (login)
export async function registerSession(token, refreshToken, metadata = {}) {
  const res = await api.post(
    "/sessions/register",
    { refresh_token: refreshToken, ...metadata },
    { headers: authHeaders(token) },
  );
  return res.data; // { session_id, user_id, message }
}

// Call when Cognito returns a new refresh_token during silent refresh
export async function rotateSession(token, sessionId, oldRefreshToken, newRefreshToken, metadata = {}) {
  const res = await api.post(
    `/sessions/${sessionId}/rotate`,
    { old_refresh_token: oldRefreshToken, new_refresh_token: newRefreshToken, ...metadata },
    { headers: authHeaders(token) },
  );
  return res.data; // { session_id, user_id, message }
}
```

---

#### 2. Register session on login — `AuthProvider.jsx`

In the `bootstrap` function, after `exchangeAuthCodeForTokens` succeeds and tokens are stored, call `registerSession` and keep the returned `session_id` in component state:

```jsx
// After: localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token)
const sessionData = await registerSession(
  tokens.access_token,
  tokens.refresh_token,
  { user_agent: navigator.userAgent },
);
setSessionId(sessionData.session_id);           // new state: const [sessionId, setSessionId] = useState(null);
```

---

#### 3. Rotate session on silent refresh — `AuthProvider.jsx`

In `checkAndRefreshToken`, when Cognito returns a new `refresh_token`, the old one is currently just overwritten in `localStorage`. The backend rotation endpoint must be called to atomically revoke the old record and create the new one:

```jsx
// After: if (newTokens.refresh_token) {
if (newTokens.refresh_token && sessionId) {
  const rotated = await rotateSession(
    newTokens.access_token,
    sessionId,
    refreshToken,          // old refresh token
    newTokens.refresh_token,
    { user_agent: navigator.userAgent },
  );
  setSessionId(rotated.session_id);  // session_id changes on every rotation
  localStorage.setItem(REFRESH_TOKEN_KEY, newTokens.refresh_token);
  setRefreshToken(newTokens.refresh_token);
}
```

> Note: Cognito does not always return a new `refresh_token` during silent refresh (it only issues one at initial login unless token rotation is explicitly enabled in the user pool). The rotation call should be guarded with `if (newTokens.refresh_token)`.

---

#### 4. Pass session ID on logout — `AuthProvider.jsx`

`revokeAllSessions` already accepts `currentSessionId` as a second argument (see `authApi.js` line 63) but the call in `logout()` never passes it. Wire it in:

```jsx
// Change:
await revokeAllSessions(token);
// To:
await revokeAllSessions(token, sessionId);
// Then after, clear state:
setSessionId(null);
```

---

#### 5. Expose `sessionId` from context (optional but useful)

Add `sessionId` to the context value so consumers (e.g., a "Manage Sessions" page) can read it:

```jsx
const value = useMemo(
  () => ({
    token, user, tenants, tenantId, authError, isLoading,
    sessionId,                 // ← add
    isAuthenticated: Boolean(token && user),
    loginWithToken, logout, changeTenant,
  }),
  [token, user, tenants, tenantId, authError, isLoading, sessionId],
);
```

---

## Summary

| Layer | Status |
|-------|--------|
| Backend model + migration | ✅ Done |
| Backend service (create/validate/rotate/revoke) | ✅ Done |
| Backend API endpoints | ✅ Done |
| Backend tests (41 passing) | ✅ Done |
| `authApi.js` helpers (`registerSession`, `rotateSession`) | ❌ Not done |
| `AuthProvider.jsx` — register on login | ❌ Not done |
| `AuthProvider.jsx` — rotate on silent refresh | ❌ Not done |
| `AuthProvider.jsx` — pass session ID to logout | ❌ Not done |
| Context value exposes `sessionId` | ❌ Not done (optional) |

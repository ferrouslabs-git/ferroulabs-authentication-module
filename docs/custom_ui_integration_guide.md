# Custom UI Auth — Host App Integration Guide

> How to use `AUTH_MODE=custom_ui` in your host application and build your own login/signup frontend.

---

## Overview

The auth module supports two authentication modes:

| Mode | How it works | Frontend |
|------|-------------|----------|
| `hosted_ui` (default) | Cognito Hosted UI redirects (OAuth2 + PKCE) | Module's `LoginForm` component handles everything |
| `custom_ui` | App-owned forms → backend proxy → Cognito API | Host app builds its own forms OR uses provided reference components |

**When to use `custom_ui`:** You need control over the login/signup UI — e.g. showing only a "set password" form for invited users instead of a full Cognito signup page.

---

## Backend Setup (copy from module — no changes needed)

The backend is fully contained in the reusable module. When you copy `auth_usermanagement/` into your host app's backend, the custom UI endpoints are included automatically.

### 1. Set environment variable

```env
AUTH_MODE=custom_ui
```

That's it. The module reads `AUTH_MODE` from the environment and:
- Enables 7 new endpoints under `/auth/custom/*`
- Pre-creates Cognito users (with `FORCE_CHANGE_PASSWORD`) when invitations are sent
- All existing `hosted_ui` endpoints continue to work (they're not disabled)

### 2. Enable USER_PASSWORD_AUTH in Cognito

In your AWS Cognito Console → User Pool → App Client:

1. Go to **App integration** → **App client settings**
2. Under **Auth Flows Configuration**, enable **ALLOW_USER_PASSWORD_AUTH**
3. Save changes

> **Important:** Without this, the `/auth/custom/login` endpoint will fail with `InvalidParameterException`.

### 3. Required environment variables (same as hosted_ui, plus AUTH_MODE)

```env
AUTH_MODE=custom_ui
COGNITO_REGION=eu-west-1
COGNITO_USER_POOL_ID=eu-west-1_XXXXXXXXX
COGNITO_CLIENT_ID=your_client_id
COGNITO_CLIENT_SECRET=your_client_secret   # if app client has a secret
FRONTEND_URL=http://localhost:5173
```

### 4. Available backend endpoints

All endpoints require `AUTH_MODE=custom_ui` — they return 404 in `hosted_ui` mode.

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/auth/custom/login` | Email + password login |
| POST | `/auth/custom/signup` | Self-service registration |
| POST | `/auth/custom/confirm` | Email verification code |
| POST | `/auth/custom/set-password` | NEW_PASSWORD_REQUIRED challenge (invited users) |
| POST | `/auth/custom/resend-code` | Resend email verification code |
| POST | `/auth/custom/forgot-password` | Request password reset code |
| POST | `/auth/custom/confirm-forgot-password` | Confirm reset with code + new password |

> **Tenant middleware:** All `/auth/custom/*` endpoints are automatically skipped by `TenantContextMiddleware` — they are pre-authentication and don't require tenant headers.

---

## Frontend: What You Need to Build

You do NOT need to copy any frontend components from the module. Instead, build your own pages that call the backend endpoints. Below is exactly what each page needs to do.

### Login Page

**Endpoint:** `POST /auth/custom/login`

```json
// Request
{ "email": "user@example.com", "password": "their_password" }

// Response — success
{
  "authenticated": true,
  "access_token": "eyJ...",
  "id_token": "eyJ...",
  "refresh_token": "eyJ...",
  "expires_in": 3600
}

// Response — invited user (needs to set password)
{
  "authenticated": false,
  "challenge": "NEW_PASSWORD_REQUIRED",
  "session": "AYA..."
}
```

**Your UI:**
1. Show email + password form
2. On success (`authenticated: true`), store the tokens and redirect to your app
3. If response has `challenge: "NEW_PASSWORD_REQUIRED"`, redirect to the Set Password page (pass email + session)

**Post-login token handling:**
After a successful login, call these module APIs (via `authApi`) to complete the session setup:
```js
// 1. Store refresh token in HttpOnly cookie
await storeRefreshCookie(accessToken, refreshToken);

// 2. Register a backend session
await registerSession(accessToken, refreshToken, { user_agent: navigator.userAgent });
```

Or use the `loginWithTokens` function from `AuthProvider` which does both automatically:
```js
const { loginWithTokens } = useAuth();
await loginWithTokens({ accessToken, idToken, refreshToken });
```

---

### Signup Page

**Endpoint:** `POST /auth/custom/signup`

```json
// Request
{ "email": "new@example.com", "password": "min_8_chars" }

// Response
{
  "user_sub": "abc-123",
  "confirmed": false,
  "needs_confirmation": true
}
```

**Your UI:**
1. Show email + password + confirm password form
2. Validate passwords match and length >= 8 characters client-side
3. On success, if `needs_confirmation: true`, show the Confirm Email form

---

### Confirm Email Page

**Endpoint:** `POST /auth/custom/confirm`

```json
// Request
{ "email": "new@example.com", "code": "123456" }

// Response
{ "confirmed": true }
```

**Resend code:** `POST /auth/custom/resend-code` with `{ "email": "..." }`

**Your UI:**
1. Show a 6-digit code input
2. "Resend code" button
3. On success, redirect to login page

---

### Set Password Page (Invited Users)

This is the page that solves the Hosted UI limitation. When an admin invites a user:
1. Backend creates a Cognito user with `FORCE_CHANGE_PASSWORD` status
2. Cognito sends a temporary password email to the invited user
3. Invited user clicks the invitation link → lands on your invite accept page
4. User enters the temp password → backend returns `NEW_PASSWORD_REQUIRED` challenge
5. User chooses their permanent password → backend completes the challenge → returns real tokens

**Step 1 — Verify temp password:**

`POST /auth/custom/login` with the temp password → gets `challenge: "NEW_PASSWORD_REQUIRED"` + `session` token

**Step 2 — Set permanent password:**

`POST /auth/custom/set-password`

```json
// Request
{
  "email": "invited@example.com",
  "new_password": "permanent_password_min8",
  "session": "AYA..."  // from Step 1 response
}

// Response — success
{
  "authenticated": true,
  "access_token": "eyJ...",
  "id_token": "eyJ...",
  "refresh_token": "eyJ...",
  "expires_in": 3600
}
```

**Your UI:**
1. Pre-fill email (read-only, from invitation data)
2. Show temp password input (from invitation email)
3. On `NEW_PASSWORD_REQUIRED` challenge, switch to permanent password form
4. Show new password + confirm password inputs
5. On success, call `loginWithTokens` and redirect

---

### Forgot Password Page

**Step 1 — Request reset code:**

`POST /auth/custom/forgot-password`

```json
// Request
{ "email": "user@example.com" }

// Response (always the same — no email enumeration)
{ "message": "If an account exists for that email, a reset code has been sent." }
```

**Step 2 — Confirm with code + new password:**

`POST /auth/custom/confirm-forgot-password`

```json
// Request
{
  "email": "user@example.com",
  "code": "123456",
  "new_password": "new_password_min8"
}

// Response
{ "message": "Password reset successfully. You can now sign in." }
```

**Your UI:**
1. Show email input → call forgot-password → show success message regardless
2. Show code + new password + confirm password inputs
3. On success, redirect to login page

---

### Logout

In `custom_ui` mode, logout does NOT redirect to Cognito's logout URL. It only:
1. Revokes backend sessions (`revokeAllSessions`)
2. Clears the HttpOnly refresh cookie (`clearRefreshCookie`)
3. Clears local state

The `AuthProvider.logout()` handles this automatically — it checks `authMode` and skips the Cognito redirect in `custom_ui` mode.

---

## Reference Components (optional — copy if helpful)

The module includes working reference implementations. You can copy them into your host frontend as a starting point, then restyle to match your design system.

| Module Component | Purpose | Props |
|-----------------|---------|-------|
| `CustomLoginForm` | Email + password login | `onSuccess(tokens)`, `onNewPasswordRequired({email, session})`, `onSwitchToSignup`, `onForgotPassword`, `initialEmail` |
| `CustomSignupForm` | Two-step signup + email confirm | `onConfirmed(email)`, `onSwitchToLogin` |
| `InviteSetPassword` | Temp password → permanent password | `email` (read-only), `onSuccess(tokens)` |
| `ForgotPasswordForm` | Two-step forgot password (request code → reset) | `onBackToLogin`, `initialEmail` |

These are exported from `auth_usermanagement/index.js`:
```js
import { CustomLoginForm, CustomSignupForm, InviteSetPassword, ForgotPasswordForm } from "./auth_usermanagement";
```

The `AcceptInvitation` component already handles dual-mode automatically — in `custom_ui` mode it renders `InviteSetPassword`, in `hosted_ui` mode it renders `LoginForm`.

---

## API Client (optional — copy if helpful)

The module includes `services/customAuthApi.js` with typed functions:

```js
import { customLogin, customSignup, customConfirmEmail, customSetPassword, customResendCode, customForgotPassword, customConfirmForgotPassword } from "./auth_usermanagement/services/customAuthApi";
```

Or build your own — the endpoints are simple JSON POST requests with no special headers.

---

## Host App Integration Checklist

### Backend (just copy the module folder)
- [ ] Copy `auth_usermanagement/` into your backend
- [ ] Set `AUTH_MODE=custom_ui` in environment
- [ ] Enable `ALLOW_USER_PASSWORD_AUTH` on Cognito app client
- [ ] Verify invitation emails now include the temp password (Cognito sends this automatically)

### Frontend (build your own or use reference components)
- [ ] Build login page → calls `POST /auth/custom/login`
- [ ] Build signup page → calls `POST /auth/custom/signup` + `POST /auth/custom/confirm`
- [ ] Build invite set-password page → calls login (temp pw) then `POST /auth/custom/set-password`
- [ ] After any successful auth, call `loginWithTokens()` from AuthProvider
- [ ] Set `VITE_AUTH_MODE=custom_ui` in `.env`
- [ ] Verify logout doesn't redirect to Cognito (handled automatically by AuthProvider)

### Cognito Console
- [ ] Enable `ALLOW_USER_PASSWORD_AUTH` in app client auth flows
- [ ] Verify email sending is configured (SES or Cognito default)
- [ ] Review password policy matches your `min_length=8` validation

---

## Switching Between Modes

To switch back to Hosted UI:

```env
AUTH_MODE=hosted_ui   # or just remove the variable (hosted_ui is default)
VITE_AUTH_MODE=hosted_ui
```

The `/auth/custom/*` endpoints will return 404, and the frontend will use Cognito redirects. No code changes needed — it's purely a config switch.

---

## Security Notes

- **Tokens never touch Cognito directly from the browser.** All Cognito API calls go through the backend, which holds the client secret.
- **Refresh tokens** are stored in HttpOnly cookies (same as hosted_ui mode).
- **Session registration** creates a server-side session record for audit and revocation.
- **Temporary passwords** are generated server-side (24 chars, mixed case + digits + symbols) and sent by Cognito via email — they never appear in API responses.
- **Rate limiting** applies to custom endpoints the same as all other auth endpoints.
- **CSRF cookie** is set with `path=/` so JavaScript can read it from any page URL. The HttpOnly refresh cookie remains scoped to `/auth/token`.
- **Forgot password** returns the same response for non-existent emails to prevent email enumeration.

---

## v3.0 Role Names

The v3.0 migration renamed roles from legacy names to scoped names:

| Legacy Name | v3.0 Name |
|---|---|
| `owner` | `account_owner` |
| `admin` | `account_admin` |
| `member` | `account_member` |

The frontend `useRole()` hook and `ROLE_PERMISSIONS` map both old and new names for backward compatibility. The backend returns v3.0 names from `/auth/tenants/my` and membership queries.

# TrustOS Cognito Setup Guide

Date: 2026-03-08

## Purpose
This document captures:
1. A step-by-step guide to set up Amazon Cognito for TrustOS.
2. The exact successful settings and fixes applied in this repository.

## Part 1: Step-by-Step Cognito Setup

### 1. Open Cognito
1. Sign in to AWS Console.
2. Search for `Cognito`.
3. Open `User pools`.

### 2. Create a User Pool
1. Click `Create user pool`.
2. Sign-in options:
   - Choose email-based sign-in.
   - Keep configuration simple for MVP.
3. Required attributes:
   - Enable `email`.
   - Add `name` if you want profile name support.
4. Password and MFA:
   - Use default strong password policy.
   - MFA optional for local/dev.
5. Create the pool.

### 3. Create App Client
1. Inside the user pool, create app client (name used: `TrustOSTest`).
2. Configure authentication flow support:
   - Use `Authorization code grant`.
   - Enable refresh token support.
3. Token durations used:
   - Access token: 60 minutes.
   - ID token: 60 minutes.
   - Refresh token: 30 days.

### 4. Configure Managed Login Domain
1. In user pool settings, open domain/managed login section.
2. Create or confirm a Cognito domain.
3. Domain used in this project:
   - `https://eu-west-1ynis0witp.auth.eu-west-1.amazoncognito.com`

### 5. Configure Callback and Sign-out URLs
Set these exactly in the app client managed login config.

Allowed callback URLs:
- `http://localhost:3000`
- `http://localhost:3000/callback`
- `https://d84l1y8p4kdic.cloudfront.net`
- `https://d84l1y8p4kdic.cloudfront.net/callback`

Allowed sign-out URLs:
- `http://localhost:3000`
- `https://d84l1y8p4kdic.cloudfront.net`

### 6. Add Project Environment Variables
Create or update project root `.env`:

```env
# AWS Cognito
COGNITO_REGION=eu-west-1
COGNITO_USER_POOL_ID=eu-west-1_ynis0WItp
COGNITO_CLIENT_ID=79pef2au4irn8s7hcic9ik9d4p

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/trustos

# Environment
APP_ENV=local
```

### 7. Install Backend Dependencies
From `backend/`:

```bash
pip install -r requirements.txt
```

### 8. Start API
From `backend/`:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 9. Perform OAuth Login (Code Grant)
Open login URL:

```text
https://eu-west-1ynis0witp.auth.eu-west-1.amazoncognito.com/login?client_id=79pef2au4irn8s7hcic9ik9d4p&response_type=code&scope=email+openid+phone&redirect_uri=http%3A%2F%2Flocalhost%3A3000
```

After sign-in, browser redirects to:

```text
http://localhost:3000/?code=<AUTH_CODE>
```

### 10. Exchange Code for Tokens
PowerShell example:

```powershell
$domain = "https://eu-west-1ynis0witp.auth.eu-west-1.amazoncognito.com"
$clientId = "79pef2au4irn8s7hcic9ik9d4p"
$redirectUri = "http://localhost:3000"
$code = "<AUTH_CODE>"

$tokenResponse = Invoke-RestMethod -Method Post -Uri "$domain/oauth2/token" -ContentType "application/x-www-form-urlencoded" -Body "grant_type=authorization_code&client_id=$clientId&code=$code&redirect_uri=$redirectUri"
$tokenResponse
```

### 11. Validate Token Against API
Use returned `id_token`:

```powershell
curl.exe -i -H "Authorization: Bearer $($tokenResponse.id_token)" http://localhost:8000/auth/debug-token
```

Expected result:
- HTTP 200
- JSON with `status: valid`

## Part 2: Successful TrustOS Configuration Summary

### What was successfully completed
- Cognito user pool configured in `eu-west-1`.
- App client configured with OAuth authorization code flow.
- Managed login domain created and working.
- Local + production callback/sign-out URLs configured.
- `.env` populated with region, pool id, and client id.
- Backend Phase 1 JWT verification implemented and validated.

### Backend files implemented/updated
- `backend/app/auth_usermanagement/security/jwt_verifier.py`
- `backend/app/auth_usermanagement/schemas/token.py`
- `backend/app/auth_usermanagement/api/__init__.py` (debug endpoint)
- `backend/app/config.py` (reliable `.env` loading)
- `backend/requirements.txt` (JWT/settings dependencies)

### Key fixes applied during debugging
1. Fixed frontend build path serving issue in `backend/app/main.py`.
2. Fixed `.env` resolution in backend config so environment loads from project root.
3. Resolved empty env override behavior in settings loading.
4. Resolved Cognito `id_token` verification issue by disabling standalone `at_hash` verification in debug path while keeping signature/issuer/audience/expiry checks.
5. Confirmed final endpoint returns HTTP 200 with valid claims.

## Troubleshooting Notes

### `Invalid request` on login page
- Usually means grant type/URL mismatch.
- If app client uses code grant, use `response_type=code`.

### `invalid_grant` during token exchange
- Auth code expired or already used.
- Get a fresh `?code=` and retry immediately.

### PowerShell `curl` header errors
- PowerShell aliases `curl` to `Invoke-WebRequest`.
- Use `curl.exe` for curl syntax.

### 401 from `/auth/debug-token`
- Check `.env` values are present and loaded.
- Check token `aud` matches app client id.
- Check token `iss` matches user pool issuer.

## Next Steps
- Continue with Phase 2: PostgreSQL schema + SQLAlchemy models + migrations.
- Then implement Phase 3 user sync (`POST /auth/sync`).

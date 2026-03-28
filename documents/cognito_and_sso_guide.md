# Cognito & SSO Guide

> Complete guide covering Cognito base setup (done), SSO federation (future), and multi-tenancy integration.

---

## Part 1: Cognito Base Setup (Completed)

This section documents the working Cognito configuration for email/password auth via PKCE OAuth2 code grant.

### 1.1 Create a User Pool

1. AWS Console → Cognito → User pools → **Create user pool**
2. Sign-in options: **email-based**
3. Required attributes: `email` (required), `name` (optional)
4. Password policy: default strong policy
5. MFA: optional for dev, recommended for production

### 1.2 Create an App Client

1. Inside user pool → App clients → **Create app client**
2. Authentication flows:
   - Authorization code grant (PKCE)
   - Refresh token auth
   - `ALLOW_USER_PASSWORD_AUTH` — **required only if using `AUTH_MODE=custom_ui`** (app-owned login forms instead of Hosted UI)
3. Token durations:
   - Access token: 60 minutes
   - ID token: 60 minutes
   - Refresh token: 30 days
4. **Do NOT** generate a client secret (public PKCE client)

### 1.3 Configure Hosted UI Domain

Set up a Cognito domain for the managed login page:

```
https://<your-prefix>.auth.<region>.amazoncognito.com
```

### 1.4 Register Callback & Sign-out URLs

In app client → Hosted UI settings:

**Callback URLs:**
```
http://localhost:5173/callback
https://your-production-domain.com/callback
```

**Sign-out URLs:**
```
http://localhost:5173
https://your-production-domain.com
```

### 1.5 Environment Variables

Add to your host project `.env`:

```env
# Cognito (required)
COGNITO_REGION=eu-west-1
COGNITO_USER_POOL_ID=eu-west-1_XXXXXXXXX
COGNITO_CLIENT_ID=your-app-client-id
COGNITO_DOMAIN=your-prefix.auth.eu-west-1.amazoncognito.com

# Frontend (Vite)
VITE_COGNITO_DOMAIN=your-prefix.auth.eu-west-1.amazoncognito.com
VITE_COGNITO_CLIENT_ID=your-app-client-id
VITE_COGNITO_REDIRECT_URI=http://localhost:5173/callback
```

### 1.6 Verify the Setup

**Manual OAuth flow test (PowerShell):**

```powershell
# 1. Open login URL in browser
$domain = "https://$env:COGNITO_DOMAIN"
$clientId = $env:COGNITO_CLIENT_ID
$redirect = "http://localhost:5173/callback"
Start-Process "$domain/login?client_id=$clientId&response_type=code&scope=email+openid+profile&redirect_uri=$redirect"

# 2. After login, browser redirects to: http://localhost:5173/callback?code=<AUTH_CODE>
# 3. Exchange code for tokens
$code = "<paste-auth-code-here>"
$tokenResponse = Invoke-RestMethod -Method Post -Uri "$domain/oauth2/token" `
  -ContentType "application/x-www-form-urlencoded" `
  -Body "grant_type=authorization_code&client_id=$clientId&code=$code&redirect_uri=$redirect"

# 4. Test against your API
curl.exe -i -H "Authorization: Bearer $($tokenResponse.id_token)" http://localhost:8001/auth/debug-token
```

Expected: HTTP 200 with `status: valid`.

> **Custom UI alternative:** If you don't want to use the Cognito Hosted UI, set `AUTH_MODE=custom_ui` in your backend `.env` and `VITE_AUTH_MODE=custom_ui` in your frontend `.env`. This enables app-owned login, signup, and forgot-password forms that proxy Cognito API calls through your backend. See the [Custom UI Integration Guide](custom_ui_integration_guide.md) for full setup details.

**Using the frontend:**
1. Start backend: `cd backend && uvicorn app.main:app --port 8001 --reload`
2. Start frontend: `cd frontend && npm run dev`
3. Open `http://localhost:5173` → Click "Sign In" → Cognito Hosted UI → Login
4. After redirect, user should be synced and dashboard visible

### 1.7 Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| `Invalid request` on login page | Grant type / URL mismatch | Use `response_type=code` for authorization code grant |
| `invalid_grant` on token exchange | Auth code expired or reused | Get fresh code, exchange immediately |
| 401 from `/auth/debug-token` | Token claims don't match config | Verify `COGNITO_USER_POOL_ID` and `COGNITO_CLIENT_ID` in `.env` |
| PowerShell `curl` header errors | PowerShell aliases `curl` | Use `curl.exe` instead of `curl` |
| Token `aud` mismatch | Wrong client ID | Check `aud` in token matches `COGNITO_CLIENT_ID` |
| Token `iss` mismatch | Wrong pool ID | Check issuer is `https://cognito-idp.<region>.amazonaws.com/<pool-id>` |

---

## Part 2: How SSO Works with This System

> **Status: Future feature** — no code implementation yet. This section is a planning reference.

### What SSO Does

SSO (Single Sign-On) lets users log in via their company's identity provider (Google Workspace, Azure AD, Okta) instead of creating a separate password. You're not replacing Cognito — you're teaching Cognito to trust external identity providers via federation.

### Auth Flow Comparison

**Current (email/password):**
```
User → Cognito login page → types email + password → Cognito verifies → JWT issued → app syncs user
```

**With SSO:**
```
User → clicks "Sign in with Google" → redirected to Google → authenticates there →
Google tells Cognito "this person is legit" → Cognito issues JWT → app syncs user
```

The JWT that reaches your app is identical in both cases — a Cognito-issued token. Your backend doesn't need to know or care which auth method was used. The `sync_user_from_cognito()` function works the same way.

### How SSO Fits the Multi-Tenant Model

SSO is per-tenant, not global. Each tenant (account) can independently:
- Enable/disable SSO
- Choose their identity provider
- Claim and verify their email domain
- Enforce SSO (block email/password) or allow both

**Example: Acme Corp tenant:**
```
Tenant: Acme Corporation
├─ Verified domains: ['acme.com']
├─ SSO: Enabled (Google Workspace)
├─ Enforce SSO: Yes
└─ Members:
   ├─ alice@acme.com (account_owner) ← must use Google SSO
   ├─ bob@acme.com (account_member)  ← must use Google SSO
   └─ contractor@freelance.com (account_member) ← invited, uses email/password
```

**Key points:**
- RLS doesn't change — it enforces data isolation by `scope_id` regardless of auth method
- The existing invitation system still works for external users / contractors
- `memberships` table already supports multi-tenant per user — SSO just adds another way to create memberships
- Permission guards (`require_permission()`) work identically for SSO and password users

### Multi-Tenant SSO Scenarios

| Scenario | How It Works |
|----------|-------------|
| **Entire tenant uses SSO** | `sso_enabled=true`, `sso_enforce=true` — all members must SSO via the configured provider |
| **Mixed auth in one tenant** | `sso_enabled=true`, `sso_enforce=false` — employees use SSO, contractors use email/password |
| **User in multiple tenants** | Jane SSOs into Acme (Google) and manually joined Beta (email/password) — tenant switcher shows both |
| **No SSO** | Default state — everything works as today |

---

## Part 3: SSO Provider Configuration

> Step-by-step instructions for configuring each identity provider before writing any code.

### 3.1 Choose a Provider

| Provider | Best For | Setup Time | Cost |
|----------|----------|------------|------|
| **Google OAuth** | Quick testing, consumer apps | 10 min | Free |
| **Google Workspace** | Enterprise (domain-verified) | 10 min | Workspace subscription |
| **Azure AD** | Microsoft 365 enterprises | 20-30 min | Azure subscription or free dev tenant |
| **Okta** | Dedicated identity platform | 20-30 min | Free trial available |
| **Generic SAML 2.0** | Custom enterprise IdPs | 30-60 min | Varies |

**Recommendation:** Start with Google OAuth for testing. Add Azure AD for enterprise customers.

### 3.2 Google OAuth Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create new project (or select existing)
3. Enable **Google+ API** (APIs & Services → search "Google+ API" → Enable)
4. Configure **OAuth consent screen**:
   - User type: External
   - App name, support email, developer contact
   - Save (skip optional scopes)
5. Create **OAuth 2.0 Client ID**:
   - Application type: Web application
   - Authorized redirect URI: your Cognito domain + `/oauth2/idpresponse`
     ```
     https://<your-prefix>.auth.<region>.amazoncognito.com/oauth2/idpresponse
     ```
6. Save your **Client ID** and **Client Secret**

**Verification checklist:**
- [ ] Google Cloud project created
- [ ] Google+ API enabled
- [ ] OAuth consent screen configured
- [ ] OAuth Client ID and Secret obtained
- [ ] Redirect URI set to Cognito's `/oauth2/idpresponse`

### 3.3 Azure AD Setup

1. Go to [Azure Portal](https://portal.azure.com/) → App registrations → New registration
2. Name: your app name
3. Supported account types: **Multitenant** (any Azure AD directory)
4. Redirect URI: Web → your Cognito domain + `/oauth2/idpresponse`
5. After creation → **Certificates & secrets** → New client secret → copy value immediately
6. Note from **Overview**: Application (client) ID, Directory (tenant) ID
7. Optional: **Token configuration** → Add optional claims → ID tab → check `email`, `given_name`, `family_name`

**Verification checklist:**
- [ ] Azure app registration created
- [ ] Client ID and Tenant ID noted
- [ ] Client secret created and saved
- [ ] Redirect URI set to Cognito's `/oauth2/idpresponse`

### 3.4 Wire Provider into Cognito

Once you have credentials from your chosen provider:

1. **AWS Cognito → User Pools → your pool → Sign-in experience → Federated sign-in**
2. **Add identity provider:**

   **For Google:**
   - Provider: Google
   - Client ID: paste from Google
   - Client secret: paste from Google
   - Authorized scopes: `profile email openid`

   **For Azure:**
   - Provider: OIDC
   - Client ID: paste from Azure
   - Client secret: paste from Azure
   - Authorized scopes: `openid profile email`
   - Issuer URL: `https://login.microsoftonline.com/{azure-tenant-id}/v2.0`

3. **Map provider attributes** to Cognito attributes:
   | Provider Claim | Cognito Attribute |
   |---------------|-------------------|
   | `email` | `email` |
   | `name` | `name` |
   | `given_name` | `given_name` |
   | `family_name` | `family_name` |

4. **App client settings:**
   - Allowed OAuth flows: ✅ Authorization code grant
   - Allowed OAuth scopes: ✅ email, ✅ openid, ✅ profile
   - Identity providers: ✅ check your new provider
   - Callback URL: `http://localhost:5173/callback` (and production URL)

5. **Link provider to Cognito domain** (App integration → Domain name)

6. **Test:** Open Hosted UI → should show "Continue with Google/Azure" button alongside email/password form

**Verification checklist:**
- [ ] Identity provider added to Cognito User Pool
- [ ] Attribute mapping configured
- [ ] App client has provider enabled + OAuth flows
- [ ] Callback URL registered
- [ ] Provider linked to domain
- [ ] Hosted UI shows SSO button
- [ ] Clicking SSO button → provider login → redirect back works

---

## Part 4: SSO Implementation Plan

> Database changes, backend endpoints, and frontend work needed to fully support SSO.

### 4.1 Database Changes

**New table: `tenant_domains`**
```sql
CREATE TABLE tenant_domains (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    domain VARCHAR(255) NOT NULL,
    verified BOOLEAN DEFAULT false,
    verification_token VARCHAR(255),
    sso_provider VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE UNIQUE INDEX idx_tenant_domains_domain ON tenant_domains(domain);
```

**Alter `tenants`:**
```sql
ALTER TABLE tenants ADD COLUMN sso_enabled BOOLEAN DEFAULT false;
ALTER TABLE tenants ADD COLUMN sso_enforce BOOLEAN DEFAULT false;
ALTER TABLE tenants ADD COLUMN sso_provider VARCHAR(50);
```

**Alter `users`:**
```sql
ALTER TABLE users ADD COLUMN sso_provider VARCHAR(50);
ALTER TABLE users ADD COLUMN sso_sub VARCHAR(255);
```

### 4.2 Backend Service

**New file: `services/sso_service.py`**

```python
def handle_sso_login(sso_claims: dict, db: Session) -> User:
    """
    Called after Cognito SSO callback. sso_claims come from the JWT.
    
    1. Find user by sso_sub or email
    2. Create user if not found (just-in-time provisioning)
    3. Extract domain from email
    4. Find tenant with verified domain
    5. Create membership if user not already a member (default: account_member)
    6. Return user
    """

def verify_domain_ownership(tenant_id: UUID, domain: str, db: Session) -> bool:
    """Check DNS TXT record for verification token."""

def get_tenant_by_domain(domain: str, db: Session) -> Tenant | None:
    """Find which tenant owns a verified domain."""
```

### 4.3 Backend Endpoints

| Method | Path | Guard | Purpose |
|--------|------|-------|---------|
| `POST` | `/tenants/{id}/domains` | `members:manage` | Add domain for verification |
| `GET` | `/tenants/{id}/domains/{domain}/verify` | `members:manage` | Check DNS and mark verified |
| `DELETE` | `/tenants/{id}/domains/{domain}` | `members:manage` | Remove domain |
| `PATCH` | `/tenants/{id}/sso-settings` | `members:manage` | Enable/disable SSO, set provider, toggle enforcement |

### 4.4 Frontend Changes

**Login page:** Add SSO buttons that redirect to Cognito with `identity_provider` hint:

```javascript
const handleSSOLogin = (provider) => {
  const params = new URLSearchParams({
    identity_provider: provider,  // 'Google', 'AzureAD'
    redirect_uri: VITE_COGNITO_REDIRECT_URI,
    response_type: 'code',
    client_id: VITE_COGNITO_CLIENT_ID,
    scope: 'email openid profile',
  });
  window.location.href = `https://${VITE_COGNITO_DOMAIN}/oauth2/authorize?${params}`;
};
```

**Admin page:** SSO settings panel where tenant admins can:
- Enable/disable SSO
- Choose provider
- Add and verify company domain
- Toggle SSO enforcement

### 4.5 SSO Role Assignment

When auto-creating a membership for an SSO user:

**MVP approach:** Assign `account_member` role. Admins promote manually.

**Advanced (future):** Map SSO group claims to roles:
```python
# SSO provider sends groups: ['engineering', 'marketing']
# Tenant admin configures: engineering → account_admin, marketing → account_member
SSO_ROLE_MAPPING = {
    'tenant-uuid': {
        'engineering': 'account_admin',
        'marketing': 'account_member',
    }
}
```

Store mappings in a `tenant_sso_role_mappings` table so admins can configure via UI.

---

## Part 5: Security Considerations

### Email Domain Verification

| Provider | How to verify enterprise domain |
|----------|-------------------------------|
| Google Workspace | Check `hd` claim (hosted domain). Absent = personal Gmail → reject for enterprise tenants |
| Azure AD | Check `tid` claim (Azure tenant ID) |
| Okta | Check `org` claim |

### Account Takeover Prevention

**Problem:** Attacker registers `bob@acme.com` with email/password before real Bob SSOs in.

**Solution:**
1. SSO user arrives → check `email_verified` claim from provider
2. If existing DB user has `email_verified=false` → overwrite with SSO claims
3. If existing DB user has `email_verified=true` → require manual account linking
4. Always match on `sso_sub` first, email second

### Deprovisioning

| Level | Behavior |
|-------|----------|
| **Basic SSO** | Employee leaves → their SSO login stops working at the provider, but existing tokens remain valid until expiry |
| **With SCIM** (future) | Provider sends webhook → your app suspends user immediately via `suspend_user()` |

**Recommendation:** Basic SSO is sufficient for MVP. SCIM can be added later for enterprise customers who require instant deprovisioning.

### Common Gotchas

| Issue | Why It Happens | Fix |
|-------|---------------|-----|
| Clock skew | SSO tokens check timestamps; >5 min drift = rejection | Sync server with NTP |
| Token size | SSO tokens with group claims can exceed cookie limits | Store token server-side (you already do this with sessions) |
| Missing JIT provisioning | User authenticates but gets "Account not found" | Always create user on first SSO login via `sync_user_from_cognito()` |

---

## Part 6: Testing SSO

### Local Development

SSO providers require HTTPS callback URLs. Options for local testing:

| Method | Effort | How |
|--------|--------|-----|
| **ngrok** (recommended) | 2 min | `ngrok http 5173` → use the `https://xxx.ngrok.io` URL in Cognito + provider config |
| **hosts + self-signed cert** | 30 min | Add `127.0.0.1 dev.yourapp.local` to hosts file, configure HTTPS in Vite |

### Test Accounts

| Provider | How to Get Test Accounts |
|----------|------------------------|
| Google Workspace | 14-day free trial → create `admin@testdomain.com`, `user1@testdomain.com` |
| Azure AD | Microsoft 365 Developer Program (free, 90 days) → get test tenant with sample users |
| Okta | Free developer account at developer.okta.com |

### Test Scenarios

**Happy path:**
- [ ] New SSO user signs in → auto-provisioned → correct tenant → default role
- [ ] Existing user signs in via SSO → recognized → correct tenant access
- [ ] SSO user appears in tenant user list

**Multi-tenant:**
- [ ] SSO user in Tenant A, email/password user in Tenant B → tenant switcher shows both
- [ ] Different tenants can use different SSO providers

**Domain verification:**
- [ ] Cannot SSO into tenant without verified domain
- [ ] DNS verification succeeds after TXT record is added
- [ ] Removing verified domain blocks future SSO logins

**Enforcement:**
- [ ] `sso_enforce=true` → email/password login blocked for that tenant's users
- [ ] `sso_enforce=false` → both methods work
- [ ] Invited contractors can always use email/password

**Error cases:**
- [ ] SSO gracefully fails if provider is down
- [ ] Clear error if domain not verified
- [ ] Clear error if SSO disabled for tenant

---

## Part 7: Migration & Effort Estimates

### Migrating Existing Users to SSO

**Recommended approach (gradual):**
1. Tenant admin enables SSO with `sso_enforce=false`
2. Both email/password and SSO work simultaneously
3. Show banner: "Your company now supports SSO! Click to link your account"
4. Users opt in → backend links SSO identity to existing account (matching by email)
5. After transition period → admin can set `sso_enforce=true`

### Effort Estimate

| Phase | Scope | Estimate |
|-------|-------|----------|
| Provider setup + Cognito federation | Config only, no code | 2-4 hours |
| Database migrations (`tenant_domains`, SSO columns) | Alembic migration | 2-3 hours |
| `sso_service.py` (domain verify, JIT provisioning, role mapping) | New service | 8-12 hours |
| Admin API endpoints (domains, SSO settings) | 4 new routes | 4-6 hours |
| Frontend: SSO login button + callback handling | Modify `LoginForm`, `cognitoClient` | 4-6 hours |
| Frontend: SSO admin settings page | New page | 4-6 hours |
| Testing + edge cases | All scenarios above | 8-12 hours |
| **Total (MVP, single provider)** | | **32-48 hours** |
| **Each additional provider** | Mostly config + testing | **8-14 hours** |

---

## References

- [AWS Cognito + Google Federation](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-identity-pools-google-identity-provider.html)
- [AWS Cognito + SAML Federation](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-identity-pools-saml-idp.html)
- [Google OAuth 2.0 for Web Apps](https://developers.google.com/identity/protocols/oauth2)
- [Microsoft Identity Platform](https://learn.microsoft.com/en-us/entra/identity-platform/)
- [Okta Developer Docs](https://developer.okta.com/docs/)

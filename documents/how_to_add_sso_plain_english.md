# How to Add SSO to Your Auth System

**Plain English Guide**  
Date: 2026-03-08  
Audience: Non-technical understanding, implementation planning

---

## What is SSO and Why Add It?

**SSO (Single Sign-On)** lets your users log in using their company's identity system instead of creating a new username/password for your app.

**Real-world example:**
- Without SSO: User creates account with email/password in your app
- With SSO: User clicks "Sign in with Google Workspace" and uses their existing work email login

**Why companies want it:**
- Employees already have one login for everything at work
- IT team can manage who has access from one central place
- When someone leaves the company, IT disables their account and they automatically lose access to your app too
- More secure (company enforces password policies, 2FA, etc.)

---

## How SSO Works with Your Current System

### Your Current Setup (Without SSO)

Right now your auth flow looks like this:

```
1. User goes to your app
2. User clicks "Login"
3. AWS Cognito shows login page
4. User types email + password
5. Cognito verifies credentials
6. User gets logged in
7. Your app creates/updates user record in database
8. User can access their tenant(s)
```

### With SSO Added

The flow becomes:

```
1. User goes to your app
2. User clicks "Sign in with [Company Name]"
3. User gets redirected to their company's login page (Google, Microsoft, Okta, etc.)
4. User logs in there (or already logged in, so instant)
5. Company's system says "Yes, this person is legit" and sends back to Cognito
6. Cognito trusts that verification
7. Your app creates/updates user record in database
8. User can access their tenant(s)
```

**Key insight:** You're not replacing Cognito. You're teaching Cognito to trust other login systems.

---

## Multi-Tenancy and SSO: The Relationship

This is where it gets interesting for your multi-tenant system.

### Scenario 1: SSO for Entire Tenants

**Example:** Acme Corp (a tenant in your system) wants all their employees to use SSO.

**How it works:**
1. Acme Corp admin enables SSO in your app settings
2. They configure it to use their Google Workspace or Azure AD
3. When Acme employees try to log in, they **must** use SSO
4. Regular email/password login is disabled for Acme users

**Database impact:**
- Your `tenants` table gets new fields:
  - `sso_enabled` (true/false)
  - `sso_provider` (google, azure, okta, etc.)
  - `sso_domain` (acme.com - so only @acme.com emails can SSO into this tenant)
  - `sso_enforce` (true = force SSO, false = optional)

### Scenario 2: Mixed Users in Same Tenant

**Example:** Acme Corp has:
- 50 employees (use SSO)
- 5 contractors (use email/password)

**How it works:**
1. Acme tenant has `sso_enabled=true` but `sso_enforce=false`
2. Employees click "Sign in with Google Workspace"
3. Contractors click "Sign in with Email" (regular Cognito login)
4. Both end up in the same tenant, both can collaborate

**Database impact:**
- Your `users` table gets new field:
  - `sso_provider` (null for regular users, 'google' for SSO users)

### Scenario 3: User in Multiple Tenants with Different SSO

**Example:** Jane works at:
- Acme Corp (uses Google Workspace SSO)
- Beta Inc (uses Microsoft Azure AD SSO)
- Gamma LLC (no SSO, email/password)

**How it works:**
1. Jane's email is `jane@acme.com`
2. When accessing Acme tenant: must use Google SSO
3. When accessing Beta tenant: might use different email `jane@betainc.com` with Azure SSO
4. When accessing Gamma tenant: uses email/password

**Database impact:**
- Your `memberships` table already handles this
- Each membership links Jane's user record to a tenant with a role
- SSO is per-tenant, not per-user globally

---

## The Setup Process (High-Level)

### Phase 1: Choose Your SSO Providers (1-2 hours)

**Decision:** Which identity providers will you support?

**Common options:**
- **Google Workspace** (Gmail for Business) - easiest to set up
- **Microsoft Azure AD** (Office 365 login) - very common in enterprises
- **Okta** - dedicated identity management platform
- **Generic SAML 2.0** - covers custom enterprise systems

**Recommendation for MVP:** Start with Google Workspace only. Add others later.

**Why:** Google is easiest to test and configure. Once you understand the pattern, adding Microsoft/Okta is similar.

---

### Phase 2: Configure Cognito Federation (2-4 hours)

**What you're doing:** Teaching Cognito to trust the SSO provider.

**Steps in AWS Console:**

1. **Go to your Cognito User Pool**
   - Currently: `eu-west-1_ynis0WItp`

2. **Add Identity Provider**
   - Click "Sign-in experience" tab
   - Click "Add identity provider"
   - Choose provider type (Google, SAML, OIDC)

3. **For Google Workspace (example):**
   - Get credentials from Google Cloud Console:
     - Client ID: `123456-abcdef.apps.googleusercontent.com`
     - Client Secret: `secret-key-here`
   - Set authorized scopes: `email`, `openid`, `profile`
   - Set callback URL: Your Cognito domain + `/oauth2/idpresponse`
     - Example: `https://eu-west-1ynis0witp.auth.eu-west-1.amazoncognito.com/oauth2/idpresponse`

4. **Map attributes**
   - SSO provider sends: `email`, `name`, `family_name`
   - Cognito expects: `email`, `name`
   - You create mapping: provider's `email` → Cognito's `email`

5. **Save and test**
   - Cognito gives you a test login URL
   - Try it before coding anything

**Output:** Cognito now has a "Sign in with Google" button on the managed login page.

---

### Phase 3: Handle Domain Verification (1-2 hours)

**Problem:** How do you ensure only real Acme Corp employees can join the Acme tenant?

**Solution:** Domain verification.

**Process:**

1. **Acme admin claims their domain in your app**
   - They say "We own acme.com"
   - Your app generates a verification code
   - They add DNS TXT record: `your-app-verify=abc123def456`
   - Your app checks DNS, confirms ownership

2. **You store verified domains**
   - Database table: `tenant_domains`
   - Fields:
     - `tenant_id`
     - `domain` (acme.com)
     - `verified` (true/false)
     - `sso_provider` (google)

3. **When someone tries to SSO in:**
   - They log in via Google
   - Google says "email is bob@acme.com"
   - Your app checks: "Is acme.com a verified domain for any tenant?"
   - If yes: auto-add Bob to that tenant
   - If no: reject or ask Bob to request access

**This prevents:**
- Random people at other companies using SSO to access Acme's tenant
- Someone registering `acme.xyz` and pretending to be Acme Corp

---

### Phase 4: Code Changes (Backend)

#### New Database Tables

**Table: `tenant_domains`**
```sql
CREATE TABLE tenant_domains (
    id UUID PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    domain VARCHAR(255) NOT NULL,
    verified BOOLEAN DEFAULT false,
    verification_token VARCHAR(255),
    sso_provider VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Table updates: `tenants`**
```sql
ALTER TABLE tenants ADD COLUMN sso_enabled BOOLEAN DEFAULT false;
ALTER TABLE tenants ADD COLUMN sso_enforce BOOLEAN DEFAULT false;
ALTER TABLE tenants ADD COLUMN sso_provider VARCHAR(50);
```

**Table updates: `users`**
```sql
ALTER TABLE users ADD COLUMN sso_provider VARCHAR(50);
ALTER TABLE users ADD COLUMN sso_sub VARCHAR(255); -- unique ID from SSO provider
```

#### New Backend Endpoints

**1. Domain verification:**
- `POST /tenants/{tenant_id}/domains` - Add domain to verify
- `GET /tenants/{tenant_id}/domains/{domain}/verify` - Check DNS and mark verified
- `DELETE /tenants/{tenant_id}/domains/{domain}` - Remove domain

**2. SSO configuration:**
- `PATCH /tenants/{tenant_id}/sso-settings` - Enable/disable SSO, set provider, set enforcement

**3. SSO login callback handling:**
- `POST /auth/sso-callback` - Handle user coming back from SSO provider
  - Extract claims (email, name, sub)
  - Find or create user
  - Find correct tenant based on email domain
  - Create/update membership
  - Return JWT token

#### Logic Changes

**File: `backend/app/auth_usermanagement/services/sso_service.py` (new)**

Key functions you'll need:

```python
def handle_sso_login(sso_claims: dict) -> User:
    """
    Called when user logs in via SSO.
    
    Claims look like:
    {
        "email": "bob@acme.com",
        "name": "Bob Smith",
        "sub": "google-oauth2|123456789",
        "email_verified": true
    }
    
    Logic:
    1. Check if user exists (by email or sso_sub)
    2. If not, create new user
    3. Extract domain from email (@acme.com)
    4. Find tenant with that verified domain
    5. Check if user is already a member
    6. If not, create membership with default role (usually 'member')
    7. Return user object
    """
    
def verify_domain_ownership(tenant_id: UUID, domain: str) -> bool:
    """
    Check DNS TXT records for verification token.
    Uses dnspython library.
    """
    
def get_tenant_by_domain(domain: str) -> Tenant | None:
    """
    Find which tenant owns a verified domain.
    """
```

---

### Phase 5: Code Changes (Frontend)

#### SSO Login Button

**File: `frontend/src/auth_usermanagement/components/LoginForm.jsx`**

Add SSO button:

```jsx
function LoginForm() {
  const handleSSOLogin = (provider) => {
    // Redirect to Cognito hosted UI with identity provider hint
    const cognitoUrl = `https://eu-west-1ynis0witp.auth.eu-west-1.amazoncognito.com`;
    const clientId = '79pef2au4irn8s7hcic9ik9d4p';
    const redirectUri = 'http://localhost:5173/callback';
    const idp = provider; // 'Google', 'AzureAD', etc.
    
    window.location.href = `${cognitoUrl}/oauth2/authorize?` +
      `identity_provider=${idp}&` +
      `redirect_uri=${redirectUri}&` +
      `response_type=code&` +
      `client_id=${clientId}&` +
      `scope=email openid profile`;
  };

  return (
    <div>
      {/* Existing email/password form */}
      
      <div style={{ margin: '20px 0', textAlign: 'center' }}>
        <div>─── OR ───</div>
      </div>
      
      <button onClick={() => handleSSOLogin('Google')}>
        Sign in with Google
      </button>
      
      <button onClick={() => handleSSOLogin('AzureAD')}>
        Sign in with Microsoft
      </button>
    </div>
  );
}
```

#### SSO Settings UI (Admin)

**New file: `frontend/src/auth_usermanagement/pages/SSOSettings.jsx`**

Page where tenant admins can:
- Enable/disable SSO
- Choose which provider (Google, Microsoft, etc.)
- Add their company domain
- See verification status
- Click "Verify Domain" button
- Toggle "Enforce SSO" (block email/password login)

**UI wireframe:**
```
┌─────────────────────────────────────────┐
│ SSO Configuration                       │
├─────────────────────────────────────────┤
│                                         │
│ [✓] Enable SSO for this tenant         │
│                                         │
│ Provider: [ Google Workspace ▾ ]       │
│                                         │
│ Company Domain                          │
│ ┌─────────────────────────────────────┐ │
│ │ acme.com                            │ │
│ └─────────────────────────────────────┘ │
│ Status: ⚠️ Not Verified                │
│                                         │
│ Verification Steps:                     │
│ 1. Add this DNS TXT record:            │
│    Name: _your-app-verify              │
│    Value: abc123def456                 │
│                                         │
│ 2. Click verify after DNS updates      │
│    [Verify Domain Now]                 │
│                                         │
│ [ ] Enforce SSO (disable email/password)│
│                                         │
│ [Save Settings]                         │
└─────────────────────────────────────────┘
```

---

### Phase 6: Multi-Tenancy Integration

#### Auto-Assignment to Tenant

**The Flow:**

```
1. Bob at Acme Corp clicks "Sign in with Google"
2. Google authenticates Bob
3. Bob's email is bob@acme.com
4. Your app extracts domain: acme.com
5. Your app queries: "Which tenant owns acme.com?"
6. Found: Tenant "Acme Corporation" (tenant_id: uuid-123)
7. Check: Is Bob already a member?
   - No: Create membership with role 'member'
   - Yes: Update last_login
8. Bob is now logged in and sees Acme tenant
```

#### Role Assignment Rules

**Question:** When auto-creating a user via SSO, what role should they get?

**Options:**

**Option 1: Always 'member' (safest)**
- Everyone starts as member
- Admin manually promotes to admin if needed
- Prevents auto-admin accidents

**Option 2: Map from SSO claims (advanced)**
- SSO provider sends: `groups: ['acme-admins', 'acme-users']`
- Your mapping: `acme-admins` → `admin` role
- Your mapping: `acme-users` → `member` role
- Automatic but requires configuration

**Recommendation:** Start with Option 1, add Option 2 later if customers need it.

#### Handling Multiple Tenants

**Scenario:** Bob has bob@acme.com but also contractor access to Beta Inc.

**Solution 1: Email-based (simple)**
- Bob can only SSO into Acme (his email domain)
- For Beta Inc, Bob uses separate email/password or they invite bob@acme.com manually

**Solution 2: Account linking (complex)**
- Bob SSOs with bob@acme.com → auto-joins Acme
- Bob is manually invited to Beta Inc with same email
- System links both memberships to same user account
- Bob sees both tenants in tenant switcher

**Recommendation:** Start with Solution 1. It's simpler and matches how most companies work.

---

## Security Considerations

### 1. Email Verification

**Problem:** SSO providers like Google verify the email is real, but do they verify the user owns that email domain?

**Answer:** Most enterprise SSO does, but consumer Google does not.

**Solution:**
- For Google Workspace: Check `hd` claim (hosted domain) in the token
  - If `hd=acme.com`, Google confirms this is an Acme Workspace account
  - If `hd` is absent, it's personal Gmail (reject for enterprise tenants)
- For Azure AD: Check `tid` claim (tenant ID in Microsoft)
- For Okta: Check `org` claim

### 2. Account Takeover Prevention

**Problem:** What if someone creates account with `bob@acme.com` using email/password before Bob SSOs in?

**Scenario:**
1. Attacker creates account: `bob@acme.com` with password (doesn't verify email)
2. Real Bob tries to SSO later
3. System finds existing `bob@acme.com` user
4. Attacker now locked out? Or Bob locked out?

**Solution:**
- When SSO user first arrives, check `email_verified` claim
- If existing user has `email_verified=false`, overwrite with SSO claims
- If existing user has `email_verified=true`, require manual account linking
- Add `sso_sub` field to users table (unique identifier from SSO provider)
- Match on `sso_sub` first, email second

### 3. Deprovisioning

**Problem:** Employee leaves Acme Corp. IT disables their Google Workspace account. Should they lose access to your app?

**Answer:** Not automatically with basic SSO. Their existing session/tokens still work.

**Advanced solution (later):**
- Implement SCIM (System for Cross-domain Identity Management)
- SSO provider sends webhooks: "user bob@acme.com was deactivated"
- Your app receives webhook, suspends user automatically
- Requires more complex setup, usually not MVP

---

## Testing Strategy

### Local Testing (Dev Environment)

**Problem:** SSO providers need real HTTPS URLs for security. Can't use `localhost`.

**Solutions:**

**Option 1: ngrok (easiest)**
1. Install ngrok: `choco install ngrok` (Windows)
2. Run: `ngrok http 5173`
3. Get URL: `https://abc123.ngrok.io`
4. Use this URL in Cognito/Google configuration
5. Test SSO flow through ngrok URL

**Option 2: hosts file + self-signed cert (harder)**
1. Edit `C:\Windows\System32\drivers\etc\hosts`
2. Add: `127.0.0.1 dev.yourapp.local`
3. Generate self-signed SSL cert
4. Configure Vite to use HTTPS
5. Test at `https://dev.yourapp.local:5173`

**Recommendation:** Use ngrok for initial testing. It's temporary but fast.

### Creating Test SSO Accounts

**For Google Workspace:**
1. Sign up for Google Workspace trial (14 days free)
2. Create test accounts: `admin@yourtestdomain.com`, `user1@yourtestdomain.com`
3. Configure as identity provider
4. Test full flow

**For Azure AD:**
1. Create Microsoft 365 Developer account (free, 90 days)
2. Get test tenant with sample users
3. Configure federation
4. Test

### Test Scenarios

Essential tests before launching:

1. **Happy path:**
   - [ ] New SSO user can sign in
   - [ ] Auto-assigned to correct tenant
   - [ ] Gets correct default role
   - [ ] Can access tenant resources

2. **Existing users:**
   - [ ] User with verified email can link SSO
   - [ ] User with unverified email gets overwritten by SSO

3. **Domain verification:**
   - [ ] Can't SSO into tenant without verified domain
   - [ ] DNS verification works correctly
   - [ ] Removing domain blocks future SSO

4. **Multi-tenant:**
   - [ ] User can SSO into Tenant A
   - [ ] Same user can email/password into Tenant B
   - [ ] Tenant switcher shows both

5. **Error cases:**
   - [ ] SSO fails gracefully if provider is down
   - [ ] Clear error if domain not verified
   - [ ] Clear error if SSO disabled for tenant

---

## Migration Path for Existing Users

**Problem:** You have 1000 users using email/password. Acme Corp enables SSO. What happens?

**Options:**

**Option 1: Gradual migration (safest)**
1. Enable SSO but don't enforce
2. Both email/password and SSO work
3. Show banner: "Your company now supports SSO! Click here to link your account"
4. User clicks, goes through SSO flow
5. Backend links SSO to existing account (matching by email)
6. User can now use either method
7. After 30 days, admin can enforce SSO only

**Option 2: Forced migration**
1. Enable and enforce SSO
2. Email/password logins fail
3. User must use SSO
4. Backend auto-links on first SSO login

**Recommendation:** Option 1 gives users time to adapt without support tickets flooding in.

---

## Estimated Effort

### MVP (Single SSO Provider - Google)

- **Setup & Learning:** 4-8 hours
  - Understanding Cognito federation
  - Creating test Google Workspace
  - Configuring integration

- **Backend Development:** 12-16 hours
  - Database migrations (tables, fields)
  - SSO callback handler
  - Domain verification logic
  - User/membership creation logic
  - Admin API endpoints

- **Frontend Development:** 8-12 hours
  - SSO button on login page
  - Callback page handler
  - SSO settings admin page
  - Domain verification UI
  - Testing across flows

- **Testing & Debugging:** 8-12 hours
  - Manual testing scenarios
  - Edge case handling
  - Error message refinement
  - Documentation

**Total: 32-48 hours (4-6 days of focused work)**

### Adding Second Provider (Microsoft/Okta)

Once you have Google working:
- **Setup:** 2-4 hours (mostly config)
- **Code changes:** 2-4 hours (mostly copy/paste with tweaks)
- **Testing:** 4-6 hours

**Total per additional provider: 8-14 hours**

---

## SSO and Your Multi-Tenancy Model

### How They Work Together

Your multi-tenancy is actually perfect for SSO! Here's why:

**Current model:**
- User belongs to one or more tenants
- Each membership has a role
- RLS ensures data isolation
- Invitations bring users into tenants

**With SSO:**
- User can SSO into tenant if their email domain matches tenant's verified domain
- Membership is auto-created if needed
- RLS still protects data (nothing changes here)
- Invitations still work for contractors/external users

**They're complementary, not competing.**

### Real-World Example

**Acme Corp setup:**
```
Tenant: Acme Corporation
├─ Verified domains: ['acme.com']
├─ SSO: Enabled (Google Workspace)
├─ Enforce SSO: Yes
└─ Members:
   ├─ alice@acme.com (admin) ← SSO
   ├─ bob@acme.com (member) ← SSO
   ├─ charlie@acme.com (member) ← SSO
   └─ contractor@freelance.com (member) ← Email/Password (invited)
```

**What happens:**
- Alice, Bob, Charlie MUST use Google SSO (enforcement on)
- Contractor uses email/password (exempted from enforcement)
- All four see same tenant data (RLS uses tenant_id regardless of auth method)
- Admin can manage all users in the same UserList UI
- SSO users show badge: "🔐 SSO User" in the list

### Database Query Example

When Bob (SSO) and Contractor (email/pass) both query tenant data:

```sql
-- Bob's query (tenant_id set in session from SSO auth)
SET app.current_tenant_id = 'acme-tenant-uuid';
SELECT * FROM tenant_data WHERE tenant_id = 'acme-tenant-uuid';

-- Contractor's query (tenant_id set in session from regular auth)
SET app.current_tenant_id = 'acme-tenant-uuid';
SELECT * FROM tenant_data WHERE tenant_id = 'acme-tenant-uuid';
```

**Same RLS policy applies to both.** Auth method doesn't matter to RLS.

---

## Common Gotchas

### 1. Clock Skew

**Problem:** SSO tokens have timestamp validations. If your server clock is off by >5 minutes, tokens get rejected.

**Solution:** Ensure servers sync with NTP (Network Time Protocol).

### 2. Token Size

**Problem:** SSO tokens can be large (especially with group claims). Exceed cookie size limits.

**Solution:** Store token in backend session, just send session ID cookie to frontend.

### 3. Just-In-Time Provisioning

**Term:** Creating user accounts automatically when they SSO for the first time.

**Your case:** You should **always** do this. Otherwise users get "Account not found" even though they successfully authenticated.

**Implementation:** In your SSO callback handler, always:
1. Try to find user
2. If not found, create user
3. Assign to appropriate tenant
4. Create membership
5. Return success

### 4. Group/Role Mapping

**Problem:** Companies want: "Anyone in our 'Engineering' AD group should be 'admin' in your app."

**Solution:** SSO claims include groups. You map them:

```python
SSO_ROLE_MAPPING = {
    'acme-tenant-uuid': {
        'acme-engineering': 'admin',
        'acme-marketing': 'member',
        'acme-executives': 'admin',
    }
}

def get_role_from_sso_groups(tenant_id: UUID, groups: list[str]) -> str:
    mapping = SSO_ROLE_MAPPING.get(str(tenant_id), {})
    for group in groups:
        if group in mapping:
            return mapping[group]
    return 'member'  # default
```

Store mapping in database so admins can configure it.

---

## Launch Checklist

Before turning on SSO for real customers:

- [ ] Domain verification tested and working
- [ ] At least 2 SSO providers configured and tested
- [ ] User auto-provisioning creates correct memberships
- [ ] Existing users can link SSO accounts
- [ ] Admin UI shows SSO status clearly
- [ ] Error messages are helpful (not "Error 500")
- [ ] Logged SSO events for debugging (who logged in when, from which provider)
- [ ] Privacy policy updated (you're now receiving data from SSO providers)
- [ ] Support docs written (screenshots of setup process)
- [ ] Tested on actual customer trial before GA launch

---

## Summary: The Big Picture

**SSO lets companies use their existing login system instead of passwords.**

**For your auth system:**
- Cognito becomes the hub that trusts multiple identity sources
- Your backend handles auto-provisioning users into tenants
- Your frontend shows appropriate login buttons
- Your RLS and permissions keep working exactly the same

**For your multi-tenancy:**
- Each tenant can have its own SSO configuration
- Domain verification ensures only real employees auto-join
- Contractors/guests can still use email/password
- All users in a tenant see same data (RLS doesn't care about auth method)

**Rough timeline:**
- Week 1: Setup and backend (domain verification, auto-provisioning)
- Week 2: Frontend UI (login buttons, admin settings)
- Week 3: Testing and refinement
- Week 4: Documentation and launch

**MVP recommendation:**
- Start with Google Workspace only
- Auto-assign role 'member' to all SSO users
- Require manual domain verification (no auto-verification)
- Keep email/password as fallback
- Launch to 3-5 pilot customers
- Iterate based on feedback

**You've got this! SSO is just another way to prove "this person is who they say they are" - and you already handle that well with Cognito.**

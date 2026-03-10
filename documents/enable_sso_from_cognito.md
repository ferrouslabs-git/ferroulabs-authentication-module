# Enable SSO from Cognito: Setup Guide

**Purpose:** Document all infrastructure and configuration steps required before implementing SSO features in the application code.

**Status:** Pre-implementation checklist

---

## Overview

Single Sign-On (SSO) allows users to authenticate via external identity providers (Google, Azure AD, etc.) instead of creating separate Cognito credentials. Once configured, the frontend can offer "Sign In with Google" buttons that federate through Cognito.

This guide covers **provider setup and Cognito configuration only**—no code changes yet.

---

## Prerequisites

You need:
- AWS account with Cognito User Pool already created (✅ you have this)
- Access to create OAuth apps in at least one external provider
- Cognito User Pool ID and App Client ID (already have these)
- Localhost callback URL: `http://localhost:5173/callback`

---

## Step 1: Choose Your Identity Provider

Pick at least one provider to test with:

### Option A: Google OAuth (Easiest, Free)
- **Pros:** Fastest setup, most users have Google accounts, no cost
- **Cons:** Consumer-focused, not ideal for enterprise
- **Effort:** 10 minutes

### Option B: Azure AD (Enterprise-Friendly)
- **Pros:** Enterprise users, role/group mapping, production-ready
- **Cons:** Requires Azure subscription or test tenant
- **Effort:** 20-30 minutes

### Option C: Okta (Full-Featured)
- **Pros:** Comprehensive SSO/IdP platform, excellent documentation
- **Cons:** Paid tier (free trial available)
- **Effort:** 20-30 minutes

---

## Option A: Configure Google OAuth

### Step A1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **Select a Project** → **New Project**
3. Name: `FerrousLabs SSO` (or similar)
4. Click **Create**
5. Wait for project to initialize

### Step A2: Enable Google+ API

1. In Google Cloud Console, search for **Google+ API**
2. Click **Google+ API** from results
3. Click **Enable**
4. Allow 1-2 minutes for activation

### Step A3: Create OAuth 2.0 Credentials

1. Go to **Credentials** (left sidebar)
2. Click **Create Credentials** → **OAuth 2.0 Client ID**
3. You'll be prompted to configure **OAuth consent screen** first:
   - Click **Configure Consent Screen**
   - Choose **External** user type
   - Fill in:
     - **App name:** `FerrousLabs`
     - **User support email:** `ali@ferrouslabs.co.uk`
     - **Developer contact:** `ali@ferrouslabs.co.uk`
   - Click **Save and Continue** (skip optional scopes)
   - Click **Save and Continue** again
4. Return to **Credentials** and click **Create Credentials** → **OAuth 2.0 Client ID**
5. Choose **Web application**
6. Under **Authorized redirect URIs**, add:
   - `http://localhost:5173/callback`
7. Click **Create**
8. **Save these values:**
   - **Client ID** (looks like `xxx.apps.googleusercontent.com`)
   - **Client Secret** (looks like `GOCSPX-xxx`)

### Step A4: Verify You Have

- [ ] Google Project ID
- [ ] Google OAuth Client ID
- [ ] Google OAuth Client Secret
- [ ] Redirect URI registered: `http://localhost:5173/callback`

---

## Option B: Configure Azure AD

### Step B1: Create Azure App Registration

1. Go to [Azure Portal](https://portal.azure.com/)
2. Search for **App registrations**
3. Click **New registration**
4. Fill in:
   - **Name:** `FerrousLabs SSO`
   - **Supported account types:** `Accounts in any organizational directory (Any Azure AD directory - Multitenant)`
5. Under **Redirect URI**:
   - Platform: **Web**
   - URI: `http://localhost:5173/callback`
6. Click **Register**

### Step B2: Create Client Secret

1. In the app, go to **Certificates & secrets**
2. Click **New client secret**
3. Set expiry to **6 months** (or suitable for testing)
4. Click **Add**
5. **Copy the secret value immediately** (you won't see it again)

### Step B3: Note Your IDs

Go to **Overview** tab and **save:**
- **Application (client) ID**
- **Directory (tenant) ID**
- **Client Secret** (from previous step)

### Step B4: Configure Token Claims (Optional)

1. Go to **Token configuration**
2. Click **Add optional claim**
3. Select **ID** tab
4. Check: `email`, `given_name`, `family_name`
5. Click **Add**

### Step B5: Verify You Have

- [ ] Azure App (Client) ID
- [ ] Azure Tenant ID
- [ ] Azure Client Secret
- [ ] Redirect URI registered: `http://localhost:5173/callback`

---

## Step 2: Configure Cognito User Pool

### Step 2.1: Add Identity Provider to Cognito

1. Go to AWS Cognito → **User Pools** → select your pool
2. Left sidebar → **Sign-in experience** → **Federated sign-in**
3. In **Identity providers**, click to add one:

#### If Using Google:
- **Provider name:** `Google`
- **App ID (Client ID):** Paste your Google OAuth Client ID
- **App secret:** Paste your Google OAuth Client Secret
- **Authorized scopes:** `profile email openid`

#### If Using Azure:
- **Provider name:** `Azure`
- **App ID (Client ID):** Paste your Azure App (Client) ID
- **App secret:** Paste your Azure Client Secret
- **Authorize scope:** `openid profile email`
- **Tenant URL:** `https://login.microsoftonline.com/{tenant-id}` (replace with your Tenant ID)

### Step 2.2: Map Provider Attributes to User Pool

1. In the same **Identity providers** section, click **Attribute mapping**
2. Map provider claims to your user attributes:
   - **Email** → `email`
   - **Name** → `name` (if available)
   - **Given Name** → `given_name` (if available)
   - **Family Name** → `family_name` (if available)

### Step 2.3: Configure App Client for Federated Sign-In

1. Go to **App integration** → **App clients and analytics**
2. Select your app client
3. Under **Authentication flows:**
   - Ensure **Allow user password auth for admin API (ALLOW_ADMIN_USER_PASSWORD_AUTH)** is enabled
   - Ensure **Allow refresh token based authentication (ALLOW_REFRESH_TOKEN_AUTH)** is enabled
4. Under **Allowed OAuth flows:**
   - Check: ✅ **Authorization code flow**
   - Check: ✅ **Implicit flow** (if not already checked)
5. Under **Allowed OAuth scopes:**
   - Check: ✅ **email**
   - Check: ✅ **openid**
   - Check: ✅ **profile**
6. Under **Callback URLs (redirect URIs):**
   - Verify: `http://localhost:5173/callback` is listed

### Step 2.4: Link Provider to Domain

1. Go to **App integration** → **Domain name**
2. Ensure your Cognito domain is configured (e.g., `https://ferrouslabs-dev.auth.eu-west-1.amazoncognito.com`)
3. Go back to **Identity providers** → Your provider (Google/Azure)
4. At the bottom, click **Link provider to domain** or similar option
5. Your Cognito domain should now show as linked

### Step 2.5: Test Cognito Hosted UI with SSO

1. Go to **App integration** → **App client settings**
2. Find **Hosted UI preview** or **Hosted Sign-In Page**
3. Open the hosted login URL
4. Verify you see:
   - **Continue with Google** button (if Google configured)
   - **Continue with Azure** button (if Azure configured)
   - Original **Sign In** form

### Step 2.6: Verify Configuration

- [ ] Identity provider added to User Pool
- [ ] Attributes mapped correctly
- [ ] App client has OAuth flows enabled
- [ ] Callback URL is registered
- [ ] Provider linked to domain
- [ ] Hosted UI shows SSO buttons
- [ ] Clicking SSO buttons redirects to provider login

---

## Step 3: Test End-to-End (Manual)

### Test SSO Login Flow

1. Open your app at `http://localhost:5173/`
2. Click **Sign In**
3. You should see Cognito Hosted UI with:
   - Email/password form
   - "Continue with Google" button (or your provider)
4. Click **Continue with Google**
5. You'll be redirected to Google login
6. Sign in with a Google account
7. You'll be redirected back to `http://localhost:5173/callback` with an auth code
8. App should:
   - Exchange code for tokens via `/auth/sync`
   - Create user in database (or update if exists)
   - Redirect to dashboard
9. Dashboard shows your name/email

### Troubleshooting

| Issue | Solution |
|-------|----------|
| "Invalid redirect URI" | Ensure `http://localhost:5173/callback` is registered in both Google/Azure AND Cognito |
| Button doesn't appear in Hosted UI | Verify identity provider is linked to domain |
| After clicking provider, redirects back to login | Check provider credentials (Client ID, Secret) are correct |
| User created with wrong email | Check attribute mapping in Cognito identity provider settings |
| CORS error in browser console | Usually not an issue - Cognito handles this, but verify callback URL matches exactly |

---

## Summary: What You Should Have Now

Before moving to code implementation:

✅ **Identity Provider Configured**
- [ ] Google OAuth OR Azure AD OR other provider set up
- [ ] Client ID and secret obtained
- [ ] Redirect URI registered with provider

✅ **Cognito User Pool Updated**
- [ ] Identity provider added to User Pool
- [ ] Provider linked to Cognito domain
- [ ] Attribute mapping configured
- [ ] App client has OAuth flows enabled
- [ ] Callback URL registered

✅ **Manual Testing Passed**
- [ ] Cognito Hosted UI shows "Continue with [Provider]" button
- [ ] Clicking button redirects to provider login
- [ ] After provider login, user is redirected back and synced
- [ ] Dashboard shows authenticated user

---

## Next Steps (Code Implementation)

Once all checkboxes above are complete, we can:

1. Add **"Sign In with Google"** button to frontend
2. Add provider-specific login URLs in `cognitoClient.js`
3. Test federated login in the app UI
4. Add **"Sign In with Azure"** or other providers

---

## References

- [AWS Cognito + Google Federation](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-identity-pools-google-identity-provider.html)
- [AWS Cognito + Azure AD Federation](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-identity-pools-saml-idp.html)
- [Google OAuth 2.0 for Web Apps](https://developers.google.com/identity/protocols/oauth2)
- [Microsoft Identity Platform Documentation](https://learn.microsoft.com/en-us/entra/identity-platform/)

---

## Checklist Before Notifying Agent

- [ ] Identity provider (Google/Azure/other) configured
- [ ] Client ID and secret saved securely
- [ ] Cognito identity provider added
- [ ] Provider linked to Cognito domain
- [ ] Attribute mapping verified
- [ ] Callback URL registered everywhere
- [ ] Hosted UI shows SSO buttons
- [ ] Manual end-to-end test successful

When all items checked, reply: **"Setup complete, ready for code implementation"**

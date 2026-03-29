# Host Integration Guide: Mapping Your Domain Models

> How to integrate auth_usermanagement with your existing application — mapping your users, organizations, and domain entities to the module's data model.

---

## Overview

The `auth_usermanagement` module provides its own `users`, `tenants`, `memberships`, and `spaces` tables. Your host app doesn't replace these — it **links** its own domain tables to them.

This guide covers:

1. [Terminology mapping](#1-terminology-mapping) — rename "Tenant" to "Company", "Organization", etc.
2. [Linking host tables to module tables](#2-linking-host-tables-to-module-tables) — FK patterns
3. [Extending module entities with host-specific data](#3-extending-module-entities) — adding `logo_url`, `billing_id`, etc.
4. [Handling an existing users table](#4-existing-users-table) — migration strategies
5. [Service hooks and event patterns](#5-service-hooks) — reacting to user/tenant changes
6. [Working examples](#6-working-examples) — concrete patterns for common scenarios
7. [Frontend integration](#7-frontend-integration) — what ships to host vs what's demo-only, styling

---

## 1. Terminology Mapping

The module uses generic names internally (`Tenant`, `Space`, `User`). You control what users see via `auth_config.yaml` — **no backend code changes needed**.

### Rename via YAML

Edit `auth_config.yaml` to change display names:

```yaml
layers:
  account:
    enabled: true
    display_name: "Company"          # was "Account"
  space:
    enabled: true
    display_name: "Department"       # was "Space"
```

Common mappings:

| Your Domain Term | Module Internal Name | YAML `display_name` |
|-----------------|---------------------|---------------------|
| Company | Tenant (table: `tenants`) | `layers.account.display_name: "Company"` |
| Organization | Tenant | `layers.account.display_name: "Organization"` |
| Workspace | Tenant | `layers.account.display_name: "Workspace"` |
| Portfolio | Tenant | `layers.account.display_name: "Portfolio"` |
| Team | Space (table: `spaces`) | `layers.space.display_name: "Team"` |
| Project | Space | `layers.space.display_name: "Project"` |
| Department | Space | `layers.space.display_name: "Department"` |

### Frontend label updates

After changing `display_name` values in YAML, update frontend labels:

1. `TenantSwitcher` component — update dropdown labels
2. Any UI copy referencing "Tenant" or "Space"
3. The `config/roles` endpoint returns `display_name` values — use these for dynamic labels

### Two-layer apps (no sub-grouping)

If your app only has users-in-organizations (no sub-groups):

```yaml
layers:
  account:
    enabled: true
    display_name: "Organization"
  space:
    enabled: false                   # disables the space layer entirely
```

---

## 2. Linking Host Tables to Module Tables

The module's `tenants`, `users`, and `spaces` tables use **UUID primary keys**. Your host domain tables should reference them via foreign keys.

### Pattern: Host table references module table

```python
# In your host app's models (NOT inside auth_usermanagement/)
from app.database import Base
from sqlalchemy import Column, String, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from uuid import uuid4

class Project(Base):
    """Host domain model — linked to auth module's Tenant"""
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)
    description = Column(String(1000))

    # FK to the module's tenants table
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)

    # FK to the module's users table (who created this project)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))

    created_at = Column(DateTime)
```

### Pattern: Host table references module User

```python
class Report(Base):
    __tablename__ = "reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    title = Column(String(255))

    # Link to module's users table
    author_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))

    # Link to module's tenants table for tenant-scoping
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
```

### Key rules

| Rule | Why |
|------|-----|
| Always FK **from** host tables **to** module tables | Module tables are the source of truth for identity and tenancy |
| Never add FKs from module tables to host tables | This would create a dependency from the reusable module to your specific app |
| Use `ondelete="CASCADE"` for tenant FKs | When a tenant is deleted, host data scoped to that tenant should be cleaned up |
| Use `ondelete="SET NULL"` for user FKs | Preserves records if a user is deleted |
| All module PKs are UUID v4 | Your host tables must use UUID columns for FK references |

### Querying with tenant scope

In your host service layer, always filter by `tenant_id`:

```python
def get_projects_for_tenant(tenant_id: UUID, db: Session):
    return db.query(Project).filter(Project.tenant_id == tenant_id).all()
```

The module's `ScopeContext` (from permission guards) gives you the current tenant/space ID:

```python
from app.auth_usermanagement.security import require_permission

@router.get("/projects")
def list_projects(
    ctx = Depends(require_permission("data:read")),
    db: Session = Depends(get_db),
):
    # ctx.scope_id is the current tenant or space UUID
    return get_projects_for_tenant(ctx.scope_id, db)
```

---

## 3. Extending Module Entities

You need extra fields on users or tenants (e.g., `logo_url`, `stripe_customer_id`, `phone_number`). **Don't modify the module's model files** — create extension tables in your host app.

### Pattern: Extension table (one-to-one)

```python
# Host-owned model file, e.g., app/models/tenant_profile.py
from app.database import Base
from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

class TenantProfile(Base):
    """Host-owned extension of auth module's Tenant"""
    __tablename__ = "tenant_profiles"

    # Shared PK — same UUID as tenants.id
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True)

    logo_url = Column(String(500))
    stripe_customer_id = Column(String(255))
    billing_email = Column(String(255))
    industry = Column(String(100))
```

```python
class UserProfile(Base):
    """Host-owned extension of auth module's User"""
    __tablename__ = "user_profiles"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)

    phone_number = Column(String(50))
    avatar_url = Column(String(500))
    timezone = Column(String(50))
    preferred_language = Column(String(10))
```

### Querying extended data

```python
def get_tenant_with_profile(tenant_id: UUID, db: Session):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    profile = db.query(TenantProfile).filter(TenantProfile.tenant_id == tenant_id).first()
    return {
        "id": tenant.id,
        "name": tenant.name,
        "plan": tenant.plan,
        "logo_url": profile.logo_url if profile else None,
        "stripe_customer_id": profile.stripe_customer_id if profile else None,
    }
```

### Why not modify the module models directly?

- Keeps the module updatable — pulling upstream changes won't conflict with your customizations
- Maintains the import boundary rules (`.github/copilot-instructions.md`)
- Extension tables are owned by your Alembic migrations alongside your other host tables

---

## 4. Existing Users Table

If your app already has a `users` table before integrating the module, you have three options:

### Option A: Replace your table with the module's (recommended)

Best for new projects or pre-launch apps.

1. Migrate existing user data into the module's `users` table schema (UUID PK, `email`, `cognito_sub`, etc.)
2. Update all host FKs to point to the new `users.id`
3. Create a `UserProfile` extension table for any custom columns (see Section 3)
4. Drop your old user table

### Option B: Link via shared email (existing production app)

If you can't replace your table:

```python
class LegacyUser(Base):
    """Your existing user table — kept as-is"""
    __tablename__ = "app_users"
    id = Column(Integer, primary_key=True)  # your existing PK
    email = Column(String(255), unique=True)
    # ... your existing columns

class UserBridge(Base):
    """Maps legacy user IDs to module user IDs"""
    __tablename__ = "user_bridge"
    legacy_user_id = Column(Integer, ForeignKey("app_users.id"), primary_key=True)
    module_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True)
```

Then in your host services:

```python
def get_legacy_user(module_user: User, db: Session):
    bridge = db.query(UserBridge).filter(UserBridge.module_user_id == module_user.id).first()
    if bridge:
        return db.query(LegacyUser).filter(LegacyUser.id == bridge.legacy_user_id).first()
    return None
```

### Option C: Rename your table and use module's

Rename your existing `users` table to `app_users` or `legacy_users` via migration, then let the module create its `users` table. Bridge using Option B.

---

## 5. Service Hooks

The module doesn't provide built-in event callbacks, but you can add host-side hooks by wrapping module service calls.

### Pattern: Wrap module services in host services

```python
# Host-owned service: app/services/onboarding_service.py
from app.auth_usermanagement.services.tenant_service import create_tenant
from app.auth_usermanagement.services.user_service import sync_user_from_cognito
from app.models.tenant_profile import TenantProfile

def onboard_tenant(name: str, user, db, stripe_customer_id: str = None):
    """Host wrapper — creates tenant + sets up host-specific data"""
    # 1. Module handles auth tenant creation + membership
    tenant = create_tenant(name=name, user=user, db=db)

    # 2. Host handles domain-specific setup
    profile = TenantProfile(
        tenant_id=tenant.id,
        stripe_customer_id=stripe_customer_id,
    )
    db.add(profile)
    db.commit()

    return tenant

def on_user_synced(user, db):
    """Called after sync_user_from_cognito — host can create profile, send welcome email, etc."""
    existing = db.query(UserProfile).filter(UserProfile.user_id == user.id).first()
    if not existing:
        db.add(UserProfile(user_id=user.id))
        db.commit()
```

### Pattern: Override routes for custom behavior

If you need to change what happens at specific endpoints, mount your own route **before** the module router:

```python
# In host main.py — host route takes priority over module route
@app.post("/auth/tenants")
def create_tenant_with_billing(
    request: TenantCreateRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Your custom logic wrapping the module's service
    return onboard_tenant(
        name=request.name,
        user=current_user,
        db=db,
        stripe_customer_id=request.stripe_customer_id,
    )

# Module router mounted after — its /auth/tenants is shadowed
app.include_router(auth_router, prefix="/auth")
```

---

## 6. Working Examples

### Example A: SaaS Project Management App

**Domain:** Users belong to Companies. Each Company has Projects.

```yaml
# auth_config.yaml
layers:
  account: { enabled: true, display_name: "Company" }
  space:   { enabled: true, display_name: "Project" }
roles:
  platform:
    - name: super_admin
      permissions: [platform:configure, accounts:manage, users:suspend]
  account:
    - name: account_owner
      display_name: "Company Owner"
      permissions: [account:delete, account:read, spaces:create, members:manage, members:invite]
    - name: account_member
      display_name: "Company Member"
      permissions: [account:read]
  space:
    - name: space_admin
      display_name: "Project Manager"
      permissions: [space:delete, space:configure, space:read, members:manage, members:invite, data:read, data:write]
    - name: space_member
      display_name: "Contributor"
      permissions: [space:read, data:read, data:write]
    - name: space_viewer
      display_name: "Viewer"
      permissions: [space:read, data:read]
```

Host tables:

```
tenants (module)          ← "Company" — identity and access
  └── tenant_profiles     ← host extension: logo_url, billing_email, industry
  └── spaces (module)     ← "Project" — identity and access
       └── tasks          ← host domain: FK to spaces.id
       └── documents      ← host domain: FK to spaces.id
```

### Example B: Consulting Platform (TrustOS)

**Domain:** Consultants own Portfolios. Each Portfolio contains Organizations.

```yaml
layers:
  account: { enabled: true, display_name: "Portfolio" }
  space:   { enabled: true, display_name: "Organization" }
roles:
  account:
    - name: account_owner
      display_name: "Consultant"
      permissions: [account:delete, account:read, spaces:create, members:manage, members:invite]
  space:
    - name: space_admin
      display_name: "Org Admin"
      permissions: [space:delete, space:configure, space:read, members:manage, members:invite, data:read, data:write]
    - name: space_viewer
      display_name: "Viewer"
      permissions: [space:read, data:read]
```

Host tables:

```
tenants (module)          ← "Portfolio"
  └── spaces (module)     ← "Organization"
       └── snapshots      ← host domain: FK to spaces.id + tenants.id
       └── surveys        ← host domain: FK to spaces.id
```

### Example C: Simple Team App (no sub-grouping)

**Domain:** Users belong to Teams. No sub-groups needed.

```yaml
layers:
  account: { enabled: true, display_name: "Team" }
  space:   { enabled: false }
roles:
  account:
    - name: account_owner
      display_name: "Team Owner"
      permissions: [account:delete, account:read, members:manage, members:invite]
    - name: account_member
      display_name: "Member"
      permissions: [account:read, data:read, data:write]
```

Host tables:

```
tenants (module)          ← "Team"
  └── channels            ← host domain: FK to tenants.id
  └── messages            ← host domain: FK to tenants.id + users.id
```

---

## Quick Reference: Module Tables You Link To

| Module Table | PK Type | Your FK Column | Use For |
|-------------|---------|---------------|---------|
| `tenants` | UUID | `tenant_id` | Scoping domain data to an organization |
| `users` | UUID | `user_id`, `created_by`, `author_id` | Linking domain records to users |
| `spaces` | UUID | `space_id` | Scoping domain data to a sub-group |

## Quick Reference: What to Change vs What to Leave Alone

| Task | Where to Change | Inside Module? |
|------|----------------|---------------|
| Rename "Tenant" → "Company" | `auth_config.yaml` `display_name` | YAML only |
| Rename roles | `auth_config.yaml` role `display_name` | YAML only |
| Add/remove permissions | `auth_config.yaml` role `permissions` | YAML only |
| Add `logo_url` to tenant | Host-owned `TenantProfile` table | No |
| Add `phone` to user | Host-owned `UserProfile` table | No |
| Link domain data to tenant | Host FK → `tenants.id` | No |
| Custom tenant creation logic | Host wrapper around `create_tenant()` | No |
| Disable spaces | `auth_config.yaml` `space.enabled: false` | YAML only |
| Change inheritance | `auth_config.yaml` `inheritance` | YAML only |

---

## 7. Frontend Integration

### What ships to the host app

Only `frontend/src/auth_usermanagement/` ships to your host. Everything else in `frontend/src/` is a demo sandbox.

| Ship to host? | Path | Purpose |
|:---:|------|---------|
| **YES** | `auth_usermanagement/` | Reusable auth module |
| NO | `App.jsx` | Demo shell with "FerrousLabs" branding |
| NO | `main.jsx` | Demo entry point |
| NO | `App.admin-routing.test.jsx` | Test for the demo shell |
| NO | `mockapp/` | Empty — prototyping placeholder |
| NO | `mockup/` | Empty — prototyping placeholder |

### Inside auth_usermanagement/ — what's style-free vs styled

**No styles (use directly, host provides all styling):**

| File | Purpose | Styling approach |
|------|---------|-----------------|
| `config.js` | Env-driven config | Pure logic |
| `constants/permissions.js` | Permission constants | Pure logic |
| `utils/errorHandling.js` | Error message helpers | Pure logic |
| `services/authApi.js` | Backend API client | Pure logic |
| `services/cognitoClient.js` | Cognito PKCE client | Pure logic |
| `services/customAuthApi.js` | Custom UI API client | Pure logic |
| `context/AuthProvider.jsx` | Auth state provider | No UI output |
| `hooks/*` | `useAuth`, `useTenant`, `useRole`, `useSpace`, `useCurrentUser` | No UI output |
| `components/ProtectedRoute.jsx` | Route guard | No styles — renders `children` or `fallback` |
| `components/TenantSwitcher.jsx` | Tenant dropdown | Accepts `className` prop, no inline styles |
| `components/RoleSelector.jsx` | Role dropdown | Accepts `className` prop, no inline styles |

**Have inline styles (functional but opinionated UI):**

| File | Purpose | Host strategy |
|------|---------|---------------|
| `components/CustomLoginForm.jsx` | Login form | Override with `className` prop or replace entirely |
| `components/CustomSignupForm.jsx` | Signup form | Override or replace |
| `components/ForgotPasswordForm.jsx` | Password reset form | Override or replace |
| `components/InviteSetPassword.jsx` | Invited user password set | Override or replace |
| `components/LoginForm.jsx` | Hosted UI login trigger | Minimal styles — minor override |
| `components/AcceptInvitation.jsx` | Invitation acceptance flow | Override or replace |
| `components/InviteUserModal.jsx` | Invite user modal | Override or replace |
| `components/UserList.jsx` | User management table | Override or replace |
| `components/SessionPanel.jsx` | Session management | Override or replace |
| `components/PlatformTenantPanel.jsx` | Platform admin tenant list | Override or replace |
| `components/ConfirmDialog.jsx` | Confirmation modal | Override or replace |
| `components/Toast.jsx` | Toast notifications | Override or replace |
| `pages/AdminDashboard.jsx` | Admin page layout | Host typically replaces entirely |

### Styling strategies

**Option A — Replace styled components (recommended for production apps):**

Use the hooks and services directly. Build your own UI components styled with your design system:

```jsx
import { useAuth, useTenant, useRole } from "./auth_usermanagement";
import { customLogin } from "./auth_usermanagement/services/customAuthApi";

function MyLoginForm() {
  // Your own styled form that calls customLogin()
}
```

Components you'd most likely keep as-is: `AuthProvider`, all hooks, all services, `ProtectedRoute`, `TenantSwitcher`, `RoleSelector`.

Components you'd most likely replace: `AdminDashboard`, `UserList`, `SessionPanel`, `CustomLoginForm`, `CustomSignupForm`, `Toast`.

**Option B — Override with className (quick start):**

Many components accept a `className` prop. Use CSS specificity to override inline styles:

```jsx
<CustomLoginForm
  className="my-login-form"
  onSuccess={handleSuccess}
  onSwitchToSignup={() => setView("signup")}
/>
```

```css
.my-login-form input { /* your styles */ }
.my-login-form button { /* your styles */ }
```

**Option C — Use as-is (prototyping only):**

The inline styles provide a functional, neutral UI suitable for prototyping. Not recommended for production.

### Minimal host setup

```jsx
// Host main.jsx
import { AuthProvider } from "./auth_usermanagement";

ReactDOM.createRoot(document.getElementById("root")).render(
  <BrowserRouter>
    <AuthProvider>
      <App />
    </AuthProvider>
  </BrowserRouter>
);
```

```jsx
// Host App.jsx — use hooks and services, build your own UI
import { useAuth, useTenant, ProtectedRoute } from "./auth_usermanagement";

function App() {
  const { isAuthenticated, logout } = useAuth();
  const { tenant, tenants, changeTenant } = useTenant();
  // ... your routes and layout
}
```

---

## Related Docs

- [Setup Guide](setup_guide.md) — step-by-step first-time integration
- [Agent Reference](agent_reference.md) — complete API and data model reference
- [Custom UI Guide](custom_ui_integration_guide.md) — building your own login forms
- [Cognito & SSO Guide](cognito_and_sso_guide.md) — AWS Cognito setup
- [Submodule Integration Guide](submodule_integration_guide.md) — Git submodule setup and multi-module migrations

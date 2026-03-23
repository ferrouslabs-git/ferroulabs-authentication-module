# User Type Guide

This guide is based on the current backend and frontend code.

## 1. User Types In This System

### Super Admin (Platform Level)
- Defined by `users.is_platform_admin = true`
- Can bypass tenant role checks in authorization guards
- Can use platform-only endpoints (for example user suspension and tenant suspension)

### Tenant Roles (Organization Level)
- owner
- admin
- member
- viewer

These are stored per-tenant in the memberships table and control tenant-scoped actions.

## 2. Where User Types Are Defined

### Global user flag (super admin)
File: `backend/app/auth_usermanagement/models/user.py`

```python
class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    cognito_sub = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255))
    is_platform_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True, nullable=False)
```

### Tenant role membership
File: `backend/app/auth_usermanagement/models/membership.py`

```python
class Membership(Base):
    __tablename__ = "memberships"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # owner, admin, member, viewer
    status = Column(String(20), default="active")
```

## 3. How Roles Are Assigned

### Tenant creator becomes owner automatically
File: `backend/app/auth_usermanagement/services/tenant_service.py`

```python
membership = Membership(
    user_id=user.id,
    tenant_id=tenant.id,
    role="owner",
    status="active"
)
```

File: `backend/app/auth_usermanagement/api/tenant_routes.py`

```python
return TenantCreateResponse(
    tenant_id=tenant.id,
    name=tenant.name,
    plan=tenant.plan,
    role="owner",
    message="Tenant created successfully",
)
```

## 4. How Permissions Are Enforced (Backend)

### Tenant guard hierarchy and platform-admin bypass
File: `backend/app/auth_usermanagement/security/guards.py`

```python
ROLE_HIERARCHY = {
    "owner": 4,
    "admin": 3,
    "member": 2,
    "viewer": 1,
}

def require_role(*allowed_roles: str) -> Callable:
    def role_checker(ctx: TenantContext = Depends(get_tenant_context)) -> TenantContext:
        if ctx.is_platform_admin:
            return ctx
        if ctx.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, ...)
        return ctx
```

### Tenant context loading from membership
File: `backend/app/auth_usermanagement/security/dependencies.py`

```python
membership = db.query(Membership).filter(
    Membership.user_id == current_user.id,
    Membership.tenant_id == tenant_id,
    Membership.status == "active",
).first()

if not membership and not current_user.is_platform_admin:
  raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: You are not a member of this tenant")

role = membership.role if membership else None
```

That means platform admins do not get a fake tenant role anymore. They stay platform admins via
`is_platform_admin = true`, and `role` is only populated when there is a real tenant membership.

### Platform-only endpoint check
File: `backend/app/auth_usermanagement/api/platform_user_routes.py`

```python
ensure_platform_admin(current_user, "suspend")
```

## 5. How Permissions Are Enforced (Frontend)

### Frontend permission map
File: `frontend/src/auth_usermanagement/constants/permissions.js`

```javascript
export const ROLE_PERMISSIONS = {
  owner: [
    PERMISSIONS.INVITE_USERS,
    PERMISSIONS.REMOVE_USERS,
    PERMISSIONS.SUSPEND_USERS,
    PERMISSIONS.UPDATE_USER_ROLES,
    PERMISSIONS.VIEW_USERS,
  ],
  admin: [
    PERMISSIONS.INVITE_USERS,
    PERMISSIONS.REMOVE_USERS,
    PERMISSIONS.SUSPEND_USERS,
    PERMISSIONS.UPDATE_USER_ROLES,
    PERMISSIONS.VIEW_USERS,
  ],
  member: [
    PERMISSIONS.VIEW_USERS,
  ],
}

export function checkPermission(currentUser, permission, tenantRole = null) {
  if (!currentUser) return false
  if (currentUser.is_platform_admin) return true
  return hasPermission(tenantRole || currentUser.role, permission)
}
```

### Frontend access to Admin page
File: `frontend/src/App.jsx`

```javascript
const canAccessAdmin = Boolean(user?.is_platform_admin || ['owner', 'admin'].includes(currentTenant?.role))
```

### Current User Management page is tenant-scoped
File: `frontend/src/auth_usermanagement/components/UserList.jsx`

```javascript
const res = await getTenantUsers(token, tenantId)
setUsers(res)
```

This means the table shows users in the selected tenant, not all users in the platform.

## 6. Effective Access Matrix

### Super Admin
- Global actions: yes
- Tenant actions: yes (bypass)
- Tenant role value when not a member: `null` / `None`
- Sees all users globally in current UI: no (current page is tenant-scoped)

### Owner
- Full tenant management in own tenant
- Cannot perform global platform actions unless also super admin

### Admin
- Tenant management in own tenant
- Limited role changes (backend enforces restrictions)

### Member
- Basic tenant participation
- No admin user-management actions

### Viewer
- Read-only style access
- No admin user-management actions

## 7. Important Practical Note

A user can be both at the same time:
- Super Admin globally (`is_platform_admin = true`)
- Owner/Admin/Member/Viewer in one or more tenants via memberships

So seeing "Role: owner" and "Super Admin" together is valid and expected.

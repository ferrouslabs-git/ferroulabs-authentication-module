# Auth & User Management — v3.0 Upgrade Implementation Plan

**Date:** 2026-03-20
**Source:** Upgrade Plan v3.0 (2026-03-19)
**Scope:** `backend/app/auth_usermanagement` + `frontend/src/auth_usermanagement`

---

## Ordering Principle

Tasks are ordered so that **earlier layers never need to be re-opened for later tasks**.

The dependency graph flows bottom-up:

```
Task 1  →  New tables + YAML loader + ScopeContext dataclass + config
           (pure additions — zero changes to existing runtime code)

Task 2  →  Membership schema migration + backfill
           (DB layer finalized — models match new schema)

Task 3  →  Guards rewrite to permission-based
           (guard layer finalized — routes can safely switch to it)

Task 4  →  Dependency path: get_scope_context replaces get_tenant_context
           (context layer finalized — all downstream code resolved)

Task 5  →  Middleware: accept X-Scope-Type / X-Scope-ID
           (request entry finalized — middleware done forever)

Task 6  →  Route handlers: switch guards + context references
           (API surface finalized — handlers never revisited)

Task 7  →  Services: invitation + user management + tenant service
           (business logic finalized)

Task 8  →  Invitation model extension + scoped invite flow
           (invitation layer finalized)

Task 9  →  Spaces: model + service + routes
           (new feature built on finished foundation)

Task 10 →  Frontend: hooks + API wrapper + components
           (consumes finished backend API)

Task 11 →  RLS migration + RLS tests
           (PostgreSQL layer — runs on final schema)

Task 12 →  Deprecation wrappers cleanup + final regression
           (housekeeping — everything else is stable)
```

Each task below includes:
- **What changes** — exact files and what happens to them
- **Verification gate** — command(s) to run before moving on
- **Why this order** — why it won't need re-visiting

---

## Task 1 — New Tables, YAML Loader, ScopeContext Dataclass

**Goal:** Add all new infrastructure without touching any existing file's runtime behavior.

### 1.1 Create `auth_config.yaml`

**New file:** `backend/auth_config.yaml`

The default configuration shipped with the module. Loaded at startup via `AUTH_CONFIG_PATH` env var.

```yaml
version: "3.0"

layers:
  account:
    enabled: true
    display_name: "Account"
  space:
    enabled: true
    display_name: "Space"

inheritance:
  account_member_space_access: none   # none | space_viewer | space_member

roles:
  platform:
    - name: super_admin
      display_name: "Super Admin"
      permissions:
        - platform:configure
        - accounts:manage
        - users:suspend

  account:
    - name: account_owner
      display_name: "Account Owner"
      permissions:
        - account:delete
        - account:read
        - spaces:create
        - members:manage
        - members:invite

    - name: account_admin
      display_name: "Account Admin"
      permissions:
        - account:read
        - spaces:create
        - members:invite

    - name: account_member
      display_name: "Account Member"
      permissions:
        - account:read

  space:
    - name: space_admin
      display_name: "Space Admin"
      permissions:
        - space:delete
        - space:configure
        - space:read
        - members:manage
        - members:invite
        - data:read
        - data:write

    - name: space_member
      display_name: "Space Member"
      permissions:
        - space:read
        - data:read
        - data:write

    - name: space_viewer
      display_name: "Space Viewer"
      permissions:
        - space:read
        - data:read
```

### 1.2 Create `models/role_definition.py`

**New file:** `backend/app/auth_usermanagement/models/role_definition.py`

```python
from sqlalchemy import Column, String, DateTime, Boolean
from datetime import datetime
from app.database import Base


class RoleDefinition(Base):
    __tablename__ = "role_definitions"

    name = Column(String(100), primary_key=True)
    layer = Column(String(20), nullable=False)          # platform | account | space
    display_name = Column(String(255), nullable=False)
    is_builtin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
```

### 1.3 Create `models/permission_grant.py`

**New file:** `backend/app/auth_usermanagement/models/permission_grant.py`

```python
from sqlalchemy import Column, String, ForeignKey, UniqueConstraint
from app.database import Base


class PermissionGrant(Base):
    __tablename__ = "permission_grants"

    role_name = Column(String(100), ForeignKey("role_definitions.name"), primary_key=True)
    permission = Column(String(200), primary_key=True, nullable=False)
    permission_type = Column(String(20), nullable=False)  # structural | product

    __table_args__ = (
        UniqueConstraint("role_name", "permission", name="unique_role_permission"),
    )
```

### 1.4 Create `models/space.py`

**New file:** `backend/app/auth_usermanagement/models/space.py`

```python
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from uuid import uuid4
from app.database import Base


class Space(Base):
    __tablename__ = "spaces"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)
    account_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True, index=True)
    status = Column(String(20), default="active")       # active | suspended
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    suspended_at = Column(DateTime, nullable=True)
```

### 1.5 Register new models in `models/__init__.py`

**Modify:** `backend/app/auth_usermanagement/models/__init__.py`

Add imports for `RoleDefinition`, `PermissionGrant`, `Space` and add them to `__all__`.

### 1.6 Create `security/scope_context.py`

**New file:** `backend/app/auth_usermanagement/security/scope_context.py`

```python
from dataclasses import dataclass, field
from uuid import UUID


@dataclass
class ScopeContext:
    user_id: UUID
    scope_type: str                            # platform | account | space
    scope_id: UUID | None                      # None for platform scope
    active_roles: list[str] = field(default_factory=list)
    resolved_permissions: set[str] = field(default_factory=set)
    is_super_admin: bool = False

    def has_permission(self, perm: str) -> bool:
        if self.is_super_admin:
            return True
        return perm in self.resolved_permissions

    def has_any_permission(self, perms: list[str]) -> bool:
        if self.is_super_admin:
            return True
        return bool(self.resolved_permissions.intersection(perms))

    def has_all_permissions(self, perms: list[str]) -> bool:
        if self.is_super_admin:
            return True
        return all(p in self.resolved_permissions for p in perms)
```

### 1.7 Create `services/auth_config_loader.py`

**New file:** `backend/app/auth_usermanagement/services/auth_config_loader.py`

Responsibilities:
1. Read `AUTH_CONFIG_PATH` (default `./auth_config.yaml`)
2. Parse YAML and validate:
   - `version` field == `"3.0"`
   - All role names unique across all layers
   - All permission strings match `[a-z_]+:[a-z_]+`
   - Structural permissions present on appropriate roles
   - Disabled layers have no roles defined
   - `inheritance.account_member_space_access` is `none`, `space_viewer`, `space_member`, or a valid space-layer role name
3. Upsert `role_definitions` rows
4. Upsert `permission_grants` rows
5. Build in-memory maps:
   - `permission_map: dict[str, set[str]]` — role_name → set of permissions
   - `inheritance_config: dict` — inheritance rules
   - `layer_config: dict` — which layers are enabled
   - `role_display_names: dict[str, str]` — role_name → display_name
6. Expose module-level singleton: `auth_config` (read-only after startup)

Structural permissions (fixed vocabulary — never change between deployments):
```python
STRUCTURAL_PERMISSIONS = frozenset({
    "platform:configure",
    "accounts:manage",
    "account:delete",
    "account:read",
    "spaces:create",
    "space:delete",
    "space:configure",
    "space:read",
    "members:manage",
    "members:invite",
    "users:suspend",
})
```

### 1.8 Add `AUTH_CONFIG_PATH` to module config

**Modify:** `backend/app/auth_usermanagement/config.py`

Add one field to `Settings`:
```python
auth_config_path: str = os.getenv("AUTH_CONFIG_PATH", "./auth_config.yaml")
```

### 1.9 Create migration 11 — `add_role_definitions_table`

Creates `role_definitions` and `permission_grants` tables.

### 1.10 Create migration 12 — `add_spaces_table`

Creates `spaces` table with `account_id` FK to `tenants.id`.

### Verification Gate

```bash
# 1. New models import without error
cd backend
python -c "from app.auth_usermanagement.models import RoleDefinition, PermissionGrant, Space; print('OK')"

# 2. ScopeContext imports and works
python -c "
from app.auth_usermanagement.security.scope_context import ScopeContext
from uuid import uuid4
ctx = ScopeContext(user_id=uuid4(), scope_type='account', scope_id=uuid4(),
                   active_roles=['account_owner'], resolved_permissions={'account:read', 'members:invite'})
assert ctx.has_permission('account:read')
assert not ctx.has_permission('space:delete')
print('ScopeContext OK')
"

# 3. Config loader validates + loads YAML
python -c "
from app.auth_usermanagement.services.auth_config_loader import load_and_validate_config
config = load_and_validate_config()
assert config['version'] == '3.0'
assert 'super_admin' in config['permission_map']
print('Config loader OK')
"

# 4. New test file passes
pytest -q tests/test_config_loader.py

# 5. ALL existing tests still pass (nothing was changed in existing runtime)
pytest -q tests
```

**Why this order:** Everything created here is additive. No existing file's behavior changes. The new ScopeContext, models, and config loader exist alongside the old code. Every subsequent task depends on these being in place.

---

## Task 2 — Membership Schema Migration + Backfill

**Goal:** Migrate the `memberships` table to the new schema. After this task, the Membership model in code matches the DB.

### 2.1 Create migration 13 — `replace_memberships_schema`

This migration:
1. Adds new columns to `memberships`: `role_name` (VARCHAR 100), `scope_type` (VARCHAR 20), `scope_id` (UUID nullable), `granted_by` (UUID FK → users.id, SET NULL)
2. Drops old unique constraint `unique_user_tenant`
3. Adds new unique constraint `unique_user_role_scope` on `(user_id, role_name, scope_type, scope_id)`

**Important:** Do NOT drop `tenant_id` or `role` columns yet. They will be used by migration 15 for backfill.

### 2.2 Create migration 14 — `extend_invitations_scope`

Adds to `invitations` table:
- `target_scope_type` (VARCHAR 20, nullable for now — will be required after backfill)
- `target_scope_id` (UUID, nullable)
- `target_role_name` (VARCHAR 100, nullable)

### 2.3 Create migration 15 — `backfill_memberships_scope`

Data migration:
```sql
UPDATE memberships
SET scope_type = 'account',
    scope_id = tenant_id,
    role_name = CASE role
        WHEN 'owner'  THEN 'account_owner'
        WHEN 'admin'  THEN 'account_admin'
        WHEN 'member' THEN 'account_member'
        WHEN 'viewer' THEN 'space_viewer'
    END
WHERE scope_type IS NULL;
```

Also backfill existing invitations:
```sql
UPDATE invitations
SET target_scope_type = 'account',
    target_scope_id = tenant_id,
    target_role_name = CASE role
        WHEN 'admin'  THEN 'account_admin'
        WHEN 'member' THEN 'account_member'
        WHEN 'viewer' THEN 'space_viewer'
    END
WHERE target_scope_type IS NULL;
```

### 2.4 Create migration 16 — `seed_role_definitions`

Reads `auth_config.yaml` and populates `role_definitions` + `permission_grants` tables.

### 2.5 Update `models/membership.py`

Replace the model to match the new schema:

```python
class Membership(Base):
    __tablename__ = "memberships"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, index=True)
    role_name = Column(String(100), nullable=False)
    scope_type = Column(String(20), nullable=False)     # platform | account | space
    scope_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    status = Column(String(20), default="active")       # active | removed | suspended
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    granted_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
                        nullable=True)

    # ──────────────────────────────────────────────────────────────────
    # DEPRECATED — kept for backward compatibility during migration.
    # TODO: Remove after 2026-05-20 (60 days from v3.0 release).
    # Drop via migration 18 (Task 12.1) once all code uses scope columns.
    # ──────────────────────────────────────────────────────────────────
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
                       nullable=True, index=True)
    role = Column(String(20), nullable=True)

    # Relationships
    user = relationship("User", back_populates="memberships", foreign_keys=[user_id])
    tenant = relationship("Tenant", back_populates="memberships")

    __table_args__ = (
        UniqueConstraint("user_id", "role_name", "scope_type", "scope_id",
                         name="unique_user_role_scope"),
    )
```

### 2.6 Update `models/invitation.py`

Add the three new columns (nullable — old invitations don't have them):

```python
# New scope columns (v3.0)
target_scope_type = Column(String(20), nullable=True)
target_scope_id = Column(UUID(as_uuid=True), nullable=True)
target_role_name = Column(String(100), nullable=True)
```

### Verification Gate

```bash
# 1. Migrations run cleanly on a fresh SQLite DB
cd backend
alembic upgrade head

# 2. Model imports work
python -c "
from app.auth_usermanagement.models.membership import Membership
assert hasattr(Membership, 'scope_type')
assert hasattr(Membership, 'role_name')
assert hasattr(Membership, 'scope_id')
print('Membership model OK')
"

# 3. Backfill verification: create old-style data, run backfill, verify new columns
# (This should be a dedicated test)
pytest -q tests/test_membership_backfill.py

# 4. Existing tests that create Membership with old args still work
#    (because tenant_id + role columns still exist as nullable)
pytest -q tests
```

**Why this order:** The migration adds new columns while keeping old ones. Existing code that writes `Membership(tenant_id=..., role=...)` still works because those columns still exist. We backfill new columns from old data. No runtime behavior changes yet.

---

## Task 3 — Permission-Based Guard System

**Goal:** Rewrite `guards.py` to check permissions instead of role names. Old guards become thin wrappers.

### 3.1 Rewrite `security/guards.py`

The file gets a full rewrite. Key changes:

1. **Remove** `ROLE_HIERARCHY` dict
2. **Remove** hardcoded `role_permissions` dict from `check_permission()`
3. **Add** `require_permission(perm)` — checks `ScopeContext.resolved_permissions`
4. **Add** `require_any_permission(perms)` — any one of the listed permissions
5. **Add** `require_all_permissions(perms)` — all listed permissions
6. **Add** `require_super_admin` — `is_super_admin` only
7. **Keep** `require_owner`, `require_admin`, `require_member`, `require_viewer` as **deprecated wrappers**:

```python
# ──────────────────────────────────────────────────────────────────────
# DEPRECATED — 60-day migration window.
# TODO: Remove after 2026-05-20 (60 days from v3.0 release 2026-03-20).
# After that date, delete _deprecated_guard and all four wrappers below.
# ──────────────────────────────────────────────────────────────────────
import warnings

def _deprecated_guard(permission: str, old_name: str):
    """Create a deprecated guard that wraps require_permission."""
    def wrapper(ctx: ScopeContext = Depends(get_scope_context)) -> ScopeContext:
        warnings.warn(
            f"{old_name} is deprecated. Use require_permission('{permission}') instead.",
            DeprecationWarning, stacklevel=2,
        )
        if not ctx.has_permission(permission) and not ctx.is_super_admin:
            raise HTTPException(status_code=403, detail=f"Access denied. Required permission: {permission}")
        return ctx
    return wrapper

require_owner = _deprecated_guard("account:delete", "require_owner")
require_admin = _deprecated_guard("members:manage", "require_admin")
require_member = _deprecated_guard("data:write", "require_member")
require_viewer = _deprecated_guard("data:read", "require_viewer")
```

8. **Keep** `require_role` and `require_min_role` as deprecated wrappers that emit warnings
9. **Update** `check_permission` to read from the config loader's permission map instead of the hardcoded dict

**Import change:** Guards now import `ScopeContext` instead of `TenantContext`, and `get_scope_context` instead of `get_tenant_context`.

### 3.2 Update `security/__init__.py`

Add new exports: `ScopeContext`, `get_scope_context`, `require_any_permission`, `require_all_permissions`, `require_super_admin`.

Keep all old exports working (they are deprecated wrappers).

### 3.3 Add `require_role` static analysis guardrail (early enforcement)

**Modify:** `tests/test_db_runtime_guardrails.py`

Add a new test now — not at the end — so that any `require_role(` call introduced in route files during Tasks 6–9 is caught immediately by CI:

```python
def test_no_require_role_in_route_files():
    """require_role() is deprecated. Route files must use require_permission()."""
    import glob, re
    route_files = glob.glob("app/auth_usermanagement/api/**/*.py", recursive=True)
    # Exclude the deprecated wrapper declaration in guards.py
    pattern = re.compile(r"\brequire_role\s*\(")
    violations = []
    for path in route_files:
        with open(path) as f:
            for i, line in enumerate(f, 1):
                if pattern.search(line):
                    violations.append(f"{path}:{i}")
    assert not violations, f"require_role() found in route files (use require_permission): {violations}"
```

This test will fail on existing code until Task 6 migrates all routes. **Mark it `@pytest.mark.skip(reason="Enable after Task 6 completes")` initially** and remove the skip in Task 6.

### 3.4 Create `tests/test_permission_guards.py`

Test cases:
- `require_permission("data:read")` passes when `resolved_permissions` contains `data:read`
- `require_permission("data:read")` raises 403 when permission missing
- `require_any_permission(["data:read", "data:write"])` passes if either present
- `require_all_permissions(["data:read", "data:write"])` fails if only one present
- `require_super_admin` passes for `is_super_admin=True`, fails otherwise
- Deprecated `require_admin` still passes for context with `members:manage` permission
- Deprecated `require_viewer` still passes for context with `data:read` permission
- Guards never check role name strings — only permissions

### Verification Gate

```bash
# 1. New guard tests pass
pytest -q tests/test_permission_guards.py

# 2. Old guard tests still pass (deprecated wrappers cover them)
pytest -q tests/test_guards.py

# 3. Static analysis guardrail exists (skipped until Task 6)
pytest -q tests/test_db_runtime_guardrails.py

# 4. Full regression
pytest -q tests
```

**Why this order:** Guards depend on ScopeContext (Task 1). After this task, the guard layer is finalized. The `require_role` guardrail is planted early so CI catches accidental use during Tasks 6–9. Route handlers (Task 6) will switch to these guards and never need to touch guards.py again.

---

## Task 4 — Dependency Path: `get_scope_context`

**Goal:** Create the new `get_scope_context` dependency alongside the existing `get_tenant_context`. The old one becomes a deprecated wrapper.

### 4.1 Add `get_scope_context` to `security/dependencies.py`

New function added to the existing file:

```python
from .scope_context import ScopeContext
from ..services.auth_config_loader import get_permission_map, get_inheritance_config

def get_scope_context(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ScopeContext:
    """
    Resolve ScopeContext from request headers.

    Header combinations:
    - X-Scope-Type + X-Scope-ID → new style
    - X-Tenant-ID (no X-Scope-Type) → legacy fallback: scope_type=account, scope_id=tenant_id

    Resolution steps:
    1. Parse scope_type + scope_id from headers
    2. Query all active memberships for user in this scope
    3. For each membership, look up permissions from in-memory permission map
    4. Apply inheritance expansion (e.g. account_owner → space_admin permissions)
    5. Union all permissions into resolved_permissions
    6. Set PostgreSQL RLS session variables
    """
```

Key implementation details:

**Header parsing with X-Tenant-ID fallback:**
```python
scope_type = request.headers.get("X-Scope-Type")
scope_id_str = request.headers.get("X-Scope-ID")

if not scope_type:
    # Legacy fallback: X-Tenant-ID → account scope
    tenant_id_str = request.headers.get("X-Tenant-ID")
    if tenant_id_str:
        scope_type = "account"
        scope_id_str = tenant_id_str
```

**Multi-membership query:**
```python
memberships = db.query(Membership).filter(
    Membership.user_id == current_user.id,
    Membership.scope_type == scope_type,
    Membership.scope_id == scope_id,
    Membership.status == "active",
).all()
```

**Inheritance expansion:**
```python
# If requesting space scope, check for parent account memberships
if scope_type == "space":
    space = db.query(Space).filter(Space.id == scope_id).first()
    if space and space.account_id:
        account_memberships = db.query(Membership).filter(
            Membership.user_id == current_user.id,
            Membership.scope_type == "account",
            Membership.scope_id == space.account_id,
            Membership.status == "active",
        ).all()
        # account_owner → inherits space_admin permissions
        # account_admin → inherits space_member permissions
        # account_member → inherits based on config
```

**RLS variables:**
```python
if bind is not None and bind.dialect.name == "postgresql":
    db.execute(text("SET LOCAL app.current_scope_type = :st"), {"st": scope_type})
    db.execute(text("SET LOCAL app.current_scope_id = :sid"), {"sid": str(scope_id)})
    db.execute(text("SET LOCAL app.is_super_admin = :sa"),
               {"sa": "true" if current_user.is_platform_admin else "false"})
```

### 4.2 Deprecate `get_tenant_context`

Keep `get_tenant_context` in `dependencies.py` but make it a thin wrapper around `get_scope_context` that returns a backward-compatible `TenantContext`:

```python
# TODO: Remove after 2026-05-20 (60 days from v3.0 release 2026-03-20).
def get_tenant_context(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TenantContext:
    """DEPRECATED: Use get_scope_context instead. Remove after 2026-05-20."""
    scope_ctx = get_scope_context(request, current_user, db)
    # Build backward-compatible TenantContext
    role = None
    if scope_ctx.active_roles:
        # Map back to legacy role name for compatibility
        role = _scope_role_to_legacy(scope_ctx.active_roles[0])
    return TenantContext(
        user_id=scope_ctx.user_id,
        tenant_id=scope_ctx.scope_id,
        role=role,
        is_platform_admin=scope_ctx.is_super_admin,
    )
```

### 4.3 Create `tests/test_scope_context.py`

Test cases:
- Account-scope request with `X-Scope-Type: account` + `X-Scope-ID` resolves correct permissions
- Legacy `X-Tenant-ID` header falls back to `scope_type=account`
- Space-scope request resolves permissions from space memberships
- Inheritance: `account_owner` gets `space_admin` permissions when requesting space scope
- Inheritance: `account_admin` gets `space_member` permissions
- Inheritance: `account_member` gets nothing by default (config: `none`)
- `super_admin` bypasses everything
- Missing scope headers → 400
- No membership in scope → 403 (non-admin)
- Platform admin can access any scope without membership
- RLS variables are set correctly (PostgreSQL-only test)

### Verification Gate

```bash
# 1. New test passes
pytest -q tests/test_scope_context.py

# 2. Old tenant context tests still pass (uses deprecated wrapper)
pytest -q tests/test_tenant_middleware.py tests/test_tenant_isolation_api.py

# 3. Full regression
pytest -q tests
```

**Why this order:** Depends on ScopeContext (Task 1), new membership schema (Task 2), and config loader (Task 1). The guard system (Task 3) imports `get_scope_context` from here. After this task, the dependency path is finalized. Route handlers and services can switch to `ScopeContext` without touching this file again.

---

## Task 5 — Middleware: Accept New Scope Headers

**Goal:** Update `TenantContextMiddleware` to accept `X-Scope-Type` + `X-Scope-ID` alongside `X-Tenant-ID`.

### 5.1 Modify `security/tenant_middleware.py`

Changes:
1. In `dispatch()`, check for `X-Scope-Type` + `X-Scope-ID` headers first
2. If not present, fall back to `X-Tenant-ID` (existing behavior)
3. Validate `X-Scope-Type` value: must be `account` or `space`
4. Validate `X-Scope-ID` UUID format
5. Store on `request.state`: `requested_scope_type` and `requested_scope_id`
6. Keep storing `requested_tenant_id` for backward compatibility
7. Add new skip routes:
   - `{prefix}/spaces` (space creation)
   - `{prefix}/spaces/my` (list user's spaces)
   - `{prefix}/config/roles` (public role definitions)
   - `{prefix}/config/permissions` (super admin only, but no scope needed)
   - `{prefix}/accounts` (account creation alias)

### Verification Gate

```bash
# 1. Middleware tests pass (old + new header styles)
pytest -q tests/test_tenant_middleware.py

# 2. Full regression
pytest -q tests
```

**Why this order:** Middleware depends on nothing from later tasks. After this, the request entry layer is finalized. All downstream code (dependencies, routes) can rely on scope headers being validated and stored.

---

## Task 6 — Route Handlers: Switch Guards + Context References

**Goal:** Update all API route files to use `ScopeContext` and permission-based guards.

### 6.1 Update `api/invitation_routes.py`

| Before | After |
|--------|-------|
| `from ..security import TenantContext, get_current_user, require_admin` | `from ..security import ScopeContext, get_current_user, get_scope_context, require_permission` |
| `ctx: TenantContext = Depends(require_admin)` | `ctx: ScopeContext = Depends(require_permission("members:invite"))` |
| `ctx.tenant_id` | `ctx.scope_id` |

### 6.2 Update `api/tenant_user_routes.py`

| Before | After |
|--------|-------|
| `from ..security import TenantContext, require_admin, require_member` | `from ..security import ScopeContext, require_permission` |
| `Depends(require_member)` | `Depends(require_permission("account:read"))` |
| `Depends(require_admin)` | `Depends(require_permission("members:manage"))` |
| `ctx.tenant_id` | `ctx.scope_id` |

### 6.3 Update `api/tenant_routes.py`

| Before | After |
|--------|-------|
| `from ..security import TenantContext, get_current_user, get_tenant_context` | `from ..security import ScopeContext, get_current_user, get_scope_context` |
| `ctx: TenantContext = Depends(get_tenant_context)` | `ctx: ScopeContext = Depends(get_scope_context)` |
| `ctx.is_owner()` | `ctx.has_permission("account:delete")` |
| `ctx.is_admin_or_owner()` | `ctx.has_permission("members:manage")` |
| `ctx.tenant_id` | `ctx.scope_id` |

### 6.4 Update `api/permission_demo_routes.py`

| Before | After |
|--------|-------|
| `require_admin` | `require_permission("members:manage")` |
| `require_owner` | `require_permission("account:delete")` |
| `require_member` | `require_permission("data:write")` |
| `require_viewer` | `require_permission("data:read")` |
| `check_permission(ctx, perm)` | `ctx.has_permission(perm)` |

### 6.5 Update `api/route_helpers.py`

| Before | After |
|--------|-------|
| `from ..security import TenantContext` | `from ..security import ScopeContext` |
| `def ensure_tenant_access(tenant_id, ctx: TenantContext)` | `def ensure_scope_access(scope_id, ctx: ScopeContext)` |
| `tenant_id != ctx.tenant_id and not ctx.is_platform_admin` | `scope_id != ctx.scope_id and not ctx.is_super_admin` |

Keep `ensure_tenant_access` as a deprecated alias pointing to `ensure_scope_access`.

### 6.6 Update `api/platform_user_routes.py`

Replace `is_platform_admin` checks with `require_super_admin` guard where applicable.

### 6.7 Update `api/platform_tenant_routes.py`

Same pattern — use `require_super_admin`.

### 6.8 Create `api/config_routes.py`

**New file:**

```python
router = APIRouter()

@router.get("/config/roles")
async def get_role_definitions(current_user: User = Depends(get_current_user)):
    """Return role definitions and display names for current deployment."""
    # Read from auth_config singleton
    ...

@router.get("/config/permissions")
async def get_permission_map(ctx: ScopeContext = Depends(require_super_admin)):
    """Return full permission map for current deployment."""
    ...
```

### 6.9 Register new routes in `api/__init__.py`

Add `config_routes` to the router.

### 6.10 Enable the `require_role` static analysis guardrail

In `tests/test_db_runtime_guardrails.py`, **remove the `@pytest.mark.skip`** from the `test_no_require_role_in_route_files` test added in Task 3.3. All route files have now been migrated to `require_permission()`, so the guardrail must pass.

### Verification Gate

```bash
# 1. Permission guard tests pass
pytest -q tests/test_permission_guards.py

# 2. Static analysis guardrail now enforced (no longer skipped)
pytest -q tests/test_db_runtime_guardrails.py

# 3. Updated route files work end-to-end
pytest -q tests/test_invitation_service.py tests/test_tenant_isolation_api.py
pytest -q tests/test_user_suspension_api.py tests/test_platform_tenant_api.py

# 4. Full regression
pytest -q tests
```

**Why this order:** Depends on guards (Task 3) and dependency path (Task 4). After this task, no route file needs to be touched again for the v3.0 migration. The `require_role` guardrail is now enforced — any subsequent task that accidentally uses the deprecated pattern will fail CI immediately.

---

## Task 7 — Services: Business Logic Updates

**Goal:** Update service functions to work with the new membership schema and permission map.

### 7.1 Update `services/invitation_service.py`

1. **Remove** `ROLE_LEVELS` dict
2. **Replace** `accept_invitation()` role-downgrade prevention: instead of comparing `ROLE_LEVELS[role]`, compare resolved permission sets from the config loader
3. **Update** `create_invitation()` to accept `target_scope_type`, `target_scope_id`, `target_role_name` parameters
4. **Update** `accept_invitation()` to create `Membership` with `scope_type`, `scope_id`, `role_name` instead of `tenant_id`, `role`
5. **Add** invite authority check:
   ```python
   def validate_invite_authority(inviter_permissions: set[str], target_role_name: str):
       target_permissions = get_permission_map()[target_role_name]
       if not target_permissions.issubset(inviter_permissions):
           raise PermissionError("Cannot invite to a role with permissions you do not hold")
   ```

### 7.2 Update `services/user_management_service.py`

1. **Update** `list_tenant_users()` → query by `scope_type="account"` + `scope_id` instead of `tenant_id`
2. **Update** `update_user_role()` → use `role_name` field, validate against permission map instead of hardcoded hierarchy
3. **Update** `remove_user_from_tenant()` → query by scope columns, check for last `account_owner` instead of last `"owner"`
4. **Update** `list_platform_users()` → include scope info in membership listings

### 7.3 Update `services/tenant_service.py`

1. **Update** `create_tenant()` → create membership with `scope_type="account"`, `scope_id=tenant.id`, `role_name="account_owner"` (in addition to old `tenant_id`/`role` during transition)

### 7.4 Update existing invitation/user-management tests

Update test fixtures to create memberships with new scope columns.

### Verification Gate

```bash
# 1. Invitation tests pass
pytest -q tests/test_invitation_service.py

# 2. User management tests pass
pytest -q tests/test_user_management_service.py

# 3. Full regression
pytest -q tests
```

**Why this order:** Depends on the new membership schema (Task 2) and config loader (Task 1). After this task, services never need revisiting.

---

## Task 8 — Scoped Invitation Flow

**Goal:** Extend the invitation system to support account-scope and space-scope invitations with invite authority validation.

### 8.1 Update invitation schemas

**Modify:** `schemas/invitation.py`

Add to `InvitationCreateRequest`:
- `target_scope_type: str | None = None` (default: `"account"` for backward compat)
- `target_scope_id: UUID | None = None` (default: uses scope from context)
- `target_role_name: str | None = None` (default: maps from `role` field for backward compat)

Add to response models: `target_scope_type`, `target_scope_id`, `target_role_name`.

### 8.2 Update invitation routes for scope-aware invites

The `POST /invite` endpoint now reads scope from the `ScopeContext` and validates invite authority:
1. Extract `target_role_name` from request body
2. Look up target role's permissions from config
3. Validate inviter holds at least those permissions → 403 if not
4. Create invitation with scope columns

### 8.3 Create `tests/test_scoped_invitations.py`

Test cases:
- Account-scope invite creates invitation with `target_scope_type=account`
- Space-scope invite creates invitation with `target_scope_type=space`
- Invite authority: `account_admin` cannot invite to `account_owner` role
- Invite authority: `account_owner` can invite to `account_admin` role
- Invite authority: `space_admin` can invite to `space_member`
- Accept invitation creates scoped membership
- Accept invitation in space scope creates `scope_type=space` membership
- Legacy invite (no scope fields) defaults to account scope

### Verification Gate

```bash
pytest -q tests/test_scoped_invitations.py
pytest -q tests/test_invitation_service.py
pytest -q tests
```

**Why this order:** Depends on services (Task 7) and route handlers (Task 6). After this task, the invitation system is finalized.

---

## Task 9 — Spaces: Model + Service + Routes

**Goal:** Build the complete space feature on top of the finished foundation.

### 9.1 Create `services/space_service.py`

Functions:
- `create_space(db, name, account_id, creator_user_id)` → creates space + `space_admin` membership for creator
- `list_user_spaces(db, user_id)` → all spaces where user has any active membership
- `list_account_spaces(db, account_id)` → spaces within an account
- `suspend_space(db, space_id)` / `unsuspend_space(db, space_id)`

### 9.2 Create `api/space_routes.py`

| Method | Path | Guard | Notes |
|--------|------|-------|-------|
| POST | `/spaces` | `require_permission("spaces:create")` | Creates space; `account_id` optional in body |
| GET | `/spaces/my` | `get_current_user` | List user's spaces |
| GET | `/accounts/{id}/spaces` | `require_permission("account:read")` | List spaces in account |
| POST | `/spaces/{id}/invite` | `require_permission("members:invite")` | Invite to space role |

### 9.3 Register space routes in `api/__init__.py`

### 9.4 Create `tests/test_space_service.py`

Test cases:
- Create space succeeds; creator gets `space_admin` membership
- Create space with `account_id` links space to account
- List user spaces returns only spaces with active membership
- List account spaces returns correct subset
- Suspend/unsuspend space lifecycle
- Non-member cannot access space (403)

### Verification Gate

```bash
pytest -q tests/test_space_service.py
pytest -q tests
```

**Why this order:** Spaces are a new feature built entirely on the finished scope system. Nothing in earlier tasks references spaces. After this task, all backend functionality is complete.

---

## Task 10 — Frontend Updates

**Goal:** Update the frontend to use scope-based headers, permission-based role checks, and new endpoints.

### 10.1 Update `services/authApi.js`

1. Add `scopeType` + `scopeId` parameters to tenant-scoped functions
2. Set `X-Scope-Type` and `X-Scope-ID` headers (keep `X-Tenant-ID` as fallback for 60-day window)
3. Add new API functions:
   - `getRoleDefinitions(token)` → `GET /config/roles`
   - `listMySpaces(token)` → `GET /spaces/my`
   - `getAccountSpaces(token, accountId)` → `GET /accounts/{id}/spaces`
   - `inviteToSpace(token, spaceId, data)` → `POST /spaces/{id}/invite`
   - `getAccountMembers(token, accountId)` → `GET /accounts/{id}/members`

### 10.2 Update `hooks/useRole.js`

**Before:**
```javascript
const ROLE_LEVELS = { owner: 4, admin: 3, member: 2, viewer: 1 };
const can = (minRole) => level >= ROLE_LEVELS[minRole];
```

**After:**
```javascript
// Permissions loaded from backend via GET /config/roles or from ScopeContext
export function useRole() {
  const { scopeContext } = useAuth();
  const permissions = scopeContext?.resolved_permissions || [];

  const can = (permission) => permissions.includes(permission);

  return {
    permissions,
    can,
    isOwner: can("account:delete"),
    isAdminOrOwner: can("members:manage"),
  };
}
```

### 10.3 Update `context/AuthProvider.jsx`

1. After login, fetch role definitions from `GET /config/roles` and cache them
2. Store `scopeContext` (including `resolved_permissions`) when scope headers are sent
3. Add `currentSpace` / `changeSpace(spaceId)` alongside existing `tenantId` / `changeTenant()`

### 10.4 Update `components/UserManagementPanel.jsx`

Role dropdown options fetched from `GET /config/roles` instead of hardcoded `["owner", "admin", "member", "viewer"]`.

### 10.5 Update `components/InvitationModal.jsx`

Role selection dropdown populated from config roles. When inviting to a space, show space-layer roles. When inviting to an account, show account-layer roles.

### 10.6 Add new hooks: `useSpace.js`

```javascript
export function useSpace() {
  const { spaces, currentSpace, changeSpace } = useAuth();
  return { spaces, space: currentSpace, changeSpace };
}
```

### 10.7 Create `tests/test_useRole_permissions.test.jsx`

The `can()` function is changing from a role-level numeric comparison to a permission string lookup. This semantic change must have at least one integration test:

```jsx
// Test cases:
// 1. can("data:read") returns true when resolved_permissions includes "data:read"
// 2. can("account:delete") returns false when permission is absent
// 3. isOwner is true only when "account:delete" is in permissions
// 4. isAdminOrOwner is true when "members:manage" is in permissions
// 5. Empty permissions array → all checks return false
// 6. Permissions fetched from GET /config/roles are reflected in can()
```

### Verification Gate

```bash
# 1. Frontend builds without errors
cd frontend
npm run build

# 2. Existing frontend tests pass
npm test

# 3. New permission hook test passes
npm test -- --testPathPattern=test_useRole_permissions

# 4. Manual verification:
#    - Login flow works with new scope headers
#    - Tenant/account selection sends X-Scope-Type + X-Scope-ID
#    - Role dropdown shows YAML-defined roles
#    - can() checks permission strings correctly
```

**Why this order:** Frontend consumes the finished backend API. All endpoints and response shapes are finalized. This task never requires backend changes.

---

## Task 11 — RLS Migration + RLS Tests

**Goal:** Update PostgreSQL RLS policies for the new scope-based session variables.

### 11.1 Create migration 17 — `update_rls_for_scope`

1. Drop existing RLS policies on `memberships` and `invitations`
2. Create new policies using **both** `app.current_scope_type` **and** `app.current_scope_id`:
   ```sql
   CREATE POLICY memberships_scope_isolation ON memberships
   USING (
       (
           scope_type = current_setting('app.current_scope_type', true)
           AND scope_id::text = current_setting('app.current_scope_id', true)
       )
       OR current_setting('app.is_super_admin', true) = 'true'
   );
   ```
   **Why both columns?** Filtering by `scope_id` alone is technically safe with uuid4 (collision probability ≈ 0), but including `scope_type` makes the policy self-documenting and prevents any theoretical cross-scope leak if UUIDs were ever reused or externally assigned.
3. Add RLS policy on `invitations`:
   ```sql
   CREATE POLICY invitations_scope_isolation ON invitations
   USING (
       (
           target_scope_type = current_setting('app.current_scope_type', true)
           AND target_scope_id::text = current_setting('app.current_scope_id', true)
       )
       OR current_setting('app.is_super_admin', true) = 'true'
   );
   ```
4. Add RLS policy on `spaces` table:
   ```sql
   CREATE POLICY spaces_account_isolation ON spaces
   USING (
       account_id::text = current_setting('app.current_scope_id', true)
       OR current_setting('app.is_super_admin', true) = 'true'
   );
   ```
   Note: `spaces` uses `account_id` (not `scope_id`) because space rows are owned by an account, not by a scope generically.
5. Maintain `FORCE ROW LEVEL SECURITY` on all tables

### 11.2 Update `tests/test_row_level_security.py`

1. Update RLS test fixtures to set `app.current_scope_type` + `app.current_scope_id` variables
2. Add tests for:
   - Space-scope isolation: memberships in space_a not visible with space_b context
   - Account-scope isolation: same pattern
   - `is_super_admin = 'true'` bypasses all scope restrictions
   - Default deny: no scope variables set → 0 rows

### Verification Gate

```bash
# MUST run with PostgreSQL — SQLite does not support RLS
RUN_POSTGRES_RLS_TESTS=1 DATABASE_URL=<postgres-url> pytest -q tests/test_row_level_security.py
```

**Why this order:** RLS policies operate on the final schema and final session variable names. Running this earlier would mean redoing it if schema or variable names changed. Now everything is locked.

---

## Task 12 — Cleanup + Final Regression

**Goal:** Remove deprecated code that is past its migration window. Run full regression.

### 12.1 Remove deprecated columns from membership model

Create migration 18 — `drop_legacy_membership_columns`:
- Drop `memberships.tenant_id` column
- Drop `memberships.role` column

Update `models/membership.py`: remove the deprecated column definitions.

### 12.2 Remove deprecated invitation columns

Eventually (after all old invitations expire): drop `invitations.role` column, make `target_scope_type` / `target_scope_id` / `target_role_name` NOT NULL.

**Note:** This step can be deferred until the 60-day migration window closes. Do not rush it.

### 12.3 Verify `require_role` static analysis guardrail is active

The guardrail was added in Task 3.3 (skipped) and enabled in Task 6.10. Confirm it is still passing and not accidentally skipped.

### 12.4 Final regression

```bash
# All existing gates
pytest -q tests/test_db_ownership_boundary.py tests/test_db_runtime_guardrails.py
pytest -q tests/test_main_auth_prefix.py tests/test_tenant_middleware.py tests/test_rate_limit_middleware.py
pytest -q tests/test_session_service.py tests/test_cookie_token_endpoints.py tests/test_audit_service.py

# New gates
pytest -q tests/test_config_loader.py
pytest -q tests/test_scope_context.py tests/test_permission_guards.py
pytest -q tests/test_space_service.py tests/test_scoped_invitations.py

# Full regression
pytest -q tests

# RLS (PostgreSQL)
RUN_POSTGRES_RLS_TESTS=1 DATABASE_URL=<postgres-url> pytest -q tests/test_row_level_security.py
```

---

## Summary — Task Dependency Map

```
Task 1   New tables + YAML loader + ScopeContext         ← no dependencies
Task 2   Membership schema migration + backfill          ← no dependencies
Task 3   Permission-based guard system                   ← Task 1
Task 4   get_scope_context dependency path               ← Tasks 1, 2
Task 5   Middleware: scope headers                       ← no dependencies (can parallel with 3-4)
Task 6   Route handlers switch to new system             ← Tasks 3, 4
Task 7   Service layer updates                           ← Tasks 1, 2
Task 8   Scoped invitation flow                          ← Tasks 6, 7
Task 9   Spaces feature                                  ← Tasks 6, 7
Task 10  Frontend updates                                ← Tasks 6, 9
Task 11  RLS migration                                   ← Tasks 2, 4
Task 12  Cleanup + final regression                      ← ALL
```

### Parallel Tracks

```
Track A (can start immediately):    Task 1 → Task 3 → Task 6
Track B (can start immediately):    Task 2 → Task 4 → Task 7 → Task 8
Track C (can start after Track A):  Task 5
Track D (can start after Tracks A+B): Task 9 → Task 10
Track E (can start after Track B):  Task 11
Final:                              Task 12
```

---

## What Does Not Change (Carried Forward Unchanged)

- `services/session_service.py` — session lifecycle
- `services/cookie_token_service.py` — HttpOnly refresh cookies, CSRF
- `services/audit_service.py` — best-effort audit logging
- `services/rate_limiter_service.py` — rate limiting
- `security/jwt_verifier.py` — RS256, Cognito JWKS, 7-step validation
- `security/security_headers_middleware.py` — response headers
- `services/email_service.py` — SES invitation sending
- `models/session.py` — session model
- `models/refresh_token.py` — refresh token store
- `models/audit_event.py` — audit events
- `models/user.py` — user model
- `models/tenant.py` — tenant model (kept as account-layer entity)
- All existing release gates 1–3 (DB ownership, middleware structure, session/cookie/audit)
- Frontend PKCE flow (cognitoClient.js)

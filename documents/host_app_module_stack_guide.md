# Host App Module Stack Guide

> Recommended host app folder structure and ownership boundaries for dropping in reusable modules such as `auth_usermanagement`, `billing`, and `llm`.

Last updated: 2026-04-03

---

## Goal

Use one host app skeleton that can integrate multiple reusable modules without import conflicts, duplicate database runtimes, or migration drift.

This guide defines:

1. Host folder structure for backend and frontend
2. Ownership boundaries (host vs module)
3. Multi-module migration layout
4. Runtime wiring conventions
5. Integration checklist for each new module

---

## 1. Recommended Host Folder Structure

```text
host-app/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── database.py                    # host-owned runtime: engine/session/Base/get_db
│   │   ├── config.py                      # host-owned root settings
│   │   ├── main.py                        # host-owned FastAPI app wiring
│   │   ├── auth_usermanagement/           # symlink or copied module package
│   │   ├── billing/                       # symlink or copied module package
│   │   ├── llm/                           # symlink or copied module package
│   │   ├── models/                        # host domain tables (extension + app-specific)
│   │   ├── services/                      # host orchestration services across modules
│   │   ├── api/                           # host-only routes (outside module packages)
│   │   └── integrations/                  # external provider adapters owned by host
│   ├── alembic/
│   │   ├── env.py                         # host migration runner
│   │   └── versions/                      # host-owned migrations
│   ├── alembic.ini                        # host Alembic config with version_locations
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── auth_usermanagement/           # symlink or copied module frontend package
│   │   ├── billing/                       # symlink or copied module frontend package
│   │   ├── llm/                           # symlink or copied module frontend package
│   │   ├── app/                           # host app shell, routes, layouts, theme
│   │   └── shared/                        # host shared UI and utilities
│   └── package.json
├── vendor/                                # optional: git submodules live here
│   ├── ferrouslabs-auth-system/
│   ├── ferrouslabs-billing-module/
│   └── ferrouslabs-llm-module/
├── .env
└── docker-compose.yml
```

### Important path rule

If modules use `from ..database import ...` internally, they must be mounted as direct packages under `backend/app/` (for example `backend/app/auth_usermanagement/`).

Do not nest them under `backend/app/modules/` unless the module code is explicitly built for that package depth.

---

## 2. Ownership Contract (Host vs Module)

| Concern | Host owns | Module owns |
|---|---|---|
| DB runtime | `database.py` (`engine`, `SessionLocal`, `Base`, `get_db`) | Bridge file only (`from app.database import ...`) |
| Root settings | `DATABASE_URL`, CORS, environment composition | Module-specific settings only (`*_API_PREFIX`, provider keys) |
| FastAPI app | App creation, middleware registration order, router mounting | Router definitions and module dependencies |
| Migrations | Alembic runner execution, `version_locations`, deployment pipeline | Module migration files in module repo |
| Domain data | Host domain tables and extension tables | Module core identity/access tables |
| Cross-module orchestration | Composite workflows and service hooks | Module-local business logic |

Non-negotiable rule: no module may create its own `create_engine()`, `sessionmaker()`, or `declarative_base()` when integrated into a host app.

---

## 3. Multi-Module Alembic Layout

Configure host `backend/alembic.ini` with all migration locations:

```ini
[alembic]
script_location = %(here)s/alembic
version_locations =
    %(here)s/alembic/versions
    %(here)s/vendor/ferrouslabs-auth-system/backend/alembic/versions
    %(here)s/vendor/ferrouslabs-billing-module/backend/alembic/versions
    %(here)s/vendor/ferrouslabs-llm-module/backend/alembic/versions
```

In `backend/alembic/env.py`:

- Keep host `Base` as `target_metadata`
- Import host models and all module models so autogenerate sees full metadata
- Enable multi-path parsing (for example `version_path_separator="space"` if needed by your Alembic config format)

When host migrations depend on a module revision, use `depends_on` in the host migration.

---

## 4. Runtime Wiring Conventions

In host `backend/app/main.py`:

1. Build app in host
2. Register host-level middleware (for example CORS)
3. Register module middleware in explicit order
4. Mount each module router with its module prefix from module settings
5. Mount host routes last or by explicit precedence strategy

Example router wiring pattern:

```python
from app.auth_usermanagement.api import router as auth_router
from app.billing.api import router as billing_router
from app.llm.api import router as llm_router

from app.auth_usermanagement.config import get_settings as get_auth_settings
from app.billing.config import get_settings as get_billing_settings
from app.llm.config import get_settings as get_llm_settings

auth_settings = get_auth_settings()
billing_settings = get_billing_settings()
llm_settings = get_llm_settings()

app.include_router(auth_router, prefix=auth_settings.auth_api_prefix, tags=["auth"])
app.include_router(billing_router, prefix=billing_settings.api_prefix, tags=["billing"])
app.include_router(llm_router, prefix=llm_settings.api_prefix, tags=["llm"])
```

---

## 5. Host Domain Modeling Pattern

Keep host-specific fields in host-owned extension tables, not in module models.

Examples:

- `user_profiles` (FK to module `users.id`)
- `tenant_profiles` (FK to module `tenants.id`)
- `billing_references` (FK to module `users.id`, billing provider identifiers)
- `llm_usage_ledger` (FK to module `users.id` and host tenant/space scope)

Use UUID foreign keys to module tables and keep tenant-scoped data explicitly filtered by `tenant_id` in services.

---

## 6. Frontend Composition Pattern

Your host frontend remains the shell. Module frontend packages are imported into host routes and pages.

Recommended:

- Keep module code in `frontend/src/<module_name>/`
- Keep host shell and navigation in `frontend/src/app/`
- Keep cross-module UI primitives in `frontend/src/shared/`

For production apps, use module hooks/services/context and replace opinionated module UI components with host-styled components where needed.

---

## 7. Adding Host-Owned Business Modules

Reusable drop-in modules (`auth_usermanagement`, `billing`, `llm`) should stay isolated. Your host app business logic should live in host-owned modules that depend on reusable modules through stable APIs, dependencies, and services.

### When to use one host module vs many

- Use one host module when your business domain is small and changes are tightly coupled.
- Split into multiple host modules when domains have different lifecycles, teams, or release cadence.

### Recommended host business module layout

```text
backend/app/
├── modules/
│   ├── __init__.py
│   ├── core_domain/                # optional single-module setup
│   │   ├── api/
│   │   ├── models/
│   │   ├── schemas/
│   │   └── services/
│   ├── onboarding/                 # multi-module setup example
│   │   ├── api/
│   │   ├── models/
│   │   ├── schemas/
│   │   └── services/
│   ├── referrals/
│   │   ├── api/
│   │   ├── models/
│   │   ├── schemas/
│   │   └── services/
│   └── analytics/
│       ├── api/
│       ├── models/
│       ├── schemas/
│       └── services/
```

Notes:

- Keep reusable module packages at `backend/app/<module_name>/` and host business modules under `backend/app/modules/`.
- Host business modules may reference reusable module tables with UUID FKs (for example `users.id`, `tenants.id`, `spaces.id`).
- Host business modules should not import internals across reusable modules unless no stable API exists.
- Cross-module orchestration belongs in host services, not in reusable module packages.

### Integration pattern for a new host business module

1. Create `backend/app/modules/<host_module>/` with `api`, `models`, `schemas`, and `services`.
2. Add tables to host migrations in `backend/alembic/versions/`.
3. Add router composition file for the host module and include it from host `main.py`.
4. Scope data with `tenant_id` and/or `space_id` where relevant.
5. Use host `get_db` dependency and never create sessions in services.
6. Add tests for permission, scope isolation, and integration seams with auth/billing/llm.

### Example host router mounting

```python
from app.modules.onboarding.api import router as onboarding_router
from app.modules.referrals.api import router as referrals_router

app.include_router(onboarding_router, prefix="/onboarding", tags=["onboarding"])
app.include_router(referrals_router, prefix="/referrals", tags=["referrals"])
```

### Frontend pairing for host business modules

If a host business module has UI, mirror it in host frontend code:

```text
frontend/src/app/modules/
├── onboarding/
│   ├── pages/
│   ├── components/
│   └── services/
└── referrals/
    ├── pages/
    ├── components/
    └── services/
```

This keeps host business UX distinct from reusable drop-in module UX.

### Copy-ready example: `onboarding` host business module

Use this as a starter for any host-owned module.

```text
backend/app/modules/onboarding/
├── __init__.py
├── api/
│   ├── __init__.py
│   └── routes.py
├── models/
│   ├── __init__.py
│   └── onboarding_progress.py
├── schemas/
│   ├── __init__.py
│   └── onboarding.py
└── services/
    ├── __init__.py
    └── onboarding_service.py
```

`backend/app/modules/onboarding/models/onboarding_progress.py`

```python
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class OnboardingProgress(Base):
    __tablename__ = "onboarding_progress"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    step_key = Column(String(100), nullable=False)
    completed = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)
```

`backend/app/modules/onboarding/schemas/onboarding.py`

```python
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class OnboardingStepUpsertRequest(BaseModel):
    step_key: str
    completed: bool


class OnboardingStepResponse(BaseModel):
    id: UUID
    user_id: UUID
    tenant_id: UUID
    step_key: str
    completed: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
```

`backend/app/modules/onboarding/services/onboarding_service.py`

```python
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.onboarding.models.onboarding_progress import OnboardingProgress


def upsert_step(
    db: Session,  # or AsyncSession if using async SQLAlchemy
    *,
    user_id: UUID,
    tenant_id: UUID,
    step_key: str,
    completed: bool,
) -> OnboardingProgress:
    """Upsert onboarding step. Adapt to async if needed."""
    row = (
        db.query(OnboardingProgress)
        .filter(
            OnboardingProgress.user_id == user_id,
            OnboardingProgress.tenant_id == tenant_id,
            OnboardingProgress.step_key == step_key,
        )
        .first()
    )

    if row is None:
        row = OnboardingProgress(
            user_id=user_id,
            tenant_id=tenant_id,
            step_key=step_key,
            completed=completed,
        )
        db.add(row)
    else:
        row.completed = completed

    db.commit()
    db.refresh(row)
    return row
```

`backend/app/modules/onboarding/api/routes.py`

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth_usermanagement.security import require_permission
from app.database import get_db
from app.modules.onboarding.schemas.onboarding import (
    OnboardingStepResponse,
    OnboardingStepUpsertRequest,
)
from app.modules.onboarding.services.onboarding_service import upsert_step

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.put("/steps", response_model=OnboardingStepResponse)
def upsert_onboarding_step(
    payload: OnboardingStepUpsertRequest,
    ctx=Depends(require_permission("data:write")),
    db: Session = Depends(get_db),
):
    return upsert_step(
        db,
        user_id=ctx.user_id,
        tenant_id=ctx.scope_id,
        step_key=payload.step_key,
        completed=payload.completed,
    )
```

`backend/app/modules/onboarding/api/__init__.py`

```python
from fastapi import APIRouter

from .routes import router as onboarding_routes

router = APIRouter()
router.include_router(onboarding_routes)
```

Host app wiring in `backend/app/main.py`:

```python
from app.modules.onboarding.api import router as onboarding_router

app.include_router(onboarding_router)
```

Migration note:

- Create this table in host migrations (`backend/alembic/versions/`), not in reusable module migration folders.

---

## 8. Per-Module Drop-In Checklist

When adding a new module (`billing`, `llm`, etc.), verify:

1. Backend package is mounted at `backend/app/<module_name>/`
2. Frontend package is mounted at `frontend/src/<module_name>/`
3. Module bridge file is the only file importing from `app.database`
4. Module router is mounted in host `main.py`
5. Module settings are namespaced (`BILLING_*`, `LLM_*`, etc.)
6. Module migrations are added to `version_locations`
7. Host orchestration hooks are implemented in host `services/`
8. Guardrail tests exist for DB ownership and import boundaries
9. PostgreSQL integration tests run for tenant and permission-sensitive paths

---

## 9. Suggested Host Conventions

- Module IDs: `auth`, `billing`, `llm`
- API prefixes: `/auth`, `/billing`, `/llm`
- Env var prefixes: `AUTH_`, `BILLING_`, `LLM_`
- Logging fields: include `module`, `tenant_id`, `user_id`, `request_id`
- Cross-module calls: orchestrate in host services, avoid module-to-module hard imports when possible

---

## 10. Practical Considerations

### 10.1 Frontend Package Dependency Management

Your modules live in `frontend/src/<module_name>/`. When you version modules independently, pin them explicitly.

**If using Git submodules:**

Each submodule has a specific commit hash pinned in `.gitmodules`. This is your version lock. When you want to upgrade a module, update the submodule commit, test the integration, and commit the change:

```bash
cd vendor/ferrouslabs-billing-module
git checkout main
git pull
cd ../..
git add vendor/ferrouslabs-billing-module
git commit -m "bump billing module to latest"
```

**If copying module files:**

Track module source and version in a manifest file at root:

```yaml
# modules-manifest.yaml (example)
modules:
  auth_usermanagement:
    source: https://github.com/ferrouslabs/ferrouslabs-auth-system
    version: v2.1.3
    lastUpdated: 2026-04-03
  billing:
    source: https://github.com/ferrouslabs/ferrouslabs-billing-module
    version: v1.0.2
    lastUpdated: 2026-03-15
```

Document breaking changes (UI API changes) in module release notes and test integration before merging.

### 10.2 Circular Dependency Avoidance

Your architecture assumes:
- `billing` never imports from `llm` directly
- `auth_usermanagement` never imports from `billing` directly
- Cross-module workflows live in host services only

This prevents hidden coupling. Add a guardrail test to enforce it:

```python
# tests/test_module_import_boundaries.py
import re
from pathlib import Path

def test_no_cross_module_imports():
    """Ensure modules don't import each other, only from host."""
    modules = ["auth_usermanagement", "billing", "llm"]
    app_dir = Path(__file__).resolve().parents[1] / "app"
    
    for module_name in modules:
        module_path = app_dir / module_name
        if not module_path.exists():
            continue
        
        violations = []
        for py_file in module_path.rglob("*.py"):
            if "__pycache__" in py_file.parts:
                continue
            source = py_file.read_text(encoding="utf-8")
            
            # Check for imports from other reusable modules
            for other_module in modules:
                if other_module == module_name:
                    continue
                pattern = rf"from\s+app\.{other_module}\s+import|import\s+app\.{other_module}"
                if re.search(pattern, source):
                    violations.append(f"{py_file}: imports from {other_module}")
        
        assert not violations, f"Cross-module imports in {module_name}:\n" + "\n".join(violations)
```

### 10.3 Service Layer Orchestration & Contracts

Host services orchestrate cross-module workflows. Define explicit **service contracts** per module so host code depends on stable APIs, not implementation details.

**Example: Service contract for `billing` module**

```python
# app/modules/entitlements_orchestration/billing_contract.py
"""
Service contract for billing module.
Host orchestrators may call these functions safely.
Contract version: 1.0.0
Last updated: 2026-04-03
"""
from typing import Callable
from uuid import UUID
from sqlalchemy.orm import Session
from pydantic import BaseModel


class EntitlementInfo(BaseModel):
    user_id: UUID
    module_id: str
    granted_at: str


# Stable API functions
def get_user_entitlements(db: Session, user_id: UUID) -> list[EntitlementInfo]:
    # For async hosts: use AsyncSession instead, mark function async
    """
    Get all active entitlements for a user.
    
    Returns: List of EntitlementInfo (empty if none)
    Idempotent: Yes
    Side effects: None (read-only)
    """
    from app.billing.services.entitlement_service import get_entitlements
    return get_entitlements(db, user_id=user_id)


def has_entitlement(db: Session, user_id: UUID, module_id: str) -> bool:
    # For async hosts: use AsyncSession instead, mark function async
    """
    Check if user has active entitlement for a module.
    
    Returns: True or False
    Idempotent: Yes
    Side effects: None (read-only)
    """
    from app.billing.services.entitlement_service import check_entitlement
    return check_entitlement(db, user_id=user_id, module_id=module_id)
```

Host orchestrators import only from the contract file, not directly from module services:

```python
# app/modules/llm_control/services.py
from app.modules.entitlements_orchestration.billing_contract import has_entitlement

def call_llm_model(db: Session, user_id: UUID, ...):
    if not has_entitlement(db, user_id, "llm"):
        raise PermissionError("User does not have LLM entitlement")
    # proceed with LLM call
```

**Async consideration:** If your host uses `AsyncSession` and async SQLAlchemy, adapt all service functions to:
- Take `db: AsyncSession` instead of `db: Session`
- Mark function as `async`
- Use `await db.execute(...)` instead of `db.query(...)`

Example async adaptation:

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

async def has_entitlement(db: AsyncSession, user_id: UUID, module_id: str) -> bool:
    """Async version of entitlement check."""
    result = await db.execute(
        select(Entitlement).where(
            (Entitlement.user_id == user_id) & (Entitlement.module_id == module_id)
        )
    )
    return result.scalar_one_or_none() is not None
```

The billing module uses `AsyncSession`, so if your host is also async, the module's actual service functions are already in the right pattern—just import and call them. Host adapters (contracts) should match your host's sync/async choice.

### 10.4 Test Coverage Strategy for Multi-Module Apps

Organize tests by scope:

**Module-level tests (in each module repo):**
- Unit tests (SQLite in-memory, modules in isolation)
- Integration tests (against test PostgreSQL)
- Guardrail tests (DB ownership, import boundaries)
- Run: `pytest -q tests`

**Host integration tests (in host repo):**
- Cross-module workflows (auth → billing → entitlement)
- Tenant isolation across module boundaries
- Permission checks spanning modules
- Run: `pytest -q tests/test_cross_module_integration.py`

**Example: host cross-module integration test**

```python
# tests/test_cross_module_integration.py
def test_user_creation_triggers_entitlement_assignment(db_session):
    """Auth user creation should auto-grant starter entitlements via billing."""
    from app.auth_usermanagement.services.user_service import create_user_from_cognito
    from app.billing.services.entitlement_service import get_entitlements
    
    user = create_user_from_cognito(
        db_session,
        cognito_sub="test-sub",
        email="test@example.com",
        tenant_id=some_tenant_id,
    )
    
    # Billing module should have auto-granted starter entitlements
    entitlements = get_entitlements(db_session, user_id=user.id)
    assert len(entitlements) > 0
    assert any(e.module_id == "llm" for e in entitlements)


def test_tenant_isolation_across_auth_and_billing(db_session):
    """User from tenant A should not see billing data from tenant B."""
    tenant_a = create_tenant(db_session, name="Tenant A")
    tenant_b = create_tenant(db_session, name="Tenant B")
    
    user_a = create_user_from_cognito(db_session, tenant_id=tenant_a.id, ...)
    user_b = create_user_from_cognito(db_session, tenant_id=tenant_b.id, ...)
    
    # User A's entitlements should not include User B's
    ent_a = get_entitlements(db_session, user_id=user_a.id)
    ent_b = get_entitlements(db_session, user_id=user_b.id)
    
    assert not any(e.user_id == user_b.id for e in ent_a)
```

### 10.5 Guardrail Tests Reference

Each module must ship guardrail tests. Reference pattern:

```python
# tests/test_db_runtime_guardrails.py (in module repo)
"""Enforce DB ownership and import boundary rules."""

def test_module_does_not_create_db_runtime():
    """No create_engine, sessionmaker, or declarative_base in module."""
    # [implemented per module_blueprint.md]

def test_no_direct_host_imports_outside_bridge():
    """Only database.py may import from app.database."""
    # [implemented per module_blueprint.md]

def test_no_cross_module_imports():
    """This module doesn't import from other reusable modules."""
    # [new — see section 10.2]
```

When adding a new module, verify it includes these tests before integration.

---

## 11. Alignment with ferrouslabs-billing

Your guide describes exactly what the billing module was built for:

| Feature | Your Guide | Billing Module |
|---------|-----------|----------------|
| DB bridge pattern | Module imports only via bridge file | ✅ `billing/database.py` (sole absolute import) |
| Import boundary | Relative imports (`from ..database`), one absolute | ✅ All files use `from ..database` except bridge |
| Service pattern | `db: Session` first arg, no session creation | ✅ All services receive `db: AsyncSession` |
| Router mounting | Host mounts with prefix from settings | ✅ Router in `api/__init__.py`, prefix from config |
| Migrations | Module migration files in `versions/` | ✅ 5 migration files ready to execute |
| Tests | Guardrail + unit + integration | ✅ `test_db_runtime_guardrails.py` + 259 tests |
| Cross-module avoidance | No hard imports between modules | ✅ No imports from auth/llm |
| Vertical ownership | Clear host vs module responsibilities | ✅ All host integration via stable APIs |

This validation means any other module (auth_usermanagement, llm, etc.) that follows the same pattern will integrate as smoothly as billing did.

---

## 12. Minimal Host Integration Contract Template

Each module should ship a short "Host Integration Contract" section in its docs:

- Host must provide: DB runtime, app wiring, env vars, migration execution
- Module provides: package code, routes, schemas, migrations, module settings
- Import boundary: only module `database.py` may import from host DB runtime
- Test gate: required unit tests and required integration tests

Use the same contract format across auth, billing, and llm so host teams can integrate each module the same way.

---

## 13. Recommended Next Steps Checklist

Before integrating your next module:

- [ ] **Template the bridge pattern** — provide boilerplate `<module>/database.py` for any new module (copy from billing/database.py)
- [ ] **Document guardrail tests** — require test_db_runtime_guardrails.py + test_module_import_boundaries.py in every module
- [ ] **Define service contracts** — each module publishes stable API (function names, signatures, idempotency rules) in a `*_contract.py` file
- [ ] **Test the full stack** — integrate auth + billing together in host, verify: user creation → billing entity → entitlement → accessible feature
- [ ] **Add cross-module integration tests** — host tests should verify permission/tenant isolation across module boundaries
- [ ] **Pin module versions** — use .gitmodules commit hash or maintain modules-manifest.yaml
- [ ] **Review import scan** — run guardrail tests for all modules before each release

---

## 14. Recommended First Pass for Your Stack

For your current direction (auth + billing + llm), start with:

1. Keep `auth_usermanagement` as the reference integration contract
2. Build `billing` and `llm` to mirror the same package layout and DB bridge pattern
3. Maintain one host Alembic pipeline with multi-location revisions
4. Put cross-module workflows (for example entitlement checks before llm actions) in host services, not inside module packages

This gives you a predictable host architecture where modules remain independently releasable, and host integration remains stable over time.
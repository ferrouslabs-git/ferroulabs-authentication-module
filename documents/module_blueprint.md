# Ferrouslabs Module Blueprint

> How to build a new reusable module (e.g. billing, analytics, notifications) that follows the same architecture as `auth_usermanagement`.

Last updated: 2026-03-28

---

## Table of Contents

1. [Guiding Principles](#1-guiding-principles)
2. [Repository Structure](#2-repository-structure)
3. [Backend Package Layout](#3-backend-package-layout)
4. [Database Bridge Pattern](#4-database-bridge-pattern)
5. [Models Pattern](#5-models-pattern)
6. [Schemas Pattern](#6-schemas-pattern)
7. [Services Pattern](#7-services-pattern)
8. [API Router Composition](#8-api-router-composition)
9. [Security & Middleware](#9-security--middleware)
10. [Module Config Pattern](#10-module-config-pattern)
11. [Alembic Migrations](#11-alembic-migrations)
12. [Tests Pattern](#12-tests-pattern)
13. [Frontend Module Layout](#13-frontend-module-layout)
14. [Host Integration Contract](#14-host-integration-contract)
15. [Submodule Setup](#15-submodule-setup)
16. [Copilot Instructions Rules](#16-copilot-instructions-rules)
17. [New Module Checklist](#17-new-module-checklist)

---

## 1. Guiding Principles

Every reusable module must follow these rules:

- **Host owns the database runtime.** The module never creates `engine`, `SessionLocal`, `Base`, or `get_db`. It imports them from the host via a single bridge file.
- **Module owns only module-specific config.** Never define `DATABASE_URL`, `CORS_ALLOWED_ORIGINS`, or any host-level setting inside the module.
- **All internal imports are relative.** Only `database.py` (the bridge) may use absolute imports from `app.database`. Every other file uses `from ..database import Base`.
- **Services never create sessions.** They receive `db: Session` as a parameter from the caller (route handler or dependency).
- **Migrations are module-defined, host-executed.** The module provides migration files; the host app's Alembic pipeline runs them.

---

## 2. Repository Structure

Each module lives in its own Git repository so it can be consumed as a submodule:

```
<module_name>/                  ← Git repo root
├── backend/
│   └── app/
│       └── <module_name>/      ← Python package
├── frontend/
│   └── src/
│       └── <module_name>/      ← JS/React package
├── documents/                  ← Module docs
├── tests/                      ← Backend tests
├── .github/
│   └── copilot-instructions.md
├── README.md
├── requirements.txt
└── docker-compose.yml          ← Optional sandbox
```

When integrated into a host app, the module is mounted via **two symlinks**:

```
host-app/
├── backend/
│   └── app/
│       ├── database.py         ← Host-owned
│       ├── config.py           ← Host-owned
│       ├── main.py             ← Host-owned
│       └── <module_name>/      ← Symlink → submodule/backend/app/<module_name>
├── frontend/
│   └── src/
│       └── <module_name>/      ← Symlink → submodule/frontend/src/<module_name>
└── submodules/
    └── <module_name>/          ← Git submodule
```

---

## 3. Backend Package Layout

```
<module_name>/
├── __init__.py          ← Module docstring only
├── database.py          ← Bridge file (sole absolute import)
├── config.py            ← Module-specific pydantic-settings
├── api/
│   ├── __init__.py      ← Router composition
│   ├── foo_routes.py
│   └── bar_routes.py
├── models/
│   ├── __init__.py      ← Re-exports all models
│   ├── foo.py
│   └── bar.py
├── schemas/
│   ├── __init__.py      ← Re-exports all schemas
│   ├── foo.py
│   └── bar.py
├── services/
│   ├── __init__.py      ← Docstring only (no code exports)
│   ├── foo_service.py
│   └── bar_service.py
└── security/              ← Optional, only if module has guards/middleware
    ├── __init__.py
    └── ...
```

---

## 4. Database Bridge Pattern

**File: `<module_name>/database.py`**

This is the only file that uses absolute imports from the host app. Every other file in the module imports from here using relative imports.

```python
"""Transitional DB compatibility layer for <module_name> module.

Do not create DB runtime objects here. Host app owns engine/session/Base/get_db.
"""

from app.database import Base, SessionLocal, get_db, engine

__all__ = ["engine", "SessionLocal", "Base", "get_db"]
```

**Rules:**
- Never add `create_engine()`, `sessionmaker()`, or `declarative_base()` calls here.
- This file is the sole import boundary between host and module.
- If the host changes its DB module path, only this file needs updating.

---

## 5. Models Pattern

**File: `<module_name>/models/foo.py`**

```python
"""
Foo model — brief description of what it represents
"""
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime, UTC
from uuid import uuid4

from ..database import Base


def utc_now() -> datetime:
    """Return naive UTC datetime compatible with existing DB DateTime columns."""
    return datetime.now(UTC).replace(tzinfo=None)


class Foo(Base):
    __tablename__ = "foos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
```

**Conventions:**
- Import `Base` via `from ..database import Base` — never `from app.database`.
- Use `UUID(as_uuid=True)` for primary keys with `default=uuid4`.
- Use the `utc_now()` helper for timestamps.
- Include `tenant_id` on every tenant-scoped table.
- Add `__repr__` for debugging convenience.

**File: `<module_name>/models/__init__.py`**

```python
"""
SQLAlchemy ORM models for <module_name> module
"""
from .foo import Foo
from .bar import Bar

__all__ = [
    "Foo",
    "Bar",
]
```

---

## 6. Schemas Pattern

**File: `<module_name>/schemas/foo.py`**

Use Pydantic v2 schemas for request/response validation:

```python
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class FooCreateRequest(BaseModel):
    name: str

class FooResponse(BaseModel):
    id: UUID
    name: str
    tenant_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}
```

**File: `<module_name>/schemas/__init__.py`**

```python
"""
Pydantic schemas for request/response validation
"""
from .foo import FooCreateRequest, FooResponse
from .bar import BarCreateRequest, BarResponse
```

---

## 7. Services Pattern

**File: `<module_name>/services/foo_service.py`**

```python
"""
Foo service — business logic for Foo entities
"""
from uuid import UUID
from sqlalchemy.orm import Session

from ..models.foo import Foo


def create_foo(db: Session, *, name: str, tenant_id: UUID) -> Foo:
    """Create a new Foo record."""
    foo = Foo(name=name, tenant_id=tenant_id)
    db.add(foo)
    db.commit()
    db.refresh(foo)
    return foo


def get_foo(db: Session, *, foo_id: UUID, tenant_id: UUID) -> Foo | None:
    """Get a Foo by ID scoped to tenant."""
    return db.query(Foo).filter(
        Foo.id == foo_id,
        Foo.tenant_id == tenant_id,
    ).first()
```

**Rules:**
- Every service function receives `db: Session` as its first argument.
- Services **never** call `get_db()`, `SessionLocal()`, or create their own sessions.
- The caller (route handler) is responsible for providing the session via `Depends(get_db)`.
- All tenant-scoped queries must filter by `tenant_id`.

**File: `<module_name>/services/__init__.py`**

```python
"""
Business logic services for <module_name> module

Includes:
- foo_service: Foo lifecycle management
- bar_service: Bar operations
"""
```

Keep this as a docstring only — do not re-export service functions. Callers import directly from the specific service file.

---

## 8. API Router Composition

**File: `<module_name>/api/__init__.py`**

```python
"""<Module_name> API router composition layer."""

from fastapi import APIRouter

from .foo_routes import router as foo_router
from .bar_routes import router as bar_router

router = APIRouter()

router.include_router(foo_router)
router.include_router(bar_router)
```

**File: `<module_name>/api/foo_routes.py`**

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas.foo import FooCreateRequest, FooResponse
from ..services import foo_service

router = APIRouter(prefix="/foos", tags=["foos"])


@router.post("/", response_model=FooResponse)
def create_foo(
    payload: FooCreateRequest,
    db: Session = Depends(get_db),
):
    return foo_service.create_foo(db, name=payload.name, tenant_id=...)
```

**Host integration (`main.py`):**

```python
from app.<module_name>.api import router as module_router
from app.<module_name>.config import get_settings

settings = get_settings()
app.include_router(module_router, prefix=settings.api_prefix, tags=["<module_name>"])
```

---

## 9. Security & Middleware

If the module provides middleware (e.g. rate limiting, context injection), follow these rules:

- Middleware must **not** call `SessionLocal()` directly.
- Middleware may read headers/auth tokens for prechecks.
- Tenant/context validation that requires DB access must go through `Depends(get_db)` in the dependency chain — not in middleware.
- Export all public security utilities from `security/__init__.py`.

**Example `security/__init__.py`:**

```python
"""
Security utilities for <module_name> module
"""
from .some_guard import require_foo_access
from .some_middleware import FooMiddleware
```

**Host registers middleware in `main.py`:**

```python
from app.<module_name>.security import FooMiddleware

app.add_middleware(FooMiddleware, ...)
```

---

## 10. Module Config Pattern

**File: `<module_name>/config.py`**

```python
"""
Settings for the <module_name> module.

This file should define module-specific settings only.
Host apps own shared runtime settings (for example DATABASE_URL).
"""
import os
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """<Module_name> module settings loaded from environment variables."""

    # Module-specific env vars only
    api_prefix: str = os.getenv("<MODULE>_API_PREFIX", "/<module_name>")
    some_api_key: str = os.getenv("<MODULE>_API_KEY", "")

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Return cached module settings."""
    return Settings()
```

**Rules:**
- Never define `DATABASE_URL`, `CORS_ALLOWED_ORIGINS`, or any host-level setting.
- Use `@lru_cache()` for the getter so it's created once.
- Prefix all env var names with the module name (e.g. `BILLING_API_KEY`, `BILLING_STRIPE_SECRET`).

---

## 11. Alembic Migrations

The module defines migration files. The host app executes them.

**Module side — create a versions folder:**

```
backend/alembic/versions/   ← Module's migration files live here
```

**Host side — `alembic.ini` uses `version_locations`:**

```ini
[alembic]
script_location = %(here)s/alembic
version_locations =
    %(here)s/alembic/versions
    %(here)s/submodules/<module_name>/backend/alembic/versions
```

**Creating a new migration:**

```bash
cd backend
alembic revision --autogenerate -m "add foos table"
```

The migration file lands in the module's `alembic/versions/` folder and gets picked up by the host's Alembic pipeline via `version_locations`.

---

## 12. Tests Pattern

**File: `tests/conftest.py`**

```python
"""Test configuration for <module_name> tests."""
from pathlib import Path
import sys
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database session for testing."""
    from app.database import Base

    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    yield session

    session.close()
    Base.metadata.drop_all(engine)
```

**Example test file: `tests/test_foo_service.py`**

```python
from app.<module_name>.services import foo_service


def test_create_foo(db_session):
    foo = foo_service.create_foo(db_session, name="Test", tenant_id=some_uuid)
    assert foo.name == "Test"
    assert foo.tenant_id == some_uuid
```

**Rules:**
- Tests use SQLite in-memory for speed.
- If the module has tenant-scoped logic, add PostgreSQL RLS tests gated by `RUN_POSTGRES_RLS_TESTS=1`.
- Add a `test_db_runtime_guardrails.py` that scans module source for forbidden patterns:
  - No `create_engine()` inside the module package
  - No `from app.database import` outside of `database.py`
  - No `sessionmaker()` or `declarative_base()` inside the module package

**Standard test commands:**

```bash
# Unit tests (SQLite)
pytest -q tests

# Tenant isolation tests (PostgreSQL)
RUN_POSTGRES_RLS_TESTS=1 DATABASE_URL=postgresql://... pytest -q tests
```

---

## 13. Frontend Module Layout

```
<module_name>/
├── index.js             ← Barrel exports (single entry point)
├── config.js            ← Module config (reads VITE_ env vars)
├── config.test.js       ← Config tests
├── context/             ← React context providers
│   └── FooProvider.jsx
├── hooks/               ← Custom React hooks
│   ├── useFoo.js
│   └── useBar.js
├── services/            ← API call layers (axios)
│   └── fooApi.js
├── components/          ← Reusable UI components
│   ├── FooList.jsx
│   └── FooForm.jsx
├── pages/               ← Full page components
│   └── index.js
├── constants/           ← Module constants
└── utils/               ← Module utilities
```

**File: `<module_name>/index.js`**

Barrel file that re-exports everything consumers need:

```js
// Context
export { FooProvider } from "./context/FooProvider";

// Hooks
export { useFoo } from "./hooks/useFoo";
export { useBar } from "./hooks/useBar";

// Components
export { FooList } from "./components/FooList";
export { FooForm } from "./components/FooForm";

// Pages
export { FooDashboard } from "./pages";

// Services
export * as fooApi from "./services/fooApi";

// Config
export * from "./config";
```

**File: `<module_name>/config.js`**

```js
function normalizePathPrefix(path, fallback) {
  const value = (path || fallback || "").trim();
  if (!value) return fallback;
  const withLeading = value.startsWith("/") ? value : `/${value}`;
  return withLeading.replace(/\/+$/, "") || fallback;
}

export const isBrowser = typeof window !== "undefined";

export function buildModuleConfig(env = import.meta.env) {
  const namespace = (env.VITE_<MODULE>_NAMESPACE || "<module_name>").trim();
  return {
    namespace,
    apiPrefix: normalizePathPrefix(env.VITE_<MODULE>_API_PREFIX, "/<module_name>"),
    // Add module-specific frontend config here
  };
}

export const config = buildModuleConfig();
```

**Rules:**
- All env vars must be prefixed with `VITE_<MODULE>_`.
- The barrel `index.js` is the only import consumers use.
- API service files use axios and read the module's API prefix from config.

---

## 14. Host Integration Contract

Every module must document what the **host owns** vs. what the **module owns**:

| Concern | Owner | Notes |
|---------|-------|-------|
| `engine`, `SessionLocal`, `Base`, `get_db` | **Host** | Module imports via `database.py` bridge |
| `DATABASE_URL` | **Host** | Module never defines this |
| CORS configuration | **Host** | Set in `main.py` middleware |
| Alembic migration execution | **Host** | Module provides version files only |
| Module-specific env vars | **Module** | Prefixed with module name |
| Models, schemas, services | **Module** | Module defines, host imports |
| API routes | **Module** | Module defines router, host mounts at prefix |
| Middleware registration | **Host** | Module provides classes, host registers them |
| Frontend context providers | **Host** | Module provides, host wraps in App tree |
| Frontend routing | **Host** | Module provides page components, host defines routes |

Include this table (filled in with specifics) in the module's `README.md` or a dedicated `HOST_INTEGRATION.md`.

---

## 15. Submodule Setup

### Adding the module to a host app

```bash
# 1. Add as submodule
git submodule add <repo-url> submodules/<module_name>
git submodule update --init --recursive

# 2. Create symlinks (two required)
# PowerShell (Windows):
New-Item -ItemType SymbolicLink -Path "backend\app\<module_name>" -Target "..\..\submodules\<module_name>\backend\app\<module_name>"
New-Item -ItemType SymbolicLink -Path "frontend\src\<module_name>" -Target "..\..\submodules\<module_name>\frontend\src\<module_name>"

# Bash (Linux/Mac):
ln -s ../../submodules/<module_name>/backend/app/<module_name> backend/app/<module_name>
ln -s ../../submodules/<module_name>/frontend/src/<module_name> frontend/src/<module_name>

# 3. Add migration path to alembic.ini
# Under [alembic], add the module's versions folder to version_locations
```

### Updating the module

```bash
cd submodules/<module_name>
git pull origin main
cd ../..
git add submodules/<module_name>
git commit -m "update <module_name> submodule"
```

---

## 16. Copilot Instructions Rules

Every module's `.github/copilot-instructions.md` must include these rules (adapted from auth_usermanagement):

```
1. Database ownership rule:
   - Never create SQLAlchemy engine, SessionLocal, or Base inside reusable modules.
   - Reusable modules must import DB runtime objects from host integration points.

2. Dependency rule:
   - All FastAPI Depends(get_db) usage must resolve to host-owned get_db.

3. Middleware rule:
   - Module middleware must not instantiate new DB sessions directly.
   - Middleware must use request-scoped DB/session strategy approved by host.

4. Configuration rule:
   - Module must not own root app settings such as DATABASE_URL.
   - Module config files may only define module-specific settings.

5. Migration rule:
   - Module can define schema/migration assets.
   - Migration execution ownership remains with host app Alembic pipeline.

6. Import boundary rule:
   - No duplicate DB runtime modules for the same process.
   - All files inside <module_name>/ must use relative imports for DB objects.
   - Only <module_name>/database.py may reference 'from app.database import ...'.

7. Review gate rule:
   - Any PR that adds create_engine(), sessionmaker(), or declarative_base()
     in module paths must be blocked.

8. Documentation rule:
   - Module must include a Host Integration Contract section.

9. Test command rule:
   - Standard verification: pytest -q tests
   - Add RLS tests if module has tenant-scoped data.

10. No validation bypass rule:
    - Do not add convenience code paths that skip tenant validation in non-test runtime.
```

---

## 17. New Module Checklist

Use this checklist when creating a new module from scratch:

### Backend

- [ ] Create `<module_name>/__init__.py` with module docstring
- [ ] Create `<module_name>/database.py` bridge (copy exact pattern from Section 4)
- [ ] Create `<module_name>/config.py` with module-specific Settings class
- [ ] Create `<module_name>/models/` with at least one model + `__init__.py` re-exports
- [ ] Create `<module_name>/schemas/` with request/response schemas + `__init__.py`
- [ ] Create `<module_name>/services/` with business logic + `__init__.py` docstring
- [ ] Create `<module_name>/api/__init__.py` with router composition
- [ ] Create `<module_name>/api/*_routes.py` for each resource
- [ ] Create `<module_name>/security/` if module needs guards or middleware
- [ ] Verify: no `create_engine()` / `sessionmaker()` / `declarative_base()` inside module
- [ ] Verify: only `database.py` has `from app.database import ...`
- [ ] Verify: all other files use `from ..database import Base` (relative)

### Alembic

- [ ] Create initial migration with `alembic revision --autogenerate`
- [ ] Migration file exists in module's `alembic/versions/`
- [ ] Host `alembic.ini` has module path in `version_locations`

### Tests

- [ ] Create `tests/conftest.py` with SQLite in-memory `db_session` fixture
- [ ] Create `tests/test_db_runtime_guardrails.py` (import boundary enforcement)
- [ ] Add service tests for each service function
- [ ] Add API tests for each endpoint
- [ ] All tests pass: `pytest -q tests`

### Frontend

- [ ] Create `<module_name>/index.js` barrel exports
- [ ] Create `<module_name>/config.js` with `VITE_` env var config
- [ ] Create `context/`, `hooks/`, `services/`, `components/` subdirectories
- [ ] All imports in host app go through `<module_name>/index.js`

### Documentation

- [ ] Module `README.md` with Host Integration Contract table
- [ ] `.github/copilot-instructions.md` with all rules from Section 16
- [ ] Module added to host's `documents/README.md` index

### Integration

- [ ] Symlinks created (backend + frontend)
- [ ] Module router mounted in host `main.py` with configurable prefix
- [ ] Module middleware registered in host `main.py` (if applicable)
- [ ] Module's Alembic versions path added to host `alembic.ini`
- [ ] All host tests still pass after integration

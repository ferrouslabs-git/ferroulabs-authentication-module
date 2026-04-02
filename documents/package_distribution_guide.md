# Package Distribution Guide

How to package this module so host apps install it as a dependency instead of copy-pasting source files.

## Goal

Move from source inclusion to installable packages:

1. Python package for backend auth module
2. npm package for frontend auth module
3. Keep host ownership boundaries exactly the same

This keeps your architecture rules intact:

- Host app owns DB runtime (`engine`, `SessionLocal`, `Base`, `get_db`)
- Module owns auth logic, routes, models, services
- Host app runs Alembic migrations

## Recommended rollout path

1. Keep Git submodule flow as current stable path.
2. Add package metadata and publish private prerelease versions.
3. Test package install in a clean host sample app.
4. Promote to stable versions after migration and RLS tests pass.

## Backend packaging (Python)

## 1. Proposed backend layout

Use a `src` layout in the module repo:

```text
backend/
	pyproject.toml
	README.md
	src/
		ferrouslabs_auth/
			__init__.py
			auth_usermanagement/
				__init__.py
				api/
				models/
				schemas/
				services/
				security/
				config.py
				auth_config.yaml
				database_bridge.py
	alembic/
		versions/
	tests/
```

Notes:

- `database_bridge.py` is the only place allowed to connect to host DB objects.
- Keep all internal imports relative below package root.

## 2. Minimal `pyproject.toml`

```toml
[build-system]
requires = ["setuptools>=69", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "ferrouslabs-auth-usermanagement"
version = "0.1.0"
description = "Reusable auth and user management module for FastAPI host apps"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
	"fastapi>=0.110",
	"sqlalchemy>=2.0",
	"pydantic>=2.6",
	"pydantic-settings>=2.2",
	"python-jose[cryptography]>=3.3",
	"python-json-logger>=2.0",
	"boto3>=1.34"
]

[tool.setuptools]
package-dir = {"" = "src"}
include-package-data = true

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-data]
"ferrouslabs_auth.auth_usermanagement" = ["auth_config.yaml"]
```

## 3. Host integration API

Expose simple install hooks so host apps do less wiring.

Example public API shape:

```python
def register_auth_module(app, *, get_db_dependency):
		"""Mount routers and wire dependencies in host app."""

def include_auth_models(base):
		"""Import models so Alembic autogenerate can see metadata."""
```

Important:

- Do not create SQLAlchemy runtime objects in package code.
- Keep dependency injection path tied to host-owned `get_db`.

## 4. Build and publish

Build:

```bash
cd backend
python -m build
```

Publish to private index (example):

```bash
python -m twine upload --repository-url <private-pypi-url> dist/*
```

Install in host app:

```bash
pip install ferrouslabs-auth-usermanagement==0.1.0
```

## Frontend packaging (npm)

## 1. Proposed frontend layout

```text
frontend/
	package.json
	tsconfig.json
	src/
		index.ts
		auth_usermanagement/
			components/
			hooks/
			context/
			services/
```

## 2. Minimal `package.json`

```json
{
	"name": "@ferrouslabs/auth-usermanagement",
	"version": "0.1.0",
	"type": "module",
	"main": "./dist/index.cjs",
	"module": "./dist/index.js",
	"types": "./dist/index.d.ts",
	"files": ["dist"],
	"scripts": {
		"build": "tsup src/index.ts --format cjs,esm --dts",
		"test": "vitest run"
	},
	"peerDependencies": {
		"react": ">=18",
		"react-dom": ">=18"
	}
}
```

Install in host frontend:

```bash
npm install @ferrouslabs/auth-usermanagement@0.1.0
```

## Migration ownership (critical)

Packaging does not change migration ownership.

- Module still defines migration files.
- Host app Alembic still executes them.
- Host `alembic.ini` uses `version_locations` to include module migrations.

Example:

```ini
[alembic]
script_location = %(here)s/alembic
version_locations = %(here)s/alembic/versions %(here)s/.venv/lib/pythonX.Y/site-packages/ferrouslabs_auth/alembic/versions
```

You can avoid site-packages path fragility by copying packaged migrations to a host-controlled vendor directory during CI and pointing `version_locations` there.

## CI/CD checklist

1. Build backend wheel and sdist.
2. Build frontend package.
3. Spin up sample host app.
4. Install both packages.
5. Run host migrations.
6. Run tests:
	 - `pytest -q tests`
	 - `RUN_COGNITO_TESTS=1` when auth/Cognito code changes
	 - `RUN_POSTGRES_RLS_TESTS=1` with PostgreSQL for tenant/RLS changes
7. Publish only if all checks pass.

## Versioning policy

Use semantic versioning:

- MAJOR: breaking API or behavior changes
- MINOR: backward-compatible features
- PATCH: backward-compatible fixes

Recommended release flow:

1. Tag prerelease (`0.2.0-rc.1`)
2. Validate in one real host app
3. Promote to stable tag (`0.2.0`)

## What to do now

If you want low risk right now:

1. Keep submodule integration in production.
2. Add backend `pyproject.toml` and frontend package metadata in this repo.
3. Publish private prerelease packages.
4. Test one host app install path end-to-end.

If you want, next step I can generate the actual backend `pyproject.toml` and frontend package export files in this repository.

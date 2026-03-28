# Submodule Integration Guide

> How to add `ferrouslabs-auth-system` as a Git submodule inside a host app instead of copy-pasting files.

---

## Why Submodule?

Copy-pasting `auth_usermanagement/` works but creates maintenance pain:
- No clear way to pull upstream fixes/features.
- Drift between the source repo and pasted copies.
- Manual diff/merge when the module is updated.

A Git submodule keeps the auth repo as a versioned dependency. You pin a specific commit, and updating is a single `git submodule update` command.

---

## Strategy: Submodule + Symlinks

The module uses relative imports (`from ..database import Base`) and expects to live at `app/auth_usermanagement/` inside the host's Python package. A symlink bridges the submodule location to the expected import path.

Alembic migrations are handled via `version_locations` in `alembic.ini` — no symlink needed for the versions folder.

```
host-app/
├── vendor/
│   └── ferrouslabs-auth-system/    ← Git submodule (this repo)
├── backend/
│   ├── app/
│   │   ├── config.py               ← Host settings
│   │   ├── database.py             ← Host DB runtime (you own this)
│   │   ├── main.py                 ← Host entrypoint
│   │   └── auth_usermanagement/    ← SYMLINK → vendor/ferrouslabs-auth-system/backend/app/auth_usermanagement/
│   ├── alembic/
│   │   ├── env.py                  ← Host migration runner (you own this)
│   │   └── versions/               ← Host-only migrations (your own tables)
│   └── alembic.ini                 ← version_locations points to both host + submodule migrations
└── frontend/
    └── src/
        └── auth_usermanagement/    ← SYMLINK → vendor/ferrouslabs-auth-system/frontend/src/auth_usermanagement/
```

The module's `database.py` bridge does `from app.database import Base, SessionLocal, get_db, engine` — so it resolves to **your** host's `app/database.py` at runtime. No fork needed.

---

## Step-by-Step Setup

### 1. Add the submodule

From your host project root:

```bash
git submodule add https://github.com/ferrouslabs/ferrouslabs-auth-system.git vendor/ferrouslabs-auth-system
git submodule update --init --recursive
```

This creates:
- `vendor/ferrouslabs-auth-system/` — the full auth repo, pinned to a specific commit.
- `.gitmodules` — tracks the submodule URL and path.

### 2. Create the backend symlink

**macOS / Linux:**

```bash
cd backend/app
ln -s ../../vendor/ferrouslabs-auth-system/backend/app/auth_usermanagement auth_usermanagement
```

**Windows (elevated PowerShell or Git Bash):**

```powershell
# Requires developer mode enabled OR an elevated shell
cd backend\app
New-Item -ItemType SymbolicLink -Path auth_usermanagement -Target ..\..\vendor\ferrouslabs-auth-system\backend\app\auth_usermanagement
```

Or use the Git config to handle symlinks automatically:

```bash
git config core.symlinks true
```

Verify the import works:

```bash
cd backend
python -c "from app.auth_usermanagement.config import get_settings; print(get_settings())"
```

### 3. Configure Alembic for multiple version locations

The auth module's migration files live in `vendor/ferrouslabs-auth-system/backend/alembic/versions/`. Your host app will have its own migrations too. Alembic's `version_locations` lets both co-exist without symlinks.

In `alembic.ini`:

```ini
[alembic]
script_location = %(here)s/alembic

# Include both host and auth module migration directories
version_locations = %(here)s/alembic/versions %(here)s/vendor/ferrouslabs-auth-system/backend/alembic/versions
```

In `alembic/env.py`, enable the path separator so Alembic reads the space-separated list:

```python
# After: config = context.config
# Add version_path_separator for multi-location support
context.configure(
    ...
    version_path_separator="space",  # or "os" for OS-native separator
)
```

Then `alembic upgrade head` picks up migrations from both directories. New host-app migrations go into `backend/alembic/versions/`, and auth module migrations come from the submodule.

If both chains are independent (no shared `down_revision`), Alembic will report "multiple heads." Merge them once:

```bash
alembic merge heads -m "merge host and auth module migrations"
```

> **Alternative — Symlink (module-only migrations):** If your host app has no migrations of its own, you can skip `version_locations` and instead symlink the entire versions folder: `ln -s ../../vendor/ferrouslabs-auth-system/backend/alembic/versions backend/alembic/versions`. This is simpler but doesn't scale once you add host-side tables.

### 4. Create the frontend symlink

```bash
cd frontend/src
ln -s ../../vendor/ferrouslabs-auth-system/frontend/src/auth_usermanagement auth_usermanagement
```

Windows:

```powershell
cd frontend\src
New-Item -ItemType SymbolicLink -Path auth_usermanagement -Target ..\..\vendor\ferrouslabs-auth-system\frontend\src\auth_usermanagement
```

Vite follows symlinks by default, so no config changes needed.

### 5. Host-owned files (do NOT symlink these)

These files must exist in your host project — they are NOT part of the submodule:

| File | Purpose | Why host-owned |
|---|---|---|
| `backend/app/database.py` | DB engine, SessionLocal, Base, get_db() | Database ownership rule — module imports from host |
| `backend/app/config.py` | CORS, host-level settings | Host environment configuration |
| `backend/app/main.py` | FastAPI app, middleware registration, router mount | Host wiring |
| `backend/alembic/env.py` | Alembic migration runner | Host controls migration execution |
| `backend/alembic.ini` | Alembic config | Points to host's env.py |
| `backend/.env` | All env vars (Cognito, DB, SES, AUTH_MODE) | Host secrets |
| `frontend/.env` | VITE_* env vars | Host frontend config |

Copy these from the auth repo's examples in [setup_guide.md](setup_guide.md) and customise for your host app.

---

## Updating the Submodule

### Pull latest changes

```bash
cd vendor/ferrouslabs-auth-system
git fetch origin
git checkout main          # or a specific tag/commit
git pull origin main

# Back to host root
cd ../..
git add vendor/ferrouslabs-auth-system
git commit -m "Update auth submodule to latest"
```

### Pin to a specific version

```bash
cd vendor/ferrouslabs-auth-system
git checkout v2.1.0        # or a specific commit SHA
cd ../..
git add vendor/ferrouslabs-auth-system
git commit -m "Pin auth submodule to v2.1.0"
```

### After updating — run migrations

If the update includes new Alembic migrations:

```bash
cd backend
alembic upgrade head
```

---

## Cloning a Host Repo That Uses This Submodule

When someone clones your host project for the first time:

```bash
git clone --recurse-submodules https://github.com/your-org/your-host-app.git
```

Or if they already cloned without `--recurse-submodules`:

```bash
git submodule update --init --recursive
```

---

## CI/CD

In your CI pipeline, add the submodule init step before installing dependencies:

```yaml
# GitHub Actions example
steps:
  - uses: actions/checkout@v4
    with:
      submodules: recursive

  - name: Install backend deps
    run: pip install -r backend/requirements.txt

  - name: Run tests
    run: cd backend && pytest -q tests
```

---

## Windows Symlink Notes

Windows requires one of:
- **Developer Mode enabled** (Settings → For Developers → toggle on)
- **Elevated (admin) PowerShell** to create symlinks with `New-Item -ItemType SymbolicLink`

Alternatively, **directory junctions** work without elevation (used in the setup scripts above):

```powershell
cmd /c mklink /J backend\app\auth_usermanagement vendor\ferrouslabs-auth-system\backend\app\auth_usermanagement
cmd /c mklink /J frontend\src\auth_usermanagement vendor\ferrouslabs-auth-system\frontend\src\auth_usermanagement
```

Junctions work the same as symlinks for Python imports and Vite bundling. The only difference is junctions are Windows-only and don't work across network drives. Note: no junction needed for Alembic versions — `version_locations` in `alembic.ini` handles that.

Also set Git to handle symlinks:

```bash
git config --global core.symlinks true
```

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'app.auth_usermanagement'`

The symlink is missing or broken. Check:
```bash
ls -la backend/app/auth_usermanagement   # Should show → vendor/...
```

### `ImportError: cannot import name 'Base' from 'app.database'`

Your host's `backend/app/database.py` is missing or doesn't export `Base`. Create it per [setup_guide.md](setup_guide.md) Step 2.

### Alembic can't find migrations

Make sure `alembic.ini` has the `version_locations` line and both paths are correct relative to `alembic.ini`. Also verify `version_path_separator="space"` is set in `alembic/env.py`'s `context.configure()` call.

### Circular import on startup

Make sure you did **not** symlink `database.py` — the submodule's `auth_usermanagement/database.py` must remain in place (it's the bridge that does `from app.database import ...`). Only the parent `auth_usermanagement/` folder is symlinked.

---

## Comparison: Copy-Paste vs Submodule

| Aspect | Copy-Paste | Submodule + Symlink |
|---|---|---|
| Initial setup | Copy folder, done | Add submodule, create 2 symlinks, configure `alembic.ini` |
| Getting updates | Manual diff + merge | `git submodule update` + `alembic upgrade head` |
| Version pinning | None (just whatever was copied) | Pinned to exact commit/tag |
| Host-owned bridge files | Same | Same (`database.py`, `main.py`, `.env`) |
| Works on all OS | Yes | Yes (symlinks/junctions on Windows need setup) |
| CI complexity | None | Add `submodules: recursive` to checkout |
| Risk of drift | High over time | None — source of truth is the submodule |
| Multiple host apps | Each copy diverges independently | All point to same upstream, update independently |

---

## Quick Setup Script

Save as `setup-auth-submodule.sh` in your host project root:

```bash
#!/bin/bash
set -e

# 1. Add submodule
git submodule add https://github.com/ferrouslabs/ferrouslabs-auth-system.git vendor/ferrouslabs-auth-system
git submodule update --init --recursive

# 2. Backend symlink
ln -sf ../../vendor/ferrouslabs-auth-system/backend/app/auth_usermanagement backend/app/auth_usermanagement

# 3. Frontend symlink
ln -sf ../../vendor/ferrouslabs-auth-system/frontend/src/auth_usermanagement frontend/src/auth_usermanagement

echo ""
echo "Done. Now:"
echo "  1. Create your host-owned files:"
echo "     - backend/app/database.py"
echo "     - backend/app/config.py"
echo "     - backend/app/main.py"
echo "     - backend/alembic/env.py (add version_path_separator='space')"
echo "     - backend/.env"
echo "     - frontend/.env"
echo "  2. Add version_locations to alembic.ini:"
echo "     version_locations = %(here)s/alembic/versions %(here)s/vendor/ferrouslabs-auth-system/backend/alembic/versions"
echo ""
echo "See documents/setup_guide.md and documents/submodule_integration_guide.md for details."
```

Windows equivalent (`setup-auth-submodule.ps1`):

```powershell
# 1. Add submodule
git submodule add https://github.com/ferrouslabs/ferrouslabs-auth-system.git vendor/ferrouslabs-auth-system
git submodule update --init --recursive

# 2. Backend symlink (requires Developer Mode or admin)
if (Test-Path backend\app\auth_usermanagement) { Remove-Item backend\app\auth_usermanagement -Recurse -Force }
cmd /c mklink /J backend\app\auth_usermanagement vendor\ferrouslabs-auth-system\backend\app\auth_usermanagement

# 3. Frontend symlink
if (Test-Path frontend\src\auth_usermanagement) { Remove-Item frontend\src\auth_usermanagement -Recurse -Force }
cmd /c mklink /J frontend\src\auth_usermanagement vendor\ferrouslabs-auth-system\frontend\src\auth_usermanagement

Write-Host ""
Write-Host "Done. Now:"
Write-Host "  1. Create your host-owned files (see documents/setup_guide.md)"
Write-Host "  2. Add version_locations to alembic.ini:"
Write-Host "     version_locations = %(here)s/alembic/versions %(here)s/vendor/ferrouslabs-auth-system/backend/alembic/versions"
Write-Host "  3. Add version_path_separator='space' to alembic/env.py context.configure()"
Write-Host ""
Write-Host "See documents/submodule_integration_guide.md for full details."
```

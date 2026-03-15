# Auth Module Host Integration Checklist

1. Copy module folders
- Copy backend folder `app/auth_usermanagement` into the host backend.
- Copy frontend folder `src/auth_usermanagement` into the host frontend.
- Example:
	- source: `backend/app/auth_usermanagement`
	- destination: `host_backend/app/auth_usermanagement`
	- source: `frontend/src/auth_usermanagement`
	- destination: `host_frontend/src/auth_usermanagement`

2. Copy auth Alembic migrations into the host app
- Copy the auth-related migration files from `backend/alembic/versions` into the host app's Alembic versions folder.
- Required files in this repo are:
	- `d3494139f54d_create_auth_tables.py`
	- `7a454a9250b1_add_user_suspension_fields.py`
	- `0eec64567dac_enable_row_level_security.py`
	- `8c5f69f3b5d1_add_session_metadata_fields.py`
	- `f1c2d3e4a5b6_add_refresh_token_store_table.py`
- If the host already has its own Alembic history, adjust `down_revision` so the auth chain attaches to the host's latest revision instead of copying blindly.
- Rule: do not skip the migration files. Copying Python models alone will not create tables or RLS policies.

3. Configure backend env values
- Set AUTH_API_PREFIX, AUTH_NAMESPACE, and optional AUTH_COOKIE_NAME/AUTH_COOKIE_PATH.
- Example:
```env
AUTH_API_PREFIX=/auth
AUTH_NAMESPACE=authum
AUTH_COOKIE_NAME=
AUTH_COOKIE_PATH=
```
- If `AUTH_COOKIE_NAME` and `AUTH_COOKIE_PATH` are empty, the module derives them automatically.

4. Configure frontend env values
- Set VITE_AUTH_API_BASE_PATH, VITE_AUTH_NAMESPACE, VITE_AUTH_CALLBACK_PATH, and VITE_AUTH_INVITE_PATH_PREFIX.
- Example:
```env
VITE_AUTH_API_BASE_PATH=/auth
VITE_AUTH_NAMESPACE=authum
VITE_AUTH_CALLBACK_PATH=/callback
VITE_AUTH_INVITE_PATH_PREFIX=/invite/
```
- Keep frontend and backend prefix values aligned.

5. Mount backend router with the same prefix
- Include the auth router using AUTH_API_PREFIX so frontend and backend paths match.
- Example:
```python
from app.auth_usermanagement.api import router as auth_router
from app.auth_usermanagement.config import get_settings

settings = get_settings()
app.include_router(auth_router, prefix=settings.auth_api_prefix, tags=["auth"])
```

6. Register auth middleware with the same prefix
- Initialize TenantContextMiddleware and RateLimitMiddleware using AUTH_API_PREFIX.
- Example:
```python
from app.auth_usermanagement.config import get_settings
from app.auth_usermanagement.security.tenant_middleware import TenantContextMiddleware
from app.auth_usermanagement.security.rate_limit_middleware import RateLimitMiddleware

settings = get_settings()
app.add_middleware(TenantContextMiddleware, auth_prefix=settings.auth_api_prefix)
app.add_middleware(RateLimitMiddleware, auth_prefix=settings.auth_api_prefix)
```

7. Ensure CORS/credentials policy matches deployment
- Allow frontend origin and credentials if cookie-based refresh is used across origins.
- Example FastAPI CORS setup:
```python
app.add_middleware(
		CORSMiddleware,
		allow_origins=["http://localhost:5173"],
		allow_credentials=True,
		allow_methods=["*"],
		allow_headers=["*"],
)
```

8. Add frontend routes
- Add callback route at VITE_AUTH_CALLBACK_PATH and invite route at VITE_AUTH_INVITE_PATH_PREFIX + token.
- Example React Router setup:
```jsx
import { AcceptInvitation, AUTH_CONFIG } from "./auth_usermanagement";

<Route path={AUTH_CONFIG.callbackPath} element={<CallbackPage />} />
<Route path={`${AUTH_CONFIG.invitePathPrefix}:token`} element={<AcceptInvitation />} />
```

9. Wire AuthProvider at app root
- Wrap host app with AuthProvider so hooks/components can access auth state.
- Example:
```jsx
import { AuthProvider } from "./auth_usermanagement";

<AuthProvider>
	<App />
</AuthProvider>
```

10. Import auth models in host Alembic env
- Ensure the host `alembic/env.py` imports auth models so metadata stays complete for future autogeneration.
- Example:
```python
from app.auth_usermanagement.models import (
		Tenant,
		User,
		Membership,
		Invitation,
		Session,
		RefreshTokenStore,
)
```

11. Run migrations in host environment
- Apply host migrations to create auth tables and tenant isolation policies.
- Example:
```powershell
alembic upgrade head
```
- Expected auth tables after migration:
	- `users`
	- `tenants`
	- `memberships`
	- `invitations`
	- `sessions`
	- `refresh_tokens`

12. Run backend verification tests
- Run cookie, middleware, and DB boundary tests before integrating host-specific features.
- Example:
```powershell
pytest -q tests/test_cookie_token_endpoints.py tests/test_db_ownership_boundary.py tests/test_db_runtime_guardrails.py
```

13. Run frontend build and auth smoke test
- Build frontend and verify sign-in, callback, invite acceptance, tenant selection, and logout flows.
- Minimum manual smoke path:
	- sign in via Cognito
	- confirm `POST /auth/cookie/store-refresh` returns `200`
	- confirm browser receives `authum_refresh_token` or configured cookie name
	- refresh page and confirm `POST /auth/token/refresh` returns `200`
	- restart backend and confirm `POST /auth/token/refresh` still returns `200`

14. If the host already has its own auth or user tables, stop and reconcile first
- Do not merge blindly if the host already defines overlapping tables or routes.
- Resolve naming conflicts, route conflicts, and Alembic revision chain conflicts before running migrations.

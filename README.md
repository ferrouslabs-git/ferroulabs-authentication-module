# Auth Module Portability Sandbox

This is a minimal standalone app to test that the `auth_usermanagement` module works outside of TrustOS.

## Purpose

Proves the auth module is truly portable by running it in a fresh React + FastAPI environment with minimal integration code.

## Setup

### Backend

```bash
cd backend
pip install -r requirements.txt
```

### Frontend

```bash
cd frontend
npm install
```

## Run

### Start Backend (Port 8001)

```bash
cd backend
python main.py
```

Or:

```bash
cd backend
uvicorn main:app --reload --port 8001
```

### Start Frontend (Port 5173)

```bash
cd frontend
npm run dev
```

## Test

1. Open http://localhost:5173
2. Click "Login with Cognito"
3. Redirects to Cognito Hosted UI
4. After login, should see:
   - User email displayed
   - Tenant switcher (if you have multiple tenants)
   - User list for current tenant
   - Invite button (if admin/owner)

## What's Being Tested

✅ Auth module works outside TrustOS  
✅ Cognito integration (Hosted UI flow)  
✅ Backend JWT verification  
✅ Tenant switching  
✅ User management (list, invite, role changes)  
✅ Role-based permissions  
✅ Middleware (tenant context, rate limiting, security headers)  

## Files Created

**Backend:**
- `main.py` - Minimal FastAPI app (registers auth router + middleware)
- `database.py` - Database connection (reuses TrustOS database)
- `requirements.txt` - Python dependencies
- `.env` - Environment variables (copied from TrustOS)

**Frontend:**
- `src/App.jsx` - Minimal React app using auth module
- `src/main.jsx` - Entry point
- `index.html` - HTML template
- `package.json` - Node dependencies
- `vite.config.js` - Vite configuration
- `.env` - Frontend environment variables

**Module (copied from TrustOS):**
- `backend/app/auth_usermanagement/` - Backend auth module (single source of truth)
- `frontend/src/auth_usermanagement/` - Frontend auth module

## Success Criteria

If login works and you can see the user list, the module is portable! ✅

## Notes

- Backend runs on port **8001** (not 8000) to avoid conflict with TrustOS
- Frontend runs on port **5173** (Vite default)
- Uses same database as TrustOS (no migrations needed)
- Uses same Cognito User Pool as TrustOS
- Frontend requires `VITE_COGNITO_DOMAIN` and `VITE_COGNITO_CLIENT_ID`; `VITE_COGNITO_REDIRECT_URI` defaults to `<origin>/callback`

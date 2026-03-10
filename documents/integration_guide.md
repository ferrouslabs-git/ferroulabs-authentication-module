# Auth Module Integration Guide

Date: 2026-03-10
Purpose: Instructions for integrating the auth_usermanagement module into a new project

---

## What Ships (Deliverable Module)

### Backend Module
**Copy entire folder:**
```
backend/app/auth_usermanagement/
├── __init__.py
├── config.py
├── database.py
├── api/
│   └── __init__.py
├── models/
│   ├── __init__.py
│   ├── user.py
│   ├── tenant.py
│   ├── membership.py
│   ├── invitation.py
│   └── session.py
├── schemas/
│   ├── __init__.py
│   ├── user_management.py
│   ├── tenant.py
│   ├── invitation.py
│   └── token.py
├── security/
│   ├── __init__.py
│   ├── jwt_verifier.py
│   ├── dependencies.py
│   ├── guards.py
│   ├── tenant_middleware.py
│   ├── tenant_context.py
│   ├── rate_limit_middleware.py
│   └── security_headers_middleware.py
└── services/
    ├── __init__.py
    ├── user_service.py
    ├── user_management_service.py
    ├── tenant_service.py
    ├── invitation_service.py
    ├── email_service.py
    ├── session_service.py
    └── audit_service.py
```

### Frontend Module
**Copy entire folder:**
```
frontend/src/auth_usermanagement/
├── index.js
├── components/
│   ├── AcceptInvitation.jsx
│   ├── AdminDashboard.jsx
│   ├── ConfirmDialog.jsx
│   ├── InviteUserModal.jsx
│   ├── Toast.jsx
│   └── UserList.jsx
├── constants/
│   └── permissions.js
├── context/
│   └── AuthProvider.jsx
├── hooks/
│   └── useAuth.js
├── pages/
│   └── HomePage.jsx
├── services/
│   ├── authApi.js
│   └── cognitoClient.js
└── utils/
    └── errorHandling.js
```

---

## What Does NOT Ship (Project Scaffolding)

### Backend (Do NOT Copy)
```
backend/
├── app/
│   ├── main.py              # Project-specific FastAPI entry point
│   ├── config.py            # Project-level config (replace with your own)
│   └── database.py          # Project-level DB setup (replace with your own)
├── alembic/                 # Migration files (generate fresh in new project)
├── alembic.ini              # Alembic config (create fresh)
├── tests/                   # Test suite (optional to copy for reference)
├── requirements.txt         # Dependencies manifest (merge into yours)
├── _manual_email_test.py    # Test script
├── create_test_invitation.py
└── send_test_invitation.py
```

### Frontend (Do NOT Copy)
```
frontend/
├── src/
│   ├── App.jsx              # App shell (replace with yours)
│   └── main.jsx             # Vite entry point (replace with yours)
├── index.html               # HTML shell (use yours)
├── vite.config.js           # Build config (use yours)
└── package.json             # Dependencies manifest (merge into yours)
```

### Documentation & Config (Do NOT Copy)
```
documents/                   # All documentation (optional for reference)
docs/                        # All documentation
README.md                    # Project README
setup-postgres.ps1           # Database setup script
backend/.env                 # Environment vars (create fresh, see template below)
frontend/.env                # Environment vars (create fresh, see template below)
```

---

## Integration Steps

### Step 1: Copy Module Files

1. Copy `backend/app/auth_usermanagement/` to your backend project
2. Copy `frontend/src/auth_usermanagement/` to your frontend project

### Step 2: Install Dependencies

**Backend (`requirements.txt` additions):**
```txt
fastapi>=0.104.0
sqlalchemy>=2.0.0
alembic>=1.12.0
psycopg2-binary>=2.9.9
python-jose[cryptography]>=3.3.0
boto3>=1.28.0
requests>=2.31.0
python-dotenv>=1.0.0
```

**Frontend (`package.json` additions):**
```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.20.0",
    "axios": "^1.6.0"
  }
}
```

### Step 3: Backend Integration

**3.1 Update your `main.py`:**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.auth_usermanagement.security.tenant_middleware import TenantMiddleware
from app.auth_usermanagement.security.rate_limit_middleware import RateLimitMiddleware
from app.auth_usermanagement.security.security_headers_middleware import SecurityHeadersMiddleware
from app.auth_usermanagement.api import router as auth_router

app = FastAPI(title="Your App")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security middlewares
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(TenantMiddleware)

# Register auth router
app.include_router(auth_router, prefix="/api/auth")

# Your app routers here
# app.include_router(your_router, prefix="/api/your-feature")
```

**3.2 Configure environment variables (`backend/.env`):**

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/yourdb

# Cognito
COGNITO_REGION=eu-west-1
COGNITO_USER_POOL_ID=your-pool-id
COGNITO_CLIENT_ID=your-client-id

# AWS SES
SES_REGION=eu-west-1
SES_SENDER_EMAIL=no-reply@yourdomain.com

# App
FRONTEND_URL=http://localhost:5173
SECRET_KEY=your-secret-key-here
```

**3.3 Create database migrations:**

```bash
# Initialize Alembic (if not already)
alembic init alembic

# Generate migration from auth models
alembic revision --autogenerate -m "add auth tables"

# Apply migration
alembic upgrade head
```

### Step 4: Frontend Integration

**4.1 Update your `main.jsx`:**

```jsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { AuthProvider } from './auth_usermanagement/context/AuthProvider'
import App from './App'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
)
```

**4.2 Update your `App.jsx` with auth routes:**

```jsx
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './auth_usermanagement/hooks/useAuth'
import HomePage from './auth_usermanagement/pages/HomePage'
import AdminDashboard from './auth_usermanagement/components/AdminDashboard'
import AcceptInvitation from './auth_usermanagement/components/AcceptInvitation'

function App() {
  const { user, loading } = useAuth()

  if (loading) {
    return <div>Loading...</div>
  }

  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/callback" element={<div>Processing login...</div>} />
      <Route 
        path="/admin" 
        element={user ? <AdminDashboard /> : <Navigate to="/" />} 
      />
      <Route path="/invite/:token" element={<AcceptInvitation />} />
      {/* Your app routes here */}
    </Routes>
  )
}

export default App
```

**4.3 Configure environment variables (`frontend/.env`):**

```env
VITE_API_BASE_URL=http://localhost:8001
VITE_COGNITO_USER_POOL_ID=your-pool-id
VITE_COGNITO_CLIENT_ID=your-client-id
VITE_COGNITO_DOMAIN=https://your-domain.auth.region.amazoncognito.com
VITE_COGNITO_REDIRECT_URI=http://localhost:5173/callback
VITE_COGNITO_LOGOUT_URI=http://localhost:5173/
```

### Step 5: AWS Cognito Setup

1. **Create Cognito User Pool:**
   - Enable username + email sign-in
   - Configure password policy
   - Enable MFA (optional)

2. **Create App Client:**
   - Enable OAuth 2.0 flows: Authorization code grant
   - Enable PKCE
   - Set callback URLs: `http://localhost:5173/callback`
   - Set logout URLs: `http://localhost:5173/`
   - OAuth scopes: `openid`, `email`, `profile`

3. **Configure Hosted UI Domain:**
   - Create Cognito domain or custom domain
   - Update `VITE_COGNITO_DOMAIN` with domain URL

4. **Configure SES (Email Sending):**
   - Verify sender email in SES
   - Move out of sandbox for production
   - Update `SES_SENDER_EMAIL` in backend `.env`

### Step 6: Database Setup

**Run the RLS migration (if not auto-generated):**

The auth module requires PostgreSQL Row-Level Security. Ensure your database migration includes:

```sql
-- Enable RLS on tenant-scoped tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE invitations ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;

-- Create RLS policies (example for users table)
CREATE POLICY users_tenant_isolation ON users
    USING (
        EXISTS (
            SELECT 1 FROM memberships
            WHERE memberships.user_id = users.id
            AND memberships.tenant_id::text = current_setting('app.current_tenant_id', true)
        )
        OR current_setting('app.bypass_rls', true) = 'true'
    );

-- Repeat for other tables (see alembic migration 0eec64567dac for full reference)
```

### Step 7: Seed Initial Data

**Create your first tenant and admin user:**

```python
# create_initial_tenant.py
import asyncio
from app.auth_usermanagement.services.tenant_service import TenantService
from app.auth_usermanagement.services.user_service import UserService
from app.auth_usermanagement.database import get_db

async def create_initial_setup():
    async for db in get_db():
        # Create tenant
        tenant = await TenantService.create_tenant(
            db=db,
            name="Your Company",
            cognito_user_id="your-cognito-sub-uuid"
        )
        
        # Create admin user
        user = await UserService.get_or_create_user(
            db=db,
            cognito_user_id="your-cognito-sub-uuid",
            email="admin@yourcompany.com",
            is_platform_admin=True
        )
        
        print(f"Created tenant: {tenant.id}")
        print(f"Created user: {user.id}")

if __name__ == "__main__":
    asyncio.run(create_initial_setup())
```

### Step 8: Verify Integration

**Backend checklist:**
- [ ] `uvicorn app.main:app --reload` starts without errors
- [ ] Visit `http://localhost:8000/docs` - Swagger UI shows auth endpoints
- [ ] Database tables created (users, tenants, memberships, invitations, sessions)

**Frontend checklist:**
- [ ] `npm run dev` starts without errors
- [ ] Visit `http://localhost:5173` - landing page renders
- [ ] Click "Sign In" - redirects to Cognito Hosted UI
- [ ] After login - redirects back to `/callback` then to app

**Integration checklist:**
- [ ] User can sign in via Cognito
- [ ] User profile synced to database after first login
- [ ] Admin can access `/admin` dashboard
- [ ] Admin can invite new users
- [ ] Invitation email delivered via SES
- [ ] New user can accept invitation and join tenant

---

## Using Auth Module in Your App

**Protect routes with `useAuth` hook:**

```jsx
import { useAuth } from './auth_usermanagement/hooks/useAuth'

function ProtectedPage() {
  const { user, loading, tenant } = useAuth()

  if (loading) return <div>Loading...</div>
  if (!user) return <div>Please sign in</div>

  return (
    <div>
      <h1>Welcome {user.email}</h1>
      <p>Tenant: {tenant?.name}</p>
    </div>
  )
}
```

**Make authenticated API calls:**

```jsx
import { useAuth } from './auth_usermanagement/hooks/useAuth'
import axios from 'axios'

function MyComponent() {
  const { token } = useAuth()

  const fetchData = async () => {
    const response = await axios.get('/api/your-endpoint', {
      headers: { Authorization: `Bearer ${token}` }
    })
    return response.data
  }

  // ... use fetchData
}
```

**Protect backend endpoints:**

```python
from fastapi import Depends
from app.auth_usermanagement.security.dependencies import (
    require_user,
    require_tenant_admin,
    require_platform_admin
)

@app.get("/api/protected")
async def protected_route(current_user=Depends(require_user)):
    return {"user_id": current_user.id}

@app.post("/api/admin-only")
async def admin_route(current_user=Depends(require_tenant_admin)):
    return {"message": "Admin access granted"}
```

---

## Customization Points

### Adding Custom User Fields

Edit `backend/app/auth_usermanagement/models/user.py`:

```python
class User(Base):
    # ... existing fields ...
    
    # Add your custom fields
    company_name: Mapped[Optional[str]] = mapped_column(String(255))
    phone_number: Mapped[Optional[str]] = mapped_column(String(50))
```

Generate migration: `alembic revision --autogenerate -m "add user custom fields"`

### Extending Roles

Edit `backend/app/auth_usermanagement/models/membership.py`:

```python
# Add new role to enum
role: Mapped[str] = mapped_column(String(50))  # e.g., "admin", "member", "viewer"
```

Update frontend permissions in `frontend/src/auth_usermanagement/constants/permissions.js`

### Custom Email Templates

Edit `backend/app/auth_usermanagement/services/email_service.py`:

Modify `send_invitation_email()` to use your HTML templates.

---

## Troubleshooting

**Issue: "Token verification failed"**
- Check `COGNITO_USER_POOL_ID` and `COGNITO_REGION` match your Cognito pool
- Verify time sync on server (JWT exp/iat validation)

**Issue: "Tenant not found"**
- Ensure user has membership record in database
- Check tenant middleware is registered in `main.py`

**Issue: "RLS policy violation"**
- Verify RLS policies created correctly
- Check `app.current_tenant_id` session variable set by middleware

**Issue: "CORS errors"**
- Update `allow_origins` in CORS middleware
- Check credentials=True is set

**Issue: "Email not sending"**
- Verify SES sender email is verified
- Check SES is out of sandbox (for production)
- Review AWS IAM permissions for SES send access

---

## Production Checklist

- [ ] Use environment-specific `.env` files (dev/staging/prod)
- [ ] Enable HTTPS and update Cognito callback URLs
- [ ] Configure production database with SSL
- [ ] Set strong `SECRET_KEY` for JWT signing
- [ ] Move SES out of sandbox
- [ ] Enable CloudWatch logging for Lambda/SES
- [ ] Set up database backups
- [ ] Configure Cognito MFA (recommended)
- [ ] Review and harden CORS origins
- [ ] Enable rate limiting in production
- [ ] Set up monitoring/alerts for auth failures
- [ ] Review RLS policies for your use case
- [ ] Pen test authentication flow

---

## Support Resources

- Feature documentation: `documents/feature_details.md`
- Cognito setup guide: `documents/cognito_setup.md`
- Test scenarios: `documents/priority2_manual_test_scenarios.md`
- Source repository: `ferrouslabs-auth-system`

---

**Last Updated:** 2026-03-10
**Module Version:** 1.0

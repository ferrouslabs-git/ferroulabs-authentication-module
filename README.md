# auth_usermanagement

Reusable multi-tenant auth and user management module for FastAPI + React applications.

## What It Does

- AWS Cognito PKCE authentication with JWT verification
- Multi-tenant RBAC with three-layer scopes (platform / account / space)
- Invitation lifecycle with hashed tokens and SES email delivery
- Cookie-based refresh tokens with CSRF protection
- Session management with device tracking
- PostgreSQL row-level security for tenant isolation
- Distributed rate limiting on sensitive endpoints
- Audit event logging for all security-relevant actions
- Automated cleanup of expired tokens, invitations, and stale data

## Quick Start

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001

# Frontend
cd frontend
npm install
npm run dev
```

Or with Docker:

```bash
docker compose up --build
```

## Documentation

All detailed documentation lives in [`documents/`](documents/):

| Document | Purpose |
|----------|---------|
| [Setup Guide](documents/setup_guide.md) | Step-by-step integration into a new host project |
| [Agent Reference](documents/agent_reference.md) | AI agent / developer technical reference |
| [Cognito & SSO Guide](documents/cognito_and_sso_guide.md) | AWS Cognito setup and SSO federation planning |
| [Version 1 Report](documents/version_1_fullreport.md) | Full system documentation, security model, and changelog |

## Running Tests

```bash
# Backend (SQLite, fast)
cd backend && pytest -q tests

# PostgreSQL RLS verification
RUN_POSTGRES_RLS_TESTS=1 DATABASE_URL=postgresql://... pytest -q tests/test_row_level_security.py

# Frontend
cd frontend && npx vitest run
```

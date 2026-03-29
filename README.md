# auth_usermanagement

Reusable multi-tenant auth and user management module for FastAPI + React applications.

## What It Does

- AWS Cognito PKCE authentication with JWT verification
- Multi-tenant RBAC with three-layer scopes (platform / account / space)
- Invitation lifecycle with hashed tokens and SES email delivery
- Cookie-based refresh tokens with CSRF protection
- Session management with device tracking
- **Dual-mode authentication**: Cognito Hosted UI (default) or custom login/signup forms (`AUTH_MODE=custom_ui`) with forgot-password support
- PostgreSQL row-level security for tenant isolation
- Space management (sub-tenant grouping within accounts)
- YAML-driven RBAC configuration with customizable roles and permissions
- Distributed rate limiting on sensitive endpoints (PostgreSQL-backed or in-memory fallback)
- Structured JSON logging (auto-configured on module import)
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
| [Host Integration Guide](documents/host_integration_guide.md) | Mapping your domain models to the module — FK patterns, naming, extensions |
| [Agent Reference](documents/agent_reference.md) | AI agent / developer technical reference |
| [Custom UI Guide](documents/custom_ui_integration_guide.md) | Build custom login/signup forms instead of Cognito Hosted UI |
| [Cognito & SSO Guide](documents/cognito_and_sso_guide.md) | AWS Cognito setup and SSO federation planning |
| [Version 1 Report](documents/version_1_fullreport.md) | Full system documentation, security model, and changelog |

## Running Tests

```bash
# Backend (SQLite, fast — 597 tests, 95% coverage)
cd backend && pytest -q tests

# Real Cognito integration tests (requires .env with valid Cognito config + AWS credentials)
RUN_COGNITO_TESTS=1 pytest -q tests/test_cognito_integration.py

# PostgreSQL RLS verification
RUN_POSTGRES_RLS_TESTS=1 DATABASE_URL=postgresql://... pytest -q tests/test_row_level_security.py

# Coverage report
pytest -q tests --cov=app.auth_usermanagement --cov-report=term-missing

# Frontend
cd frontend && npx vitest run
```

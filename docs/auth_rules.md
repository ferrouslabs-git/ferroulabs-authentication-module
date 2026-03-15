# Authentication Rules (Non-Negotiable)

1. Authentication is handled by Amazon Cognito
2. Backend ONLY verifies JWT tokens
3. Backend controls all authorization logic
4. NO passwords stored in local database
5. User identity is Cognito `sub` claim
6. All queries MUST be tenant-scoped

## Host Integration Contract

### Host App Owns
- Database runtime objects: engine, SessionLocal, Base, and get_db
- Shared runtime configuration (including DATABASE_URL)
- Migration execution via host Alembic pipeline
- Final application wiring (middleware + router registration)

### Reusable Auth Module Owns
- Auth domain models, schemas, services, and route handlers
- Auth-specific configuration values (for example Cognito/SES/frontend auth settings)
- Schema and migration assets for the auth domain (execution remains host-owned)

### Boundary Rule
- Reusable module code must not create a second DB runtime in-process.
- Reusable module middleware must not instantiate new DB sessions directly.

## Tenant Request Lifecycle (RLS-Safe)

1. Middleware enforces request prechecks (Authorization header + X-Tenant-ID format) for protected auth routes.
2. Endpoint dependency resolves authenticated user using host-owned get_db.
3. Endpoint dependency validates active membership for requested tenant using that same request DB session.
4. Endpoint dependency sets tenant DB session variables for the same request session.
5. Handler logic executes through the same session path so tenant scope is consistent.

Guardrail:
- Do not add alternate tenant validation paths in middleware or utility code that bypass the dependency-owned request DB session flow.
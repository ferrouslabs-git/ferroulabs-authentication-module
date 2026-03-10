"""
FastAPI app entrypoint for auth module test app.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth_usermanagement.api import router as auth_router
from app.auth_usermanagement.security.rate_limit_middleware import RateLimitMiddleware
from app.auth_usermanagement.security.security_headers_middleware import SecurityHeadersMiddleware
from app.auth_usermanagement.security.tenant_middleware import TenantContextMiddleware

app = FastAPI(title="Auth Sandbox Test")

# CORS for local frontend apps.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware stack: added order means execution order is reversed.
app.add_middleware(TenantContextMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

# Mount auth routes at /auth to match frontend authApi baseURL.
app.include_router(auth_router, prefix="/auth", tags=["auth"])

@app.get("/")
async def root():
    return {"message": "Auth sandbox API"}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "auth-sandbox-test"}

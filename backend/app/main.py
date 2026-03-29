"""
FastAPI app entrypoint for auth module test app.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_host_settings
from app.database import SessionLocal
from app.auth_usermanagement.api import router as auth_router
from app.auth_usermanagement.config import get_settings
from app.auth_usermanagement.security.rate_limit_middleware import RateLimitMiddleware
from app.auth_usermanagement.security.security_headers_middleware import SecurityHeadersMiddleware
from app.auth_usermanagement.security.tenant_middleware import TenantContextMiddleware

app = FastAPI(title="Auth Sandbox Test")
settings = get_settings()
host_settings = get_host_settings()

# CORS is host-owned and environment-configurable.
app.add_middleware(
    CORSMiddleware,
    allow_origins=host_settings.resolved_cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware stack: added order means execution order is reversed.
app.add_middleware(TenantContextMiddleware, auth_prefix=settings.auth_api_prefix)
app.add_middleware(RateLimitMiddleware, auth_prefix=settings.auth_api_prefix, get_db=SessionLocal)
app.add_middleware(SecurityHeadersMiddleware)

# Mount auth routes at the configured auth prefix.
app.include_router(auth_router, prefix=settings.auth_api_prefix, tags=["auth"])

@app.get("/")
async def root():
    return {"message": "Auth sandbox API"}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "auth-sandbox-test"}

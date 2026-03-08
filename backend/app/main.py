"""
Minimal FastAPI app for testing auth module portability.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.auth_usermanagement.api import router as auth_router
from app.auth_usermanagement.security.tenant_middleware import TenantContextMiddleware
from app.auth_usermanagement.security.rate_limit_middleware import RateLimitMiddleware
from app.auth_usermanagement.security.security_headers_middleware import SecurityHeadersMiddleware

app = FastAPI(title="Auth Sandbox Test")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security middleware (order matters: last added = first executed)
app.add_middleware(TenantContextMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

# Auth router
app.include_router(auth_router, prefix="/auth", tags=["auth"])

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "auth-sandbox-test"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

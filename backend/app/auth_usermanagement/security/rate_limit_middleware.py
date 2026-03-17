"""Rate limiting middleware for auth-sensitive endpoints.

Supports both PostgreSQL-backed distributed limiting and in-memory limiting.
"""
from typing import Optional, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from ..config import get_settings
from ..services.rate_limiter_service import RateLimiter, create_rate_limiter


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate-limit auth endpoints by client IP and path.

    Uses PostgreSQL for distributed limiting if get_db is provided,
    otherwise falls back to in-memory limiting for single-process deployments.
    """

    def __init__(
        self,
        app,
        limit: int = 30,
        window_seconds: int = 60,
        auth_prefix: str | None = None,
        rate_limiter: RateLimiter | None = None,
        get_db: Optional[Callable] = None,
    ):
        super().__init__(app)
        self.limit = limit
        self.window_seconds = window_seconds
        settings = get_settings()
        configured_prefix = auth_prefix or settings.auth_api_prefix
        self.auth_prefix = self._normalize_prefix(configured_prefix)

        # Use provided limiter or create one based on config
        if rate_limiter:
            self.rate_limiter = rate_limiter
        else:
            self.rate_limiter = create_rate_limiter(get_db)

        self.protected_routes = {
            f"{self.auth_prefix}/debug-token",
            f"{self.auth_prefix}/sync",
            f"{self.auth_prefix}/invite",
            f"{self.auth_prefix}/invites/accept",
            f"{self.auth_prefix}/token/refresh",
            f"{self.auth_prefix}/cookie/store-refresh",
        }

    @staticmethod
    def _normalize_prefix(prefix: str) -> str:
        cleaned = (prefix or "/auth").strip()
        if not cleaned:
            return "/auth"
        if not cleaned.startswith("/"):
            cleaned = f"/{cleaned}"
        return cleaned.rstrip("/") or "/auth"

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if not self._is_protected_path(path):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        key = f"{client_ip}:{path}"

        if self.rate_limiter.is_rate_limited(key, self.limit, self.window_seconds):
            retry_after = self.window_seconds
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded. Please retry later.",
                    "path": path,
                    "limit": self.limit,
                    "window_seconds": self.window_seconds,
                },
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)

    def _is_protected_path(self, path: str) -> bool:
        if path in self.protected_routes:
            return True

        # Protect plan-compatible invite route: /auth/tenants/{tenant_id}/invite
        return path.startswith(f"{self.auth_prefix}/tenants/") and path.endswith("/invite")

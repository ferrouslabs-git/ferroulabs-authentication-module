"""
Simple in-memory rate limiting middleware for auth-sensitive endpoints.
"""
from collections import defaultdict, deque
from datetime import datetime, timedelta

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from ..config import get_settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate-limit auth endpoints by client IP and path.

    Note: in-memory limiter is acceptable for local/dev and single-process deploys.
    """

    def __init__(self, app, limit: int = 30, window_seconds: int = 60, auth_prefix: str | None = None):
        super().__init__(app)
        self.limit = limit
        self.window = timedelta(seconds=window_seconds)
        self.hits = defaultdict(deque)
        settings = get_settings()
        configured_prefix = auth_prefix or settings.auth_api_prefix
        self.auth_prefix = self._normalize_prefix(configured_prefix)

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
        now = datetime.utcnow()
        q = self.hits[key]

        while q and (now - q[0]) > self.window:
            q.popleft()

        if len(q) >= self.limit:
            retry_after = int(self.window.total_seconds())
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded. Please retry later.",
                    "path": path,
                    "limit": self.limit,
                    "window_seconds": int(self.window.total_seconds()),
                },
                headers={"Retry-After": str(retry_after)},
            )

        q.append(now)
        return await call_next(request)

    def _is_protected_path(self, path: str) -> bool:
        if path in self.protected_routes:
            return True

        # Protect plan-compatible invite route: /auth/tenants/{tenant_id}/invite
        return path.startswith(f"{self.auth_prefix}/tenants/") and path.endswith("/invite")

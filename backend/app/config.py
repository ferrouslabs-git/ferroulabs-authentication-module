"""Host application settings and compatibility exports.

Host app owns root settings such as CORS configuration.
Auth-module settings remain available via compatibility exports.
"""
from functools import lru_cache
import os

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.auth_usermanagement.config import Settings, get_settings


class HostSettings(BaseSettings):
    """Host-owned application settings."""

    cors_allowed_origins: str = os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:3000,http://localhost:5173",
    )

    @property
    def resolved_cors_allowed_origins(self) -> list[str]:
        """Return normalized list of allowed CORS origins."""
        return [
            origin.strip()
            for origin in self.cors_allowed_origins.split(",")
            if origin.strip()
        ]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache()
def get_host_settings() -> HostSettings:
    """Return cached host settings instance."""
    return HostSettings()


__all__ = ["Settings", "get_settings", "HostSettings", "get_host_settings"]

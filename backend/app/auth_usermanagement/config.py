"""
Settings for the auth_usermanagement module.

This file should define module-specific settings only.
Host apps own shared runtime settings (for example DATABASE_URL).
"""
import os
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Auth module settings loaded from environment variables."""

    # Cognito
    cognito_region: str = os.getenv("COGNITO_REGION", "eu-west-1")
    cognito_user_pool_id: str = os.getenv("COGNITO_USER_POOL_ID", "")
    cognito_client_id: str = os.getenv("COGNITO_CLIENT_ID", "")
    cognito_domain: str = os.getenv("COGNITO_DOMAIN", "")

    # SES (optional)
    ses_region: str = os.getenv("SES_REGION", "")
    ses_sender_email: str = os.getenv("SES_SENDER_EMAIL", "")

    # Frontend
    frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:5173")
    cookie_secure: bool = os.getenv("COOKIE_SECURE", "true").lower() == "true"

    # Auth config (v3.0)
    auth_config_path: str = os.getenv(
        "AUTH_CONFIG_PATH",
        os.path.join(os.path.dirname(__file__), "auth_config.yaml"),
    )

    # Portability
    auth_namespace: str = os.getenv("AUTH_NAMESPACE", "authum")
    auth_api_prefix: str = os.getenv("AUTH_API_PREFIX", "/auth")
    auth_cookie_name: str = os.getenv("AUTH_COOKIE_NAME", "")
    auth_cookie_path: str = os.getenv("AUTH_COOKIE_PATH", "")
    auth_csrf_cookie_name: str = os.getenv("AUTH_CSRF_COOKIE_NAME", "")

    @property
    def resolved_auth_cookie_name(self) -> str:
        if self.auth_cookie_name:
            return self.auth_cookie_name
        return f"{self.auth_namespace}_refresh_token"

    @property
    def resolved_auth_cookie_path(self) -> str:
        if self.auth_cookie_path:
            return self.auth_cookie_path
        return f"{self.auth_api_prefix.rstrip('/')}/token"

    @property
    def resolved_auth_csrf_cookie_name(self) -> str:
        if self.auth_csrf_cookie_name:
            return self.auth_csrf_cookie_name
        return f"{self.auth_namespace}_csrf_token"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()

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

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()

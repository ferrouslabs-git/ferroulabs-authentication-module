"""
Settings for the auth_usermanagement module.

Keeping settings local to the module removes hard coupling to a host app package
and makes the module easier to reuse in standalone services.
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

    # Database
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/trustos",
    )

    # SES (optional)
    ses_region: str = os.getenv("SES_REGION", "")
    ses_sender_email: str = os.getenv("SES_SENDER_EMAIL", "")

    # Frontend
    frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:5173")

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()

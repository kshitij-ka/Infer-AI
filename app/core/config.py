"""
Application configuration.

Settings are loaded from environment variables or a .env file using
pydantic-settings. No default values exist for secrets, so a missing
required setting fails at import time instead of falling back to an
insecure default.
"""
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MIN_JWT_SECRET_LENGTH = 32


class Settings(BaseSettings):
    """
    Holds every environment driven configuration value the application
    needs: app metadata, JWT signing parameters, database and Redis
    connection strings, the LLM provider credentials, and rate limit
    tuning.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "ai-qa-api"
    environment: str = "development"
    log_level: str = "INFO"

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    database_url: str
    redis_url: str

    groq_api_key: str
    groq_model: str = "llama-3.1-8b-instant"
    llm_timeout_seconds: int = 15
    llm_max_retries: int = 3

    rate_limit_per_minute: int = 60
    login_rate_limit_per_minute: int = 10
    cache_ttl_seconds: int = 300
    cors_allowed_origins: str = ""
    max_request_body_bytes: int = 65536

    @field_validator("jwt_secret_key")
    @classmethod
    def jwt_secret_key_must_be_long_enough(cls, value: str) -> str:
        """
        Rejects a JWT secret shorter than MIN_JWT_SECRET_LENGTH
        characters. A short secret is within reach of offline brute
        force against a captured token signature.

        Args:
            value: the raw jwt_secret_key value read from the
                environment.

        Returns:
            The same value, unchanged, once it passes the length
            check.
        """
        if len(value) < MIN_JWT_SECRET_LENGTH:
            raise ValueError(
                f"jwt_secret_key must be at least {MIN_JWT_SECRET_LENGTH} "
                "characters long"
            )
        return value


@lru_cache
def get_settings() -> Settings:
    """
    Returns a cached Settings instance. Cached so environment variables
    are read once per process rather than on every request.

    Returns:
        The process wide Settings instance.
    """
    return Settings()

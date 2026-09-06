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
MIN_MAX_REQUEST_BODY_BYTES = 1024


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
    ip_only_login_rate_limit_per_minute: int = 30
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
                f"jwt_secret_key must be at least {MIN_JWT_SECRET_LENGTH} " "characters long"
            )
        return value

    @field_validator("cors_allowed_origins")
    @classmethod
    def cors_allowed_origins_must_not_contain_wildcard(cls, value: str) -> str:
        """
        Rejects a literal "*" entry in cors_allowed_origins. The app
        registers CORSMiddleware with allow_credentials=True, and
        Starlette treats an origin list containing "*" as reflect any
        origin, which combined with allow_credentials=True would let
        any external site make credentialed cross origin requests and
        read responses.

        Args:
            value: the raw cors_allowed_origins value read from the
                environment, a comma separated list of origins.

        Returns:
            The same value, unchanged, once it passes the check.
        """
        entries = [entry.strip() for entry in value.split(",")]
        if "*" in entries:
            raise ValueError(
                "cors_allowed_origins must not contain a literal '*' entry, "
                "since allow_credentials=True combined with a wildcard "
                "origin allows any site to make credentialed requests"
            )
        return value

    @field_validator("max_request_body_bytes")
    @classmethod
    def max_request_body_bytes_must_have_a_sane_floor(cls, value: int) -> int:
        """
        Rejects a max_request_body_bytes value below
        MIN_MAX_REQUEST_BODY_BYTES. A zero or negative value would be
        silently accepted otherwise, and a value smaller than a bare
        empty JSON object would reject essentially all legitimate
        payloads.

        Args:
            value: the raw max_request_body_bytes value read from the
                environment.

        Returns:
            The same value, unchanged, once it passes the floor check.
        """
        if value < MIN_MAX_REQUEST_BODY_BYTES:
            raise ValueError(
                f"max_request_body_bytes must be at least " f"{MIN_MAX_REQUEST_BODY_BYTES} bytes"
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

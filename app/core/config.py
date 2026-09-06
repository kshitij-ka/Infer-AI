from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
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


@lru_cache
def get_settings() -> Settings:
    return Settings()

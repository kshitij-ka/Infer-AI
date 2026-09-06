import os

import pytest
from pydantic import ValidationError


def test_settings_rejects_short_jwt_secret(monkeypatch):
    """
    A JWT secret under 32 characters must be rejected at settings
    construction time, since a short secret is brute forceable and
    the failure should happen at startup, not silently in production.
    """
    monkeypatch.setenv("JWT_SECRET_KEY", "too-short")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings()


def test_settings_accepts_long_jwt_secret(monkeypatch):
    """A JWT secret of 32 or more characters is accepted."""
    monkeypatch.setenv("JWT_SECRET_KEY", "a" * 32)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    from app.core.config import Settings

    settings = Settings()
    assert settings.jwt_secret_key == "a" * 32


def test_settings_rejects_wildcard_cors_origin(monkeypatch):
    """
    A literal '*' entry in CORS_ALLOWED_ORIGINS must be rejected at
    settings construction time, since the app pairs CORSMiddleware
    with allow_credentials=True and a wildcard origin combined with
    credentials allows any external site to make credentialed cross
    origin requests.
    """
    monkeypatch.setenv("JWT_SECRET_KEY", "a" * 32)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "*")

    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings()


def test_settings_rejects_wildcard_among_other_cors_origins(monkeypatch):
    """
    A '*' entry must be rejected even when it appears alongside other,
    legitimate origins in the comma separated list, not only when it
    is the sole entry.
    """
    monkeypatch.setenv("JWT_SECRET_KEY", "a" * 32)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://app.example.com,*")

    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings()


def test_settings_accepts_non_wildcard_cors_origins(monkeypatch):
    """
    A normal comma separated list of concrete origins, with no literal
    '*' entry, is accepted. A dangling wildcard token used within a
    real origin such as 'https://*.example.com' is a different, more
    permissive pattern that the app's exact string list based origin
    matching does not use, so only a whole-entry '*' is rejected.
    """
    monkeypatch.setenv("JWT_SECRET_KEY", "a" * 32)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://app.example.com,https://admin.example.com")

    from app.core.config import Settings

    settings = Settings()
    assert settings.cors_allowed_origins == "https://app.example.com,https://admin.example.com"

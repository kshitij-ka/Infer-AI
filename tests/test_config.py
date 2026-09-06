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

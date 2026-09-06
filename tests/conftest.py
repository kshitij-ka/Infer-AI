import os

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-with-minimum-length-required")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("GROQ_API_KEY", "test-key")

import fakeredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_redis
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.models.user import Role, User
from app.services.llm_client import LLMResult, get_llm_client

TEST_ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=TEST_ENGINE)


def _override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def fake_llm():
    from unittest.mock import MagicMock

    mock_client = MagicMock()
    mock_client.ask.return_value = LLMResult(
        answer="mocked answer", prompt_tokens=5, completion_tokens=10
    )
    return mock_client


@pytest.fixture
def client(fake_llm):
    from app.main import app

    Base.metadata.create_all(bind=TEST_ENGINE)
    fake_redis = fakeredis.FakeStrictRedis(decode_responses=True)

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis] = lambda: fake_redis
    app.dependency_overrides[get_llm_client] = lambda: fake_llm

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=TEST_ENGINE)


@pytest.fixture
def test_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def seed_user(test_db):
    def _seed(username="alice", password="password123", role=Role.user):
        user = User(username=username, hashed_password=hash_password(password), role=role)
        test_db.add(user)
        test_db.commit()
        return user

    return _seed

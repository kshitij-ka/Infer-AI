"""
Fixtures for the integration test tier.

Unlike the unit test tier (tests/conftest.py), these tests run
against the real Postgres and Redis containers defined in
docker-compose.yml, with a mocked LLM client (a real LLM call would
be slow, flaky, and cost money, and proves nothing about database or
Redis correctness). Run `docker compose up -d postgres redis` before
running this test tier.
"""
import os
import uuid
from unittest.mock import MagicMock

import pytest
import redis as redis_module
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Pytest collects tests/conftest.py (the unit tier's conftest) even when
# only tests/integration/ is passed on the command line, since it walks
# every conftest.py between rootdir and the collected path. That file
# already sets these same variables to sqlite/fakeredis defaults via
# os.environ.setdefault, and it is imported before this file because it
# sits higher in the directory tree. A setdefault here would therefore be
# a no-op and silently point these tests at sqlite instead of Postgres, so
# these are direct assignments to force the real containers regardless of
# import order.
os.environ["JWT_SECRET_KEY"] = "integration-test-secret-key-1234567890"
os.environ["DATABASE_URL"] = "postgresql+psycopg2://postgres:postgres@localhost:5432/qa_api"
os.environ["REDIS_URL"] = "redis://localhost:6379/1"
os.environ["GROQ_API_KEY"] = "integration-test-key"

from app.api.deps import get_redis
from app.db.base import Base
from app.db.session import get_db
from app.services.llm_client import LLMResult, get_llm_client

# Importing app.main registers every model (User, ChatLog) on Base.metadata
# via the route import chain, which must happen before integration_engine
# calls Base.metadata.create_all below. Without this import, only whichever
# model tests/conftest.py happens to import is registered, and create_all
# silently creates an incomplete schema (missing the chat_logs table).
import app.main  # noqa: F401


@pytest.fixture(scope="session")
def integration_engine():
    """
    Creates a SQLAlchemy engine against the real Postgres container,
    session scoped since connecting is comparatively expensive and
    the schema only needs to be created once per test run.
    """
    engine = create_engine(os.environ["DATABASE_URL"])
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def integration_db(integration_engine):
    """
    Yields a database session against the real Postgres container,
    and truncates every table after the test so tests do not leak
    state into each other.
    """
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=integration_engine)
    session = session_local()
    try:
        yield session
    finally:
        session.close()
        with integration_engine.begin() as connection:
            for table in reversed(Base.metadata.sorted_tables):
                connection.execute(table.delete())


@pytest.fixture
def integration_redis():
    """
    Yields a real Redis client against database index 1 (separate
    from the default index 0 a developer might be using locally),
    and flushes that database after the test.
    """
    client = redis_module.from_url(os.environ["REDIS_URL"], decode_responses=True)
    yield client
    client.flushdb()


@pytest.fixture
def integration_fake_llm():
    """A mocked LLM client, since integration tests should not make real LLM calls."""
    mock_client = MagicMock()
    mock_client.ask.return_value = LLMResult(answer="integration test answer", prompt_tokens=3, completion_tokens=7)
    return mock_client


@pytest.fixture
def integration_client(integration_engine, integration_db, integration_redis, integration_fake_llm):
    """
    A TestClient wired to the real Postgres and Redis containers, via
    dependency overrides on the same get_db and get_redis dependency
    functions the unit test tier overrides, and a mocked LLM client.
    """
    from app.main import app

    def override_get_db():
        yield integration_db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = lambda: integration_redis
    app.dependency_overrides[get_llm_client] = lambda: integration_fake_llm

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def _skip_if_containers_unreachable():
    """
    Raises pytest.skip with a clear message if Postgres or Redis are
    not reachable, so running this test tier without Docker running
    gives an actionable message instead of a confusing connection
    error deep in a fixture.
    """
    try:
        client = redis_module.from_url(os.environ["REDIS_URL"])
        client.ping()
    except Exception as exc:
        pytest.skip(f"Redis is not reachable, run docker compose up -d redis first: {exc}")

    try:
        engine = create_engine(os.environ["DATABASE_URL"])
        with engine.connect():
            pass
    except Exception as exc:
        pytest.skip(f"Postgres is not reachable, run docker compose up -d postgres first: {exc}")


@pytest.fixture(autouse=True, scope="session")
def _require_containers():
    """Skips the entire integration tier up front if containers are not reachable."""
    _skip_if_containers_unreachable()

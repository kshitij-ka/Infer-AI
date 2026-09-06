"""
Tests for scripts/seed_admin.py.

The interesting case here is not the normal, non-concurrent path (an
existence check finding no user, then a plain insert), it is the race
where two concurrent invocations of the script both pass the existence
check before either commits. A real concurrency race is impractical to
reproduce in a simple test, so instead these tests simulate the race
having already happened: a conflicting username exists in the database
at commit time even though the script's own existence check did not
see it (because, in the test, the existence check is bypassed for this
scenario). This exercises exactly the code path that matters: the
IntegrityError handling around db.commit.
"""
import os

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-with-minimum-length-required")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("GROQ_API_KEY", "test-key")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.db.base import Base
from app.models.user import Role, User

TEST_ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=TEST_ENGINE)


@pytest.fixture
def seed_admin_module(monkeypatch):
    """
    Imports scripts.seed_admin with its module level SessionLocal
    replaced by a SessionLocal bound to an isolated in-memory test
    database, so the script under test never touches the real
    database configured by DATABASE_URL.
    """
    import scripts.seed_admin as seed_admin_module

    Base.metadata.create_all(bind=TEST_ENGINE)
    monkeypatch.setattr(seed_admin_module, "SessionLocal", TestSessionLocal)
    yield seed_admin_module
    Base.metadata.drop_all(bind=TEST_ENGINE)


def test_seed_admin_creates_user_when_none_exists(seed_admin_module, monkeypatch, capsys):
    """The normal, non-concurrent case still creates the admin user and prints a success message."""
    monkeypatch.setenv("ADMIN_USERNAME", "newadmin")
    monkeypatch.setenv("ADMIN_PASSWORD", "adminpass123")

    seed_admin_module.seed_admin()

    captured = capsys.readouterr()
    assert "Created admin user: newadmin" in captured.out

    db = TestSessionLocal()
    try:
        user = db.query(User).filter(User.username == "newadmin").first()
        assert user is not None
        assert user.role == Role.admin
    finally:
        db.close()


def test_seed_admin_exits_cleanly_when_existence_check_finds_duplicate(
    seed_admin_module, monkeypatch, capsys
):
    """
    The normal, non-concurrent duplicate detection path: a user with
    the requested username already exists and the existence check
    finds it, so the script exits 1 with the friendly message before
    ever attempting an insert.
    """
    db = TestSessionLocal()
    try:
        db.add(User(username="dupe", hashed_password=hash_password("whatever123"), role=Role.admin))
        db.commit()
    finally:
        db.close()

    monkeypatch.setenv("ADMIN_USERNAME", "dupe")
    monkeypatch.setenv("ADMIN_PASSWORD", "adminpass123")

    with pytest.raises(SystemExit) as exc_info:
        seed_admin_module.seed_admin()

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "User dupe already exists" in captured.err


def test_seed_admin_handles_integrity_error_from_concurrent_race(
    seed_admin_module, monkeypatch, capsys
):
    """
    Simulates the actual race: another process's insert lands in the
    database after this script's existence check already ran (and saw
    nothing), so the conflict only surfaces when this script tries to
    commit its own insert. The fix under test is that this raises
    IntegrityError, which seed_admin catches, rolling back and exiting
    with exactly the same message and exit code as the ordinary,
    non-concurrent duplicate detection path, instead of an unhandled
    crash or a silently created duplicate admin.

    The existence check itself is bypassed here (monkeypatched to
    always return None) specifically to model the race window where
    the check ran before the conflicting row existed, so the only way
    the duplicate can be caught is the commit-time IntegrityError
    handling.
    """
    username = "raceadmin"

    db = TestSessionLocal()
    try:
        db.add(User(username=username, hashed_password=hash_password("firstpass123"), role=Role.admin))
        db.commit()
        original_password_hash = (
            db.query(User).filter(User.username == username).first().hashed_password
        )
    finally:
        db.close()

    class _NoneFoundQuery:
        """A query stand-in whose filter/first chain always reports no existing user, modeling the race window where the existence check ran before the conflicting row existed."""

        def filter(self, *args, **kwargs):
            return self

        def first(self):
            return None

    class _RaceSimulatingSession(TestSessionLocal.class_):
        """A session whose query(User) always reports no match, so the only place a pre-existing duplicate can be caught is the commit time IntegrityError handling."""

        def query(self, entity, *args, **kwargs):
            if entity is User:
                return _NoneFoundQuery()
            return super().query(entity, *args, **kwargs)

    monkeypatch.setattr(
        seed_admin_module,
        "SessionLocal",
        sessionmaker(autocommit=False, autoflush=False, bind=TEST_ENGINE, class_=_RaceSimulatingSession),
    )

    monkeypatch.setenv("ADMIN_USERNAME", username)
    monkeypatch.setenv("ADMIN_PASSWORD", "secondpass123")

    with pytest.raises(SystemExit) as exc_info:
        seed_admin_module.seed_admin()

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert f"User {username} already exists" in captured.err

    db = TestSessionLocal()
    try:
        matching_users = db.query(User).filter(User.username == username).all()
        assert len(matching_users) == 1
        assert matching_users[0].hashed_password == original_password_hash
    finally:
        db.close()

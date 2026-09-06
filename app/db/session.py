"""
Database engine and session factory.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """
    FastAPI dependency that yields a database session and always
    closes it afterward, even if the request raised an exception.

    Yields:
        A SQLAlchemy Session bound to the configured database.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

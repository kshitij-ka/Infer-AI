"""
Shared SQLAlchemy declarative base, imported by every model and by
Alembic so migrations see every table.
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """The declarative base every model inherits from."""

    pass

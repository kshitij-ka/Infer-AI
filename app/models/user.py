"""
User model and role enum.
"""

import enum
import uuid

from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Role(str, enum.Enum):
    """
    The three roles this application recognizes. Admin manages users
    and configuration and can access metrics. User can call the chat
    endpoint. Readonly can access permitted reports and data but is
    blocked from the chat endpoint.
    """

    admin = "admin"
    user = "user"
    readonly = "readonly"


class User(Base):
    """
    A registered user. Passwords are stored as a bcrypt hash, never
    in plain text. A user's role determines what routes they can
    call, enforced through the require_role dependency.
    """

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.user, nullable=False)

"""
Request and response models for admin only user management routes.
"""

from pydantic import BaseModel, Field

from app.models.user import Role


class CreateUserRequest(BaseModel):
    """The payload an admin submits to create a new user."""

    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    role: Role = Role.user


class CreateUserResponse(BaseModel):
    """
    The response returned after creating a user. Contains no
    password or hash, since this response is not a place secrets
    should ever appear.
    """

    id: str
    username: str
    role: Role

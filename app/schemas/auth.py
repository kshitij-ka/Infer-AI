"""
Request and response models for the login route.
"""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """The submitted username and password."""

    username: str = Field(max_length=64)
    password: str = Field(max_length=128)


class LoginResponse(BaseModel):
    """The issued JWT and its type, always "bearer"."""

    access_token: str
    token_type: str = "bearer"

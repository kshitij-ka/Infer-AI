"""
Request and response models for the login route.
"""
from pydantic import BaseModel


class LoginRequest(BaseModel):
    """The submitted username and password."""

    username: str
    password: str


class LoginResponse(BaseModel):
    """The issued JWT and its type, always "bearer"."""

    access_token: str
    token_type: str = "bearer"

"""
Admin only user management routes.

There is no open self service registration endpoint in this
application. New users are provisioned either by an admin through
this route, or by the one time seed script (scripts/seed_admin.py)
for the very first admin account, since an admin only endpoint has
no way to create the first admin.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_role
from app.core.security import hash_password
from app.models.user import Role, User
from app.schemas.admin import CreateUserRequest, CreateUserResponse

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/users", response_model=CreateUserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: CreateUserRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role(Role.admin)),
) -> CreateUserResponse:
    """
    Creates a new user with the given username, password, and role.
    Restricted to admin role callers.

    Args:
        payload: the username, password, and role for the new user.
        db: the database session dependency.
        _admin: the authenticated admin user making the request; not
            used beyond the role check, since the created user is
            not tied to the creating admin's identity.

    Returns:
        A CreateUserResponse describing the created user.

    Raises:
        HTTPException: 409 if the username is already taken.
    """
    user = User(
        username=payload.username,
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as err:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        ) from err

    db.refresh(user)
    return CreateUserResponse(id=user.id, username=user.username, role=user.role)

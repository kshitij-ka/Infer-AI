"""
One time script to create the first admin user.

Run this once against a fresh database, since there is no other way
to create the first admin (the admin creation API route itself
requires an existing admin to call it). Reads credentials from the
ADMIN_USERNAME and ADMIN_PASSWORD environment variables rather than
command line arguments, since arguments are visible in process
listings and shell history on a shared machine.

Usage:
    ADMIN_USERNAME=admin ADMIN_PASSWORD=change-me python -m scripts.seed_admin
"""
import os
import sys

from sqlalchemy.exc import IntegrityError

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import Role, User


def seed_admin() -> None:
    """
    Reads ADMIN_USERNAME and ADMIN_PASSWORD from the environment and
    creates an admin user with those credentials, if no user with
    that username already exists.

    The existence check below is a fast path for the common,
    non-concurrent case only. It is not what actually prevents
    duplicate admins: two concurrent invocations of this script (for
    example from a CI/CD retry or a Kubernetes Job restart) can both
    pass the existence check before either commits. The database's
    unique constraint on username is the real race-safe guard, so the
    db.add/db.commit below is wrapped in a try/except for
    IntegrityError, matching the same pattern already used in
    app/api/routes/admin.py's create_user route. This keeps the
    script's observable behavior identical in the normal case (same
    message, same exit code) while also closing the race in the
    concurrent case, instead of crashing with an unhandled
    IntegrityError or silently creating a second admin account.

    Exits with a non zero status and prints an error if the required
    environment variables are missing, if the username already
    exists, or if the password is shorter than 8 characters.
    """
    username = os.environ.get("ADMIN_USERNAME")
    password = os.environ.get("ADMIN_PASSWORD")

    if not username or not password:
        print("ADMIN_USERNAME and ADMIN_PASSWORD must both be set", file=sys.stderr)
        sys.exit(1)

    if len(password) < 8:
        print("ADMIN_PASSWORD must be at least 8 characters", file=sys.stderr)
        sys.exit(1)

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == username).first()
        if existing is not None:
            print(f"User {username} already exists", file=sys.stderr)
            sys.exit(1)

        admin_user = User(
            username=username,
            hashed_password=hash_password(password),
            role=Role.admin,
        )
        db.add(admin_user)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            print(f"User {username} already exists", file=sys.stderr)
            sys.exit(1)
        print(f"Created admin user: {username}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_admin()

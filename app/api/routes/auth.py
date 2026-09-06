"""
Authentication routes.

Exposes the login endpoint that exchanges a username and password
for a JWT. Login attempts are rate limited per username and client
IP combined, so an attacker cannot brute force one account from one
IP without being blocked, and cannot bypass the limit by rotating
usernames from a single IP either, since the chat endpoint's rate
limiter and this one are independent per key.
"""
import hashlib

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_redis
from app.core.config import get_settings
from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse
from app.services.cache import is_rate_limited

router = APIRouter(prefix="/auth", tags=["auth"])


def _build_login_rate_limit_key(username: str, client_ip: str) -> str:
    """
    Builds a rate limit key for a username and client IP pair that
    cannot collide across different pairs. Username is an unconstrained
    string, so concatenating it with the IP using a plain separator
    would let a crafted username containing that separator alias onto
    another user's key. Hashing each component separately with a fixed
    length digest before joining them removes that ambiguity, since
    the digest of one component can never be mistaken for a boundary
    inside the other.

    Args:
        username: the submitted login username, untrusted and
            unconstrained in content.
        client_ip: the client IP address read from the request.

    Returns:
        A deterministic rate limit key string unique to this
        username and client IP combination.
    """
    username_digest = hashlib.sha256(username.encode("utf-8")).hexdigest()
    ip_digest = hashlib.sha256(client_ip.encode("utf-8")).hexdigest()
    return f"login:{username_digest}:{ip_digest}"


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
    redis_client=Depends(get_redis),
) -> LoginResponse:
    """
    Verifies a username and password, and if valid, returns a signed
    JWT carrying the username and role.

    Args:
        payload: the submitted username and password.
        request: the incoming request, used to read the client IP
            for rate limiting.
        db: the database session dependency.
        redis_client: the Redis client dependency, used for rate
            limiting.

    Returns:
        A LoginResponse containing the access token.

    Raises:
        HTTPException: 429 if the rate limit for this username and IP
            combination is exceeded, 401 if the credentials are
            invalid.
    """
    settings = get_settings()
    client_ip = request.client.host if request.client else "unknown"
    rate_limit_key = _build_login_rate_limit_key(payload.username, client_ip)

    if is_rate_limited(
        redis_client,
        key=rate_limit_key,
        limit_per_minute=settings.login_rate_limit_per_minute,
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts, please try again later",
        )

    user = db.query(User).filter(User.username == payload.username).first()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    token = create_access_token(subject=user.username, role=user.role.value)
    return LoginResponse(access_token=token)

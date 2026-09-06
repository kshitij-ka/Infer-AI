"""
Authentication routes.

Exposes the login endpoint that exchanges a username and password
for a JWT. Login attempts are rate limited per username and client
IP combined, so an attacker cannot brute force one account from one
IP without being blocked, and cannot bypass the limit by rotating
usernames from a single IP either, since the chat endpoint's rate
limiter and this one are independent per key.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_redis
from app.core.config import get_settings
from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse
from app.services.cache import build_rate_limit_key, is_rate_limited

router = APIRouter(prefix="/auth", tags=["auth"])


def _build_login_rate_limit_key(username: str, client_ip: str) -> str:
    """
    Builds a rate limit key for a username and client IP pair, using
    the shared build_rate_limit_key helper under the "login" namespace
    so this key can never collide with a key built under any other
    namespace ("chat", "loginip", or any future one), no matter what
    characters the username or IP contain.

    Args:
        username: the submitted login username, untrusted and
            unconstrained in content.
        client_ip: the client IP address read from the request.

    Returns:
        A deterministic rate limit key string unique to this
        username and client IP combination.
    """
    return build_rate_limit_key("login", username, client_ip)


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

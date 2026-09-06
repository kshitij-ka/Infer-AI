from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    # passlib ships no type stubs, so CryptContext.hash is typed Any;
    # its actual return type is always str.
    return _pwd_context.hash(password)  # type: ignore[no-any-return]


def verify_password(plain_password: str, hashed_password: str) -> bool:
    # passlib ships no type stubs, so CryptContext.verify is typed Any;
    # its actual return type is always bool.
    return _pwd_context.verify(plain_password, hashed_password)  # type: ignore[no-any-return]


def create_access_token(subject: str, role: str) -> str:
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": subject, "role": role, "exp": expire}
    # python-jose ships no type stubs, so jwt.encode is typed Any; its
    # actual return type is always str.
    return jwt.encode(  # type: ignore[no-any-return]
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    try:
        # python-jose ships no type stubs, so jwt.decode is typed Any;
        # its actual return type is always dict.
        return jwt.decode(  # type: ignore[no-any-return]
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
    except JWTError as exc:
        raise ValueError("Invalid or expired token") from exc

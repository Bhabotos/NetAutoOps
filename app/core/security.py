from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import settings


class InvalidTokenError(Exception):
    """Raised when a bearer token is missing, malformed, expired, or has a bad signature."""


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    """Issue a JWT for `subject` (the username). Deliberately carries no role
    claim -- app/api/deps.get_current_user always re-reads role/is_active
    from the database so a role change or deactivation takes effect
    immediately rather than waiting out the token's lifetime."""
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str:
    """Return the username (the `sub` claim) from a valid token."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.InvalidTokenError as exc:
        raise InvalidTokenError("Invalid or expired token") from exc

    username = payload.get("sub")
    if not username:
        raise InvalidTokenError("Token missing subject claim")
    return username

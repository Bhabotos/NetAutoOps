from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import InvalidTokenError, decode_access_token
from app.models.user import User, UserRole
from app.services.user_service import get_user_by_username

security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)

ROLE_LEVEL = {UserRole.VIEWER: 0, UserRole.OPERATOR: 1, UserRole.ADMIN: 2}


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the bearer token to a User, always re-reading role/is_active
    from the database (the token itself carries no role claim) so a role
    change or deactivation takes effect on the very next request."""
    try:
        username = decode_access_token(credentials.credentials)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = get_user_by_username(db, username)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_security),
    db: Session = Depends(get_db),
) -> User | None:
    """Like get_current_user, but returns None instead of 401ing when no
    Authorization header was sent at all. A header that IS present but
    invalid/expired still raises 401 -- only a missing header is tolerated.
    Used solely by POST /auth/register to support the bootstrap (first
    account, no token yet) case while still requiring a valid admin token
    for every registration after that."""
    if credentials is None:
        return None
    return get_current_user(credentials=credentials, db=db)


def require_role(minimum: UserRole):
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if ROLE_LEVEL[current_user.role] < ROLE_LEVEL[minimum]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires '{minimum.value}' role or higher",
            )
        return current_user

    return dependency


require_operator = require_role(UserRole.OPERATOR)
require_admin = require_role(UserRole.ADMIN)

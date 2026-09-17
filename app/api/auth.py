from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.auth_schemas import LoginRequest, Token, UserCreate, UserResponse, UserUpdate
from app.api.deps import ROLE_LEVEL, get_current_user, get_optional_current_user, require_admin
from app.core.database import get_db
from app.core.security import create_access_token
from app.models.user import User, UserRole
from app.services import user_service
from app.services.user_service import (
    EmailTakenError,
    InvalidCredentialsError,
    UserNotFoundError,
    UsernameTakenError,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    """Bootstrap rule: if no users exist yet, registration is open (no token
    needed) and the new account is forced to 'admin' regardless of the
    requested role -- this is how the very first account gets created. Once
    any user exists, an admin token is required, and the requested role is
    honored."""
    bootstrap = not user_service.users_exist(db)

    if not bootstrap:
        if current_user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if ROLE_LEVEL[current_user.role] < ROLE_LEVEL[UserRole.ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Requires 'admin' role or higher",
            )

    try:
        return user_service.create_user(db, user_in, force_admin=bootstrap)
    except (UsernameTakenError, EmailTakenError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.post("/login", response_model=Token)
def login(credentials: LoginRequest, db: Session = Depends(get_db)):
    try:
        user = user_service.authenticate_user(db, credentials.username, credentials.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    return Token(access_token=create_access_token(subject=user.username))


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/users", response_model=list[UserResponse])
def list_users(db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    return user_service.list_users(db)


@router.patch("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    try:
        return user_service.update_user(db, user_id, user_in)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

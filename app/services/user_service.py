from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.auth_schemas import UserCreate, UserUpdate
from app.core.security import hash_password, verify_password
from app.models.user import User, UserRole
from app.utils.logger import get_logger

logger = get_logger(__name__)


class UsernameTakenError(Exception):
    """Raised when a user with the given username already exists."""


class EmailTakenError(Exception):
    """Raised when a user with the given email already exists."""


class InvalidCredentialsError(Exception):
    """Raised when a login attempt fails, for any reason (unknown username,
    wrong password, or an inactive account) -- deliberately generic so the
    API never reveals which part of the login was wrong."""


class UserNotFoundError(Exception):
    """Raised when a user cannot be found by id."""


def create_user(db: Session, user_in: UserCreate, *, force_admin: bool = False) -> User:
    if db.query(User).filter(User.username == user_in.username).first():
        raise UsernameTakenError(f"Username '{user_in.username}' is already taken")
    if db.query(User).filter(User.email == user_in.email).first():
        raise EmailTakenError(f"Email '{user_in.email}' is already registered")

    user = User(
        username=user_in.username,
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
        role=UserRole.ADMIN if force_admin else user_in.role,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise UsernameTakenError(f"Username '{user_in.username}' is already taken")
    db.refresh(user)
    logger.info("Created user id=%s username=%s role=%s", user.id, user.username, user.role)
    return user


def authenticate_user(db: Session, username: str, password: str) -> User:
    user = db.query(User).filter(User.username == username).first()
    if user is None or not user.is_active or not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError("Invalid username or password")
    return user


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.query(User).filter(User.username == username).first()


def list_users(db: Session) -> list[User]:
    return db.query(User).order_by(User.id).all()


def get_user(db: Session, user_id: int) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise UserNotFoundError(f"User with id {user_id} not found")
    return user


def update_user(db: Session, user_id: int, user_in: UserUpdate) -> User:
    user = get_user(db, user_id)

    update_data = user_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    logger.info("Updated user id=%s", user.id)
    return user


def users_exist(db: Session) -> bool:
    return db.query(User).first() is not None

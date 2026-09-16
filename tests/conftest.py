import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.core.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    # Not used as a context manager: this intentionally skips the app's
    # startup event, which would otherwise call create_all() against the
    # real production database configured in .env.
    return TestClient(app)


@pytest.fixture
def db_session():
    """A raw SQLAlchemy session against the same in-memory test database,
    for service-layer tests that don't go through the HTTP client."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()

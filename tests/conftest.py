import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.core.database import Base, get_db
from app.core.security import create_access_token
from app.main import app
from app.models.user import User, UserRole

TEST_DATABASE_URL = "sqlite:///:memory:"

# Every route except / and /health now requires a bearer token (Phase 9).
# Rather than touching ~150 existing call sites across the other test files,
# the `client` fixture below seeds one fixed admin account directly into the
# test database (no bcrypt call needed -- this row is only ever looked up by
# get_current_user, never logged in via password) and attaches its token as
# a default header, which httpx applies to every request unless a test
# overrides `headers=` itself. Tests that specifically exercise the
# unauthenticated/insufficient-role paths build their own plain
# TestClient(app) or role-specific token instead of using this fixture.
DEFAULT_TEST_ADMIN_USERNAME = "test-admin"

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
    #
    # Seeding happens here rather than in the autouse setup_database fixture
    # above so that tests which don't request `client` (e.g. Phase 9's
    # bootstrap-registration tests) see a genuinely empty `users` table.
    db = TestingSessionLocal()
    try:
        db.add(
            User(
                username=DEFAULT_TEST_ADMIN_USERNAME,
                email="test-admin@example.com",
                hashed_password="unused",
                role=UserRole.ADMIN,
                is_active=True,
            )
        )
        db.commit()
    finally:
        db.close()

    token = create_access_token(subject=DEFAULT_TEST_ADMIN_USERNAME)
    return TestClient(app, headers={"Authorization": f"Bearer {token}"})


@pytest.fixture
def db_session():
    """A raw SQLAlchemy session against the same in-memory test database,
    for service-layer tests that don't go through the HTTP client."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def _no_webhook_retry_delay(monkeypatch):
    """Skip real sleeps between webhook retry attempts so retry/backoff
    tests run instantly instead of taking several real seconds each."""
    monkeypatch.setattr("app.alerts.webhook_client.time.sleep", lambda seconds: None)


@pytest.fixture(autouse=True)
def _reset_scheduler():
    """Ensure no background scheduler thread survives past a single test.

    The app's TestClient fixture never triggers the FastAPI lifespan (see
    its comment above), so the scheduler only ever starts in tests that
    call start_scheduler() directly -- this guarantees it's stopped again
    afterward regardless of how the test exits.
    """
    from app.scheduler.scheduler import stop_scheduler

    yield
    stop_scheduler()

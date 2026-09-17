from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.main import app
from app.models.user import User, UserRole


def _plain_client() -> TestClient:
    """A TestClient with no default Authorization header -- for exercising
    the unauthenticated path (the shared `client` fixture always carries a
    valid admin token, see conftest.py)."""
    return TestClient(app)


def _seed_user(db_session, username: str, role: UserRole, *, is_active: bool = True) -> User:
    """Insert a user row directly, bypassing hashing -- these users are only
    ever looked up by get_current_user via a hand-crafted token, never
    logged in via password, so a real bcrypt hash isn't needed here."""
    user = User(
        username=username,
        email=f"{username}@example.com",
        hashed_password="unused",
        role=role,
        is_active=is_active,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _headers_for(username: str) -> dict:
    return {"Authorization": f"Bearer {create_access_token(subject=username)}"}


# ---------------------------------------------------------------------------
# POST /auth/register
# ---------------------------------------------------------------------------


def test_register_bootstrap_first_user_becomes_admin(db_session):
    response = _plain_client().post(
        "/auth/register",
        json={"username": "first-admin", "email": "first@example.com", "password": "supersecret", "role": "viewer"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "admin"  # forced to admin despite requesting "viewer"
    assert "hashed_password" not in body


def test_register_second_user_without_auth_is_rejected(db_session):
    _seed_user(db_session, "existing-admin", UserRole.ADMIN)

    response = _plain_client().post(
        "/auth/register",
        json={"username": "someone", "email": "someone@example.com", "password": "supersecret"},
    )
    assert response.status_code == 401


def test_register_as_admin_honors_requested_role(db_session):
    admin = _seed_user(db_session, "existing-admin", UserRole.ADMIN)

    response = _plain_client().post(
        "/auth/register",
        json={"username": "new-operator", "email": "op@example.com", "password": "supersecret", "role": "operator"},
        headers=_headers_for(admin.username),
    )
    assert response.status_code == 201
    assert response.json()["role"] == "operator"


def test_register_as_non_admin_is_forbidden(db_session):
    _seed_user(db_session, "existing-admin", UserRole.ADMIN)
    operator = _seed_user(db_session, "existing-operator", UserRole.OPERATOR)

    response = _plain_client().post(
        "/auth/register",
        json={"username": "someone", "email": "someone@example.com", "password": "supersecret"},
        headers=_headers_for(operator.username),
    )
    assert response.status_code == 403


def test_register_duplicate_username_is_conflict(db_session):
    admin = _seed_user(db_session, "existing-admin", UserRole.ADMIN)
    client_headers = _headers_for(admin.username)
    payload = {"username": "dupe", "email": "dupe1@example.com", "password": "supersecret"}
    assert _plain_client().post("/auth/register", json=payload, headers=client_headers).status_code == 201

    payload["email"] = "dupe2@example.com"
    response = _plain_client().post("/auth/register", json=payload, headers=client_headers)
    assert response.status_code == 409


def test_register_duplicate_email_is_conflict(db_session):
    admin = _seed_user(db_session, "existing-admin", UserRole.ADMIN)
    client_headers = _headers_for(admin.username)
    payload = {"username": "user1", "email": "shared@example.com", "password": "supersecret"}
    assert _plain_client().post("/auth/register", json=payload, headers=client_headers).status_code == 201

    payload["username"] = "user2"
    response = _plain_client().post("/auth/register", json=payload, headers=client_headers)
    assert response.status_code == 409


def test_register_short_password_is_rejected():
    response = _plain_client().post(
        "/auth/register",
        json={"username": "shortpw", "email": "shortpw@example.com", "password": "short"},
    )
    assert response.status_code == 422


def test_register_missing_field_is_rejected():
    response = _plain_client().post("/auth/register", json={"username": "nofields"})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------


def test_login_success_returns_token():
    register_response = _plain_client().post(
        "/auth/register",
        json={"username": "logintest", "email": "logintest@example.com", "password": "correct-password"},
    )
    assert register_response.status_code == 201

    response = _plain_client().post("/auth/login", json={"username": "logintest", "password": "correct-password"})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_wrong_password_is_unauthorized():
    _plain_client().post(
        "/auth/register",
        json={"username": "wrongpw", "email": "wrongpw@example.com", "password": "correct-password"},
    )
    response = _plain_client().post("/auth/login", json={"username": "wrongpw", "password": "incorrect"})
    assert response.status_code == 401


def test_login_unknown_username_is_unauthorized():
    response = _plain_client().post("/auth/login", json={"username": "ghost", "password": "whatever1"})
    assert response.status_code == 401


def test_login_inactive_user_is_unauthorized(db_session):
    _seed_user(db_session, "inactive-user", UserRole.VIEWER, is_active=False)
    response = _plain_client().post("/auth/login", json={"username": "inactive-user", "password": "anything1"})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------


def test_me_returns_current_user(db_session):
    viewer = _seed_user(db_session, "me-viewer", UserRole.VIEWER)
    response = _plain_client().get("/auth/me", headers=_headers_for(viewer.username))
    assert response.status_code == 200
    assert response.json()["username"] == "me-viewer"


def test_me_without_token_is_unauthorized():
    assert _plain_client().get("/auth/me").status_code == 401


def test_me_with_garbage_token_is_unauthorized():
    response = _plain_client().get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /auth/users, PATCH /auth/users/{id}
# ---------------------------------------------------------------------------


def test_list_users_requires_admin(db_session):
    admin = _seed_user(db_session, "list-admin", UserRole.ADMIN)
    operator = _seed_user(db_session, "list-operator", UserRole.OPERATOR)
    viewer = _seed_user(db_session, "list-viewer", UserRole.VIEWER)

    assert _plain_client().get("/auth/users", headers=_headers_for(operator.username)).status_code == 403
    assert _plain_client().get("/auth/users", headers=_headers_for(viewer.username)).status_code == 403

    response = _plain_client().get("/auth/users", headers=_headers_for(admin.username))
    assert response.status_code == 200
    assert len(response.json()) == 3


def test_update_user_requires_admin(db_session):
    admin = _seed_user(db_session, "update-admin", UserRole.ADMIN)
    operator = _seed_user(db_session, "update-operator", UserRole.OPERATOR)
    target = _seed_user(db_session, "update-target", UserRole.VIEWER)

    forbidden = _plain_client().patch(
        f"/auth/users/{target.id}", json={"role": "operator"}, headers=_headers_for(operator.username)
    )
    assert forbidden.status_code == 403

    response = _plain_client().patch(
        f"/auth/users/{target.id}", json={"role": "operator"}, headers=_headers_for(admin.username)
    )
    assert response.status_code == 200
    assert response.json()["role"] == "operator"


def test_update_user_deactivate(db_session):
    admin = _seed_user(db_session, "deactivate-admin", UserRole.ADMIN)
    target = _seed_user(db_session, "deactivate-target", UserRole.VIEWER)

    response = _plain_client().patch(
        f"/auth/users/{target.id}", json={"is_active": False}, headers=_headers_for(admin.username)
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_update_unknown_user_is_not_found(db_session):
    admin = _seed_user(db_session, "notfound-admin", UserRole.ADMIN)
    response = _plain_client().patch(
        "/auth/users/999999", json={"role": "operator"}, headers=_headers_for(admin.username)
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# RBAC spot-checks -- every mutation route shares the same
# require_operator/require_admin dependency, so a full endpoint-by-endpoint
# matrix isn't necessary; these confirm the dependency is actually wired in.
# ---------------------------------------------------------------------------


def test_viewer_can_read_but_not_create_devices(db_session):
    viewer = _seed_user(db_session, "rbac-viewer", UserRole.VIEWER)
    headers = _headers_for(viewer.username)

    assert _plain_client().get("/devices", headers=headers).status_code == 200

    response = _plain_client().post(
        "/devices",
        json={
            "hostname": "r1",
            "ip_address": "10.0.0.1",
            "vendor": "Cisco",
            "device_type": "router",
            "username": "admin",
        },
        headers=headers,
    )
    assert response.status_code == 403


def test_operator_can_create_devices_but_not_manage_users(db_session):
    operator = _seed_user(db_session, "rbac-operator", UserRole.OPERATOR)
    headers = _headers_for(operator.username)

    response = _plain_client().post(
        "/devices",
        json={
            "hostname": "r2",
            "ip_address": "10.0.0.2",
            "vendor": "Cisco",
            "device_type": "router",
            "username": "admin",
        },
        headers=headers,
    )
    assert response.status_code == 201
    assert _plain_client().get("/auth/users", headers=headers).status_code == 403


def test_protected_route_without_token_is_unauthorized():
    assert _plain_client().get("/devices").status_code == 401


def test_public_routes_stay_public():
    plain = _plain_client()
    assert plain.get("/").status_code == 200
    assert plain.get("/health").status_code == 200

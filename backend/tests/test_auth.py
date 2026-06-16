import uuid

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token, get_password_hash, verify_password

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL    = "/api/v1/auth/login"
ME_URL       = "/api/v1/auth/me"

TEST_USER = {
    "username": "testuser",
    "email": "test@example.com",
    "password": "TestPass123!",
}
     

# ── Registration ──────────────────────────────────────────────────────────────

async def test_register_success(client: AsyncClient):
    response = await client.post(REGISTER_URL, json=TEST_USER)

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == TEST_USER["email"]
    assert data["username"] == TEST_USER["username"]
    assert data["is_active"] is True
    assert "id" in data
    assert uuid.UUID(data["id"])  # must be a valid UUID
    assert "password" not in data
    assert "hashed_password" not in data


async def test_register_returns_correct_schema(client: AsyncClient):
    response = await client.post(REGISTER_URL, json=TEST_USER)

    assert response.status_code == 201
    data = response.json()
    assert set(data.keys()) == {"id", "username", "email", "is_active"}


async def test_register_duplicate_username(client: AsyncClient):
    await client.post(REGISTER_URL, json=TEST_USER)

    response = await client.post(
        REGISTER_URL,
        json={**TEST_USER, "email": "other@example.com"},
    )

    assert response.status_code == 400
    assert "already registered" in response.json()["detail"]


async def test_register_duplicate_email(client: AsyncClient):
    await client.post(REGISTER_URL, json=TEST_USER)

    response = await client.post(
        REGISTER_URL,
        json={**TEST_USER, "username": "otheruser"},
    )

    assert response.status_code == 400
    assert "already registered" in response.json()["detail"]


async def test_register_missing_username(client: AsyncClient):
    response = await client.post(
        REGISTER_URL,
        json={"email": "test@example.com", "password": "TestPass123!"},
    )
    assert response.status_code == 422


async def test_register_missing_email(client: AsyncClient):
    response = await client.post(
        REGISTER_URL,
        json={"username": "testuser", "password": "TestPass123!"},
    )
    assert response.status_code == 422


async def test_register_missing_password(client: AsyncClient):
    response = await client.post(
        REGISTER_URL,
        json={"username": "testuser", "email": "test@example.com"},
    )
    assert response.status_code == 422


async def test_register_empty_body(client: AsyncClient):
    response = await client.post(REGISTER_URL, json={})
    assert response.status_code == 422


async def test_register_two_different_users(client: AsyncClient):
    user_a = {**TEST_USER}
    user_b = {"username": "user_b", "email": "userb@example.com", "password": "PassB123!"}

    r1 = await client.post(REGISTER_URL, json=user_a)
    r2 = await client.post(REGISTER_URL, json=user_b)

    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] != r2.json()["id"]


# ── Login ─────────────────────────────────────────────────────────────────────

async def test_login_success(client: AsyncClient, registered_user: dict):
    response = await client.post(
        LOGIN_URL,
        data={
            "username": registered_user["email"],
            "password": registered_user["password"],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "user_id" in data
    assert uuid.UUID(data["user_id"])  # must be a valid UUID
    assert len(data["access_token"]) > 20


async def test_login_token_is_jwt_format(client: AsyncClient, registered_user: dict):
    response = await client.post(
        LOGIN_URL,
        data={"username": registered_user["email"], "password": registered_user["password"]},
    )

    token = response.json()["access_token"]
    parts = token.split(".")
    assert len(parts) == 3  # header.payload.signature


async def test_login_wrong_password(client: AsyncClient, registered_user: dict):
    response = await client.post(
        LOGIN_URL,
        data={"username": registered_user["email"], "password": "WrongPassword!"},
    )

    assert response.status_code == 401
    assert "Invalid" in response.json()["detail"]


async def test_login_wrong_email(client: AsyncClient, registered_user: dict):
    response = await client.post(
        LOGIN_URL,
        data={"username": "nobody@example.com", "password": registered_user["password"]},
    )

    assert response.status_code == 401


async def test_login_empty_password(client: AsyncClient, registered_user: dict):
    response = await client.post(
        LOGIN_URL,
        data={"username": registered_user["email"], "password": ""},
    )

    # OAuth2PasswordRequestForm rejects empty password before auth logic runs
    assert response.status_code == 422


async def test_login_missing_password_field(client: AsyncClient):
    response = await client.post(LOGIN_URL, data={"username": TEST_USER["email"]})
    assert response.status_code == 422


async def test_login_missing_username_field(client: AsyncClient):
    response = await client.post(LOGIN_URL, data={"password": TEST_USER["password"]})
    assert response.status_code == 422


async def test_login_returns_different_token_each_time(client: AsyncClient, registered_user: dict):
    """Each login produces a unique token (different iat/exp)."""
    login = lambda: client.post(
        LOGIN_URL,
        data={"username": registered_user["email"], "password": registered_user["password"]},
    )
    r1 = await login()
    r2 = await login()

    assert r1.json()["access_token"] != r2.json()["access_token"]


# ── /me ───────────────────────────────────────────────────────────────────────

async def test_me_success(client: AsyncClient, auth_token: str):
    response = await client.get(
        ME_URL,
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == TEST_USER["email"]
    assert data["username"] == TEST_USER["username"]
    assert data["is_active"] is True
    assert "id" in data
    assert "hashed_password" not in data
    assert "password" not in data


async def test_me_returns_correct_schema(client: AsyncClient, auth_token: str):
    response = await client.get(
        ME_URL,
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert response.status_code == 200
    assert set(response.json().keys()) == {"id", "username", "email", "is_active"}


async def test_me_no_token(client: AsyncClient):
    response = await client.get(ME_URL)
    assert response.status_code == 401


async def test_me_invalid_token(client: AsyncClient):
    response = await client.get(
        ME_URL,
        headers={"Authorization": "Bearer totally.invalid.token"},
    )
    assert response.status_code == 401


async def test_me_malformed_bearer(client: AsyncClient):
    response = await client.get(
        ME_URL,
        headers={"Authorization": "NotBearer sometoken"},
    )
    assert response.status_code == 401


async def test_me_empty_token(client: AsyncClient):
    response = await client.get(
        ME_URL,
        headers={"Authorization": "Bearer "},
    )
    assert response.status_code == 401


async def test_me_token_with_nonexistent_user(client: AsyncClient):
    """Token is valid JWT but user UUID does not exist in DB."""
    fake_token = create_access_token(subject=str(uuid.uuid4()))
    response = await client.get(
        ME_URL,
        headers={"Authorization": f"Bearer {fake_token}"},
    )
    assert response.status_code == 401


# ── Full Auth Flow ────────────────────────────────────────────────────────────

async def test_full_register_login_me_flow(client: AsyncClient):
    """End-to-end: register → login → access /me."""
    reg = await client.post(REGISTER_URL, json=TEST_USER)
    assert reg.status_code == 201

    login = await client.post(
        LOGIN_URL,
        data={"username": TEST_USER["email"], "password": TEST_USER["password"]},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    me = await client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == TEST_USER["email"]


async def test_register_id_matches_login_user_id(client: AsyncClient):
    """The UUID returned on register must match the user_id returned on login."""
    reg = await client.post(REGISTER_URL, json=TEST_USER)
    registered_id = reg.json()["id"]

    login = await client.post(
        LOGIN_URL,
        data={"username": TEST_USER["email"], "password": TEST_USER["password"]},
    )
    login_user_id = login.json()["user_id"]

    assert registered_id == login_user_id


# ── Password Security ─────────────────────────────────────────────────────────

def test_password_is_hashed():
    hashed = get_password_hash("MySecret123")
    assert hashed != "MySecret123"
    assert hashed.startswith("$2b$")


def test_verify_correct_password():
    hashed = get_password_hash("MySecret123")
    assert verify_password("MySecret123", hashed) is True


def test_verify_wrong_password():
    hashed = get_password_hash("MySecret123")
    assert verify_password("WrongPassword", hashed) is False


def test_each_hash_is_unique():
    """bcrypt salt makes every hash different even for the same input."""
    assert get_password_hash("SamePassword") != get_password_hash("SamePassword")


def test_hash_length_is_consistent():
    """bcrypt always produces a 60-character hash."""
    hashed = get_password_hash("AnyPassword123")
    assert len(hashed) == 60

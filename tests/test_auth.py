"""Auth flow tests: signup, login, /me, error paths."""

from httpx import AsyncClient


# --- Signup -----------------------------------------------------------------
async def test_signup_returns_token_and_user(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/auth/signup",
        json={"name": "Eve", "email": "eve@example.com", "password": "goodgoodpw"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "accessToken" in body
    assert body["tokenType"] == "bearer"
    assert body["user"]["email"] == "eve@example.com"
    assert "passwordHash" not in body["user"]
    assert "password" not in body["user"]


async def test_signup_duplicate_email_409(client: AsyncClient) -> None:
    payload = {"name": "Eve", "email": "dup@example.com", "password": "goodgoodpw"}
    first = await client.post("/api/auth/signup", json=payload)
    assert first.status_code == 201

    again = await client.post("/api/auth/signup", json=payload)
    assert again.status_code == 409
    assert "registered" in again.json()["detail"].lower()


async def test_signup_rejects_weak_password(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/auth/signup",
        json={"name": "Eve", "email": "eve@example.com", "password": "short"},
    )
    assert resp.status_code == 422  # pydantic validation error


# --- Login ------------------------------------------------------------------
async def test_login_with_correct_password(client: AsyncClient, alice: dict) -> None:
    resp = await client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "hunter2hunter"},
    )
    assert resp.status_code == 200
    assert resp.json()["accessToken"]


async def test_login_wrong_password_401(client: AsyncClient, alice: dict) -> None:
    resp = await client.post(
        "/api/auth/login",
        json={"email": "alice@example.com", "password": "WRONG_PASSWORD"},
    )
    assert resp.status_code == 401
    # Generic message — must not say "no such user" vs "wrong password".
    assert "invalid" in resp.json()["detail"].lower()


async def test_login_unknown_email_returns_same_401(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/auth/login",
        json={"email": "ghost@example.com", "password": "hunter2hunter"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid email or password"


# --- /me --------------------------------------------------------------------
async def test_me_with_valid_token(client: AsyncClient, alice: dict) -> None:
    resp = await client.get("/api/auth/me", headers=alice["headers"])
    assert resp.status_code == 200
    assert resp.json()["email"] == "alice@example.com"


async def test_me_without_token_401(client: AsyncClient) -> None:
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401


async def test_me_with_garbage_token_401(client: AsyncClient) -> None:
    resp = await client.get(
        "/api/auth/me", headers={"Authorization": "Bearer not-a-real-jwt"}
    )
    assert resp.status_code == 401

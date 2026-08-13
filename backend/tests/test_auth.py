from httpx import AsyncClient

from tests.conftest import register_and_login


async def test_register_login_me(client: AsyncClient) -> None:
    headers = await register_and_login(client)

    me = await client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == "adi@example.com"
    assert body["username"] == "adi"
    assert "password" not in body and "password_hash" not in body


async def test_duplicate_email_rejected(client: AsyncClient) -> None:
    await register_and_login(client)
    response = await client.post(
        "/api/auth/register",
        json={"email": "ADI@example.com", "username": "xx", "password": "supersecret123"},
    )
    assert response.status_code == 409


async def test_wrong_password_rejected(client: AsyncClient) -> None:
    await register_and_login(client)
    response = await client.post(
        "/api/auth/login",
        json={"email": "adi@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 401


async def test_short_password_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/register",
        json={"email": "a@b.com", "username": "a", "password": "short"},
    )
    assert response.status_code == 422


async def test_refresh_flow(client: AsyncClient) -> None:
    register = await client.post(
        "/api/auth/register",
        json={"email": "r@example.com", "username": "rr", "password": "supersecret123"},
    )
    refresh_token = register.json()["refresh_token"]

    refreshed = await client.post(
        "/api/auth/refresh", json={"refresh_token": refresh_token}
    )
    assert refreshed.status_code == 200
    new_access = refreshed.json()["access_token"]
    me = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {new_access}"}
    )
    assert me.status_code == 200


async def test_access_token_cannot_be_used_as_refresh(client: AsyncClient) -> None:
    register = await client.post(
        "/api/auth/register",
        json={"email": "t@example.com", "username": "tt", "password": "supersecret123"},
    )
    access_token = register.json()["access_token"]
    response = await client.post(
        "/api/auth/refresh", json={"refresh_token": access_token}
    )
    assert response.status_code == 401


async def test_protected_route_requires_token(client: AsyncClient) -> None:
    response = await client.get("/api/sessions")
    assert response.status_code == 401

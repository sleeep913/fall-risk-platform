import pytest
from httpx import AsyncClient

from tests.conftest import TEST_PASSWORD


@pytest.mark.asyncio
async def test_login_me_refresh_rotation_and_logout(client: AsyncClient) -> None:
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": " ADMIN ", "password": TEST_PASSWORD},
    )
    assert login.status_code == 200
    tokens = login.json()
    assert tokens["token_type"] == "bearer"
    assert tokens["expires_in"] == 300
    assert tokens["user"]["role"] == "admin"
    assert "refresh_token" not in tokens
    first_refresh_cookie = client.cookies.get("fall_risk_refresh")
    assert first_refresh_cookie

    me = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["username"] == "admin"

    refresh = await client.post(
        "/api/v1/auth/refresh",
    )
    assert refresh.status_code == 200
    rotated = refresh.json()
    rotated_refresh_cookie = client.cookies.get("fall_risk_refresh")
    assert rotated_refresh_cookie != first_refresh_cookie

    client.cookies.set("fall_risk_refresh", first_refresh_cookie)
    reused = await client.post("/api/v1/auth/refresh")
    assert reused.status_code == 401

    client.cookies.set("fall_risk_refresh", rotated_refresh_cookie)
    logout = await client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {rotated['access_token']}"},
    )
    assert logout.status_code == 204

    client.cookies.set("fall_risk_refresh", rotated_refresh_cookie)
    after_logout = await client.post("/api/v1/auth/refresh")
    assert after_logout.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("username", "password"),
    [
        ("missing", TEST_PASSWORD),
        ("admin", "wrong-password"),
        ("disabled", TEST_PASSWORD),
    ],
)
async def test_login_rejects_invalid_or_inactive_users(
    client: AsyncClient, username: str, password: str
) -> None:
    response = await client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password"


@pytest.mark.asyncio
async def test_me_requires_access_token(client: AsyncClient) -> None:
    missing = await client.get("/api/v1/auth/me")
    assert missing.status_code == 401

    await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": TEST_PASSWORD},
    )
    refresh_token = client.cookies.get("fall_risk_refresh")
    rejected = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {refresh_token}"},
    )
    assert rejected.status_code == 401

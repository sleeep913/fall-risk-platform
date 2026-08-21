from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient


class HealthyResponse:
    def raise_for_status(self) -> None:
        return None


@pytest.mark.asyncio
async def test_health_is_public(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == "0.1.0"


@pytest.mark.asyncio
async def test_readiness_reports_all_dependencies(client: AsyncClient, app, monkeypatch) -> None:
    monkeypatch.setattr(app.state.redis, "ping", AsyncMock(return_value=True))
    monkeypatch.setattr(
        app.state.http_client,
        "get",
        AsyncMock(return_value=HealthyResponse()),
    )
    response = await client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["mode"] == "full"
    assert set(body["checks"]) == {"database", "redis", "minio"}
    assert all(check["status"] == "ok" for check in body["checks"].values())


@pytest.mark.asyncio
async def test_readiness_returns_503_when_dependencies_are_down(client: AsyncClient) -> None:
    response = await client.get("/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"


@pytest.mark.asyncio
async def test_lightweight_readiness_disables_unused_dependencies(
    client: AsyncClient, app
) -> None:
    app.state.settings.local_lightweight_mode = True

    response = await client.get("/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["mode"] == "lightweight"
    assert body["checks"]["database"]["status"] == "ok"
    assert body["checks"]["redis"]["status"] == "disabled"
    assert body["checks"]["minio"]["status"] == "disabled"

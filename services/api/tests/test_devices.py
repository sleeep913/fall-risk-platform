from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.core.config import Settings
from app.models.device import Device, DeviceOnlineStatus
from app.modules.devices.service import DeviceService, map_online_status
from app.modules.ezviz.errors import EzvizConfigurationError
from app.schemas.device import DeviceSyncResponse
from tests.conftest import TEST_PASSWORD


class FakeTokenManager:
    configured = True

    def __init__(self) -> None:
        self.force_refresh_calls = 0

    async def get_valid_token(self, *, force_refresh: bool = False) -> str:
        self.force_refresh_calls += int(force_refresh)
        return "refreshed-token" if force_refresh else "cached-token"


class FakeEzvizClient:
    async def list_devices(self, access_token: str, page_start: int, page_size: int):
        return (
            [
                {
                    "deviceSerial": "ABC123456789",
                    "deviceName": "客厅摄像机",
                    "deviceType": "CS-C6N",
                    "status": 1,
                    "cameraNum": 1,
                }
            ],
            1,
        )

    async def list_channels(self, access_token: str, page_start: int, page_size: int):
        return (
            [
                {
                    "deviceSerial": "ABC123456789",
                    "channelNo": 1,
                    "channelName": "客厅",
                    "status": 1,
                    "isEncrypt": 1,
                    "videoLevel": 2,
                }
            ],
            1,
        )

    async def get_device_info(self, access_token: str, device_serial: str):
        return {"deviceSerial": device_serial, "status": 0, "isEncrypt": 0}


class UnconfiguredDeviceService:
    async def sync(self, session):
        raise EzvizConfigurationError("server credentials missing")


async def admin_headers(client: AsyncClient) -> dict[str, str]:
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": TEST_PASSWORD},
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def caregiver_headers(client: AsyncClient) -> dict[str, str]:
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": "caregiver", "password": TEST_PASSWORD},
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest.mark.asyncio
async def test_device_sync_persists_and_masks_serial(client: AsyncClient, app) -> None:
    service = DeviceService(
        FakeEzvizClient(),  # type: ignore[arg-type]
        FakeTokenManager(),  # type: ignore[arg-type]
        Settings(
            _env_file=None,
            app_env="test",
            jwt_secret="test-secret-that-is-longer-than-thirty-two-characters",
        ),
    )
    async with app.state.session_factory() as session:
        result = await service.sync(session)
        devices = await service.list_devices(session)

    assert result.created == 1
    assert result.channel_count == 1
    assert len(devices) == 1
    assert devices[0].serial_masked == "ABC*****6789"
    assert devices[0].online_status == "online"
    assert devices[0].channels[0].is_encrypted is True
    assert "ABC123456789" not in devices[0].model_dump_json()


@pytest.mark.asyncio
async def test_device_routes_require_authentication(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/devices")).status_code == 401
    assert (await client.post("/api/v1/devices/sync")).status_code == 401


@pytest.mark.asyncio
async def test_integration_status_never_returns_token_value(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/devices/integration", headers=await admin_headers(client)
    )

    assert response.status_code == 200
    assert response.json()["token_status"] == "not_configured"
    assert response.json()["token_expires_at"] is None
    assert "access_token" not in response.text.lower()


@pytest.mark.asyncio
async def test_device_routes_require_admin_role(client: AsyncClient) -> None:
    headers = await caregiver_headers(client)

    assert (await client.get("/api/v1/devices", headers=headers)).status_code == 403
    assert (await client.post("/api/v1/devices/sync", headers=headers)).status_code == 403


@pytest.mark.asyncio
async def test_sync_reports_missing_server_configuration(client: AsyncClient, app) -> None:
    app.state.device_service = UnconfiguredDeviceService()
    response = await client.post(
        "/api/v1/devices/sync", headers=await admin_headers(client)
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "ezviz_not_configured"


@pytest.mark.asyncio
async def test_sync_response_never_contains_credentials(client: AsyncClient, app) -> None:
    class SuccessfulService:
        async def sync(self, session):
            return DeviceSyncResponse(
                created=1,
                updated=0,
                missing=0,
                channel_count=1,
                synced_at=datetime.now(UTC),
            )

    app.state.device_service = SuccessfulService()
    response = await client.post(
        "/api/v1/devices/sync", headers=await admin_headers(client)
    )

    assert response.status_code == 200
    assert set(response.json()) == {
        "created",
        "updated",
        "missing",
        "channel_count",
        "synced_at",
    }


@pytest.mark.asyncio
async def test_live_status_query_updates_the_device(client: AsyncClient, app) -> None:
    token_manager = FakeTokenManager()
    service = DeviceService(
        FakeEzvizClient(),  # type: ignore[arg-type]
        token_manager,  # type: ignore[arg-type]
        Settings(
            _env_file=None,
            app_env="test",
            jwt_secret="test-secret-that-is-longer-than-thirty-two-characters",
        ),
    )
    async with app.state.session_factory() as session:
        device = Device(
            provider="ezviz",
            device_serial="ABC123456789",
            name="客厅摄像机",
            online_status=DeviceOnlineStatus.ONLINE,
            channel_count=1,
            is_present=True,
            last_synced_at=datetime.now(UTC),
        )
        session.add(device)
        await session.commit()
        device_id = device.id
    app.state.device_service = service

    response = await client.get(
        f"/api/v1/devices/{device_id}/status", headers=await admin_headers(client)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["serial_masked"] == "ABC*****6789"
    assert body["online_status"] == "offline"
    assert body["is_encrypted"] is False


def test_device_list_offline_status_two_is_supported() -> None:
    assert map_online_status(2) == DeviceOnlineStatus.OFFLINE
    assert map_online_status("2") == DeviceOnlineStatus.OFFLINE

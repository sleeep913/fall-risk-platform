from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import Settings
from app.models.device import Device, DeviceChannel, DeviceOnlineStatus
from app.models.device_package import DevicePackageActivation
from app.modules.device_packages.service import DevicePackageService
from app.modules.ezviz.client import EzvizPackageActivationResult
from app.modules.ezviz.errors import EzvizApiError
from app.modules.ezviz.token_manager import EzvizTokenCacheStatus
from tests.conftest import TEST_PASSWORD


class FakePackageTokenManager:
    configured = True

    def __init__(self) -> None:
        self.force_refresh_calls = 0

    async def get_valid_token(
        self, *, force_refresh: bool = False, stale_token: str | None = None
    ) -> str:
        self.force_refresh_calls += int(force_refresh)
        return "refreshed-token" if force_refresh else "cached-token"

    async def cache_status(self) -> EzvizTokenCacheStatus:
        return EzvizTokenCacheStatus(state="valid")


class FakePackageClient:
    def __init__(self, *, expire_first: bool = False) -> None:
        self.calls = 0
        self.expire_first = expire_first

    async def activate_device_package(
        self, access_token: str, package_code: str, device_serial: str, channel_no: int
    ) -> EzvizPackageActivationResult:
        self.calls += 1
        assert package_code == "sensitive-package-code-0001"
        assert device_serial == "ABC123456789"
        assert channel_no == 1
        if self.expire_first and self.calls == 1:
            raise EzvizApiError(
                "expired", platform_code="10002", token_invalid=True
            )
        return EzvizPackageActivationResult(
            "200", 0, "激活成功 sensitive-package-code-0001"
        )


def package_settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env="test",
        jwt_secret="test-secret-that-is-longer-than-thirty-two-characters",
        ezviz_app_key="app-key",
        ezviz_app_secret="app-secret",
        ezviz_package_code_01="sensitive-package-code-0001",
        ezviz_coupon_redeemed=True,
    )


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


async def create_online_device(app) -> tuple[int, int]:
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
        await session.flush()
        channel = DeviceChannel(
            device_id=device.id,
            channel_no=1,
            name="客厅",
            online_status=DeviceOnlineStatus.ONLINE,
            is_present=True,
            last_synced_at=datetime.now(UTC),
        )
        session.add(channel)
        await session.commit()
        return device.id, channel.id


@pytest.mark.asyncio
async def test_package_routes_require_admin(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/admin/ezviz/packages")).status_code == 401
    response = await client.get(
        "/api/v1/admin/ezviz/packages", headers=await caregiver_headers(client)
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_package_activation_is_idempotent_and_audited(client: AsyncClient, app) -> None:
    device_id, _ = await create_online_device(app)
    fake_client = FakePackageClient()
    service = DevicePackageService(
        fake_client,  # type: ignore[arg-type]
        FakePackageTokenManager(),  # type: ignore[arg-type]
        package_settings(),
    )
    app.state.device_package_service = service
    payload = {
        "package_slot": 1,
        "device_id": device_id,
        "channel_no": 1,
        "confirmed": True,
    }
    headers = await admin_headers(client)

    first = await client.post(
        "/api/v1/admin/ezviz/packages/activate", json=payload, headers=headers
    )
    repeated = await client.post(
        "/api/v1/admin/ezviz/packages/activate", json=payload, headers=headers
    )

    assert first.status_code == repeated.status_code == 200
    assert first.json()["activation_status"] == "succeeded"
    assert first.json()["device_serial_masked"] == "ABC*****6789"
    assert first.json()["package_code_suffix"] == "0001"
    assert first.json()["official_message"] == "激活成功 [redacted]"
    assert "sensitive-package-code" not in first.text
    assert repeated.json()["id"] == first.json()["id"]
    assert fake_client.calls == 1
    async with app.state.session_factory() as session:
        records = (await session.scalars(select(DevicePackageActivation))).all()
    assert len(records) == 1


@pytest.mark.asyncio
async def test_package_activation_refreshes_expired_token_once(client: AsyncClient, app) -> None:
    device_id, _ = await create_online_device(app)
    fake_client = FakePackageClient(expire_first=True)
    token_manager = FakePackageTokenManager()
    app.state.device_package_service = DevicePackageService(
        fake_client,  # type: ignore[arg-type]
        token_manager,  # type: ignore[arg-type]
        package_settings(),
    )

    response = await client.post(
        "/api/v1/admin/ezviz/packages/activate",
        json={
            "package_slot": 1,
            "device_id": device_id,
            "channel_no": 1,
            "confirmed": True,
        },
        headers=await admin_headers(client),
    )

    assert response.status_code == 200
    assert response.json()["activation_status"] == "succeeded"
    assert response.json()["retry_count"] == 1
    assert fake_client.calls == 2
    assert token_manager.force_refresh_calls == 1


@pytest.mark.asyncio
async def test_package_activation_requires_explicit_confirmation(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/admin/ezviz/packages/activate",
        json={"package_slot": 1, "device_id": 1, "channel_no": 1, "confirmed": False},
        headers=await admin_headers(client),
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_slot_list_never_exposes_package_code(client: AsyncClient, app) -> None:
    app.state.device_package_service = DevicePackageService(
        FakePackageClient(),  # type: ignore[arg-type]
        FakePackageTokenManager(),  # type: ignore[arg-type]
        package_settings(),
    )
    response = await client.get(
        "/api/v1/admin/ezviz/packages", headers=await admin_headers(client)
    )
    assert response.status_code == 200
    assert response.json()[0]["configured"] is True
    assert response.json()[0]["activation"] is None
    assert "sensitive-package-code" not in response.text


@pytest.mark.asyncio
async def test_entitlement_summary_reports_readiness_without_secrets(
    client: AsyncClient, app
) -> None:
    app.state.device_package_service = DevicePackageService(
        FakePackageClient(),  # type: ignore[arg-type]
        FakePackageTokenManager(),  # type: ignore[arg-type]
        package_settings(),
    )

    response = await client.get(
        "/api/v1/admin/ezviz/packages/entitlements",
        headers=await admin_headers(client),
    )

    assert response.status_code == 200
    assert response.json() == {
        "source": "competition_notice",
        "package_slots_total": 5,
        "configured_slot_count": 1,
        "activated_slot_count": 0,
        "validity_months": 6,
        "coupon_redeemed": True,
        "token_status": "valid",
        "online_device_count": 0,
        "activation_ready": False,
        "blockers": ["no_online_devices"],
    }
    assert "sensitive-package-code" not in response.text

import httpx
import pytest

from app.core.config import Settings
from app.modules.ezviz.client import EzvizClient
from app.modules.ezviz.errors import EzvizApiError


def settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env="test",
        jwt_secret="test-secret-that-is-longer-than-thirty-two-characters",
        ezviz_api_base_url="https://ezviz.test",
        ezviz_app_key="server-app-key",
        ezviz_app_secret="server-app-secret",
    )


@pytest.mark.asyncio
async def test_token_request_uses_form_data_and_parses_expiry() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/lapp/token/get"
        assert request.headers["content-type"].startswith(
            "application/x-www-form-urlencoded"
        )
        assert request.content == b"appKey=server-app-key&appSecret=server-app-secret"
        return httpx.Response(
            200,
            json={
                "code": "200",
                "msg": "操作成功",
                "data": {"accessToken": "sensitive-token", "expireTime": 2_000_000_000_000},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        token, expires_at = await EzvizClient(http_client, settings()).request_token()

    assert token == "sensitive-token"
    assert expires_at == 2_000_000_000_000


@pytest.mark.asyncio
async def test_client_marks_token_expiry_for_single_retry() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": "110003", "msg": "token expired"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = EzvizClient(http_client, settings())
        with pytest.raises(EzvizApiError) as caught:
            await client.list_devices("expired-token", 0, 20)

    assert caught.value.token_invalid is True
    assert caught.value.platform_code == "110003"


@pytest.mark.asyncio
async def test_package_activation_uses_header_and_never_returns_package_code() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v3/mall/device/package/code/active"
        assert request.headers["accessToken"] == "server-token"
        assert request.content == (
            b'[{"packageDeviceId":"one-time-code","deviceSerial":"ABC123",'
            b'"channelNo":"1"}]'
        )
        return httpx.Response(
            200,
            json={
                "meta": {"code": 200, "message": "操作成功"},
                "data": [
                    {
                        "packageDeviceId": "one-time-code",
                        "activeCode": 0,
                        "activeMessage": "激活成功",
                    }
                ],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        result = await EzvizClient(http_client, settings()).activate_device_package(
            "server-token", "one-time-code", "ABC123", 1
        )

    assert result.active_code == 0
    assert result.message == "激活成功"
    assert "one-time-code" not in repr(result)


@pytest.mark.asyncio
async def test_package_activation_marks_expired_token() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"meta": {"code": 10002, "message": "token expired"}, "data": []},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        with pytest.raises(EzvizApiError) as caught:
            await EzvizClient(http_client, settings()).activate_device_package(
                "expired-token", "one-time-code", "ABC123", 1
            )

    assert caught.value.token_invalid is True
    assert caught.value.platform_code == "10002"

import asyncio
import time

import pytest

from app.core.config import Settings
from app.modules.ezviz.cache import MemoryTokenCache
from app.modules.ezviz.errors import EzvizConfigurationError
from app.modules.ezviz.token_manager import EzvizTokenManager


class FakeTokenClient:
    def __init__(self) -> None:
        self.calls = 0

    async def request_token(self) -> tuple[str, int]:
        self.calls += 1
        await asyncio.sleep(0)
        return f"secret-token-{self.calls}", int(time.time() * 1000) + 3_600_000


def configured_settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env="test",
        jwt_secret="test-secret-that-is-longer-than-thirty-two-characters",
        ezviz_app_key="app-key",
        ezviz_app_secret="app-secret",
    )


@pytest.mark.asyncio
async def test_token_manager_caches_and_forces_refresh() -> None:
    client = FakeTokenClient()
    manager = EzvizTokenManager(client, MemoryTokenCache(), configured_settings())  # type: ignore[arg-type]

    first = await manager.get_valid_token()
    cached = await manager.get_valid_token()
    refreshed = await manager.get_valid_token(force_refresh=True)

    assert first == cached == "secret-token-1"
    assert refreshed == "secret-token-2"
    assert client.calls == 2

    status = await manager.cache_status()
    assert status.state == "valid"
    assert status.expires_at is not None
    assert status.refreshed_at is not None


@pytest.mark.asyncio
async def test_token_manager_lock_prevents_duplicate_concurrent_refreshes() -> None:
    client = FakeTokenClient()
    manager = EzvizTokenManager(client, MemoryTokenCache(), configured_settings())  # type: ignore[arg-type]

    tokens = await asyncio.gather(*(manager.get_valid_token() for _ in range(8)))

    assert tokens == ["secret-token-1"] * 8
    assert client.calls == 1


@pytest.mark.asyncio
async def test_concurrent_invalid_token_recovery_refreshes_only_once() -> None:
    client = FakeTokenClient()
    manager = EzvizTokenManager(client, MemoryTokenCache(), configured_settings())  # type: ignore[arg-type]
    stale = await manager.get_valid_token()

    tokens = await asyncio.gather(
        *(
            manager.get_valid_token(force_refresh=True, stale_token=stale)
            for _ in range(8)
        )
    )

    assert tokens == ["secret-token-2"] * 8
    assert client.calls == 2


@pytest.mark.asyncio
async def test_token_manager_rejects_missing_server_credentials() -> None:
    settings = Settings(
        _env_file=None,
        app_env="test",
        jwt_secret="test-secret-that-is-longer-than-thirty-two-characters",
    )
    manager = EzvizTokenManager(FakeTokenClient(), MemoryTokenCache(), settings)  # type: ignore[arg-type]

    with pytest.raises(EzvizConfigurationError):
        await manager.get_valid_token()

    status = await manager.cache_status()
    assert status.state == "not_configured"
    assert status.expires_at is None

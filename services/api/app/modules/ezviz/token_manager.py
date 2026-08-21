import time
from dataclasses import dataclass
from datetime import UTC, datetime

from app.core.config import Settings
from app.modules.ezviz.cache import TokenCache
from app.modules.ezviz.client import EzvizClient
from app.modules.ezviz.errors import EzvizConfigurationError


@dataclass(frozen=True)
class EzvizTokenCacheStatus:
    state: str
    expires_at: datetime | None = None
    refreshed_at: datetime | None = None


class EzvizTokenManager:
    def __init__(
        self, client: EzvizClient, cache: TokenCache, settings: Settings
    ) -> None:
        self._client = client
        self._cache = cache
        self._settings = settings

    @property
    def configured(self) -> bool:
        return self._settings.ezviz_credentials_configured

    async def get_valid_token(
        self, *, force_refresh: bool = False, stale_token: str | None = None
    ) -> str:
        self._require_configured()
        if not force_refresh:
            cached = await self._cache.get()
            if self._is_valid(cached):
                return str(cached["access_token"])

        async with self._cache.lock(self._settings.ezviz_token_lock_timeout_seconds):
            cached = await self._cache.get()
            if self._is_valid(cached) and (
                not force_refresh
                or (stale_token is not None and cached["access_token"] != stale_token)
            ):
                return str(cached["access_token"])
            return await self._refresh_token()

    async def invalidate(self) -> None:
        await self._cache.delete()

    async def cache_status(self) -> EzvizTokenCacheStatus:
        if not self.configured:
            return EzvizTokenCacheStatus(state="not_configured")
        cached = await self._cache.get()
        if not cached or not cached.get("access_token"):
            return EzvizTokenCacheStatus(state="not_cached")

        expires_at = _parse_expire_time(cached.get("expire_time"))
        refreshed_at = _parse_datetime(cached.get("refreshed_at"))
        return EzvizTokenCacheStatus(
            state="valid" if self._is_valid(cached) else "refresh_required",
            expires_at=expires_at,
            refreshed_at=refreshed_at,
        )

    async def _refresh_token(self) -> str:
        token, expires_at_ms = await self._client.request_token()
        now_ms = int(time.time() * 1000)
        ttl_seconds = max(1, (expires_at_ms - now_ms) // 1000)
        await self._cache.set(
            {
                "access_token": token,
                "expire_time": expires_at_ms,
                "refreshed_at": datetime.now(UTC).isoformat(),
            },
            ttl_seconds,
        )
        return token

    def _is_valid(self, cached: dict[str, object] | None) -> bool:
        if not cached or not cached.get("access_token"):
            return False
        try:
            expires_at_ms = int(cached["expire_time"])
        except (KeyError, TypeError, ValueError):
            return False
        skew_ms = self._settings.ezviz_token_refresh_skew_seconds * 1000
        return expires_at_ms - skew_ms > int(time.time() * 1000)

    def _require_configured(self) -> None:
        if not self.configured:
            raise EzvizConfigurationError(
                "EZVIZ_APP_KEY and EZVIZ_APP_SECRET are not configured on the server"
            )


def _parse_expire_time(value: object) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(value) / 1000, UTC)
    except (TypeError, ValueError, OSError):
        return None


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)

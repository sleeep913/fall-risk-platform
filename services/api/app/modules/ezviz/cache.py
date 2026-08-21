import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Protocol

from redis.asyncio import Redis
from redis.exceptions import LockError, RedisError


class TokenCache(Protocol):
    async def get(self) -> dict[str, object] | None: ...

    async def set(self, value: dict[str, object], ttl_seconds: int) -> None: ...

    async def delete(self) -> None: ...

    def lock(self, timeout_seconds: int) -> AsyncIterator[None]: ...


class MemoryTokenCache:
    def __init__(self) -> None:
        self._value: dict[str, object] | None = None
        self._lock = asyncio.Lock()

    async def get(self) -> dict[str, object] | None:
        return self._value.copy() if self._value else None

    async def set(self, value: dict[str, object], ttl_seconds: int) -> None:
        self._value = value.copy()

    async def delete(self) -> None:
        self._value = None

    @asynccontextmanager
    async def lock(self, timeout_seconds: int) -> AsyncIterator[None]:
        async with asyncio.timeout(timeout_seconds):
            async with self._lock:
                yield


class RedisTokenCache:
    CACHE_KEY = "fall-risk:ezviz:access-token"
    LOCK_KEY = "fall-risk:ezviz:access-token:lock"

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def get(self) -> dict[str, object] | None:
        raw = await self._redis.get(self.CACHE_KEY)
        return json.loads(raw) if raw else None

    async def set(self, value: dict[str, object], ttl_seconds: int) -> None:
        await self._redis.set(
            self.CACHE_KEY, json.dumps(value, separators=(",", ":")), ex=ttl_seconds
        )

    async def delete(self) -> None:
        await self._redis.delete(self.CACHE_KEY)

    @asynccontextmanager
    async def lock(self, timeout_seconds: int) -> AsyncIterator[None]:
        lock = self._redis.lock(
            self.LOCK_KEY,
            timeout=timeout_seconds,
            blocking_timeout=timeout_seconds,
        )
        try:
            acquired = await lock.acquire()
            if not acquired:
                raise TimeoutError("Timed out waiting for EZVIZ token refresh lock")
            yield
        except RedisError as exc:
            raise ConnectionError("Redis token cache unavailable") from exc
        finally:
            if await lock.owned():
                try:
                    await lock.release()
                except LockError:
                    pass

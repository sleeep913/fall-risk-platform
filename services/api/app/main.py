import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from app.core.config import Settings, get_settings
from app.core.database import create_database
from app.models import Base
from app.modules.auth.router import router as auth_router
from app.modules.device_packages.router import router as device_packages_router
from app.modules.device_packages.service import DevicePackageService
from app.modules.devices.router import router as devices_router
from app.modules.devices.service import DeviceService
from app.modules.ezviz.cache import MemoryTokenCache, RedisTokenCache
from app.modules.ezviz.client import EzvizClient
from app.modules.ezviz.token_manager import EzvizTokenManager
from app.modules.offline_videos.router import router as offline_videos_router
from app.modules.system.router import router as system_router


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine, session_factory = create_database(resolved_settings)
        app.state.engine = engine
        app.state.session_factory = session_factory
        app.state.redis = Redis.from_url(
            resolved_settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=resolved_settings.health_check_timeout_seconds,
            socket_timeout=resolved_settings.health_check_timeout_seconds,
            retry_on_timeout=False,
        )
        app.state.http_client = httpx.AsyncClient()
        token_cache = (
            MemoryTokenCache()
            if resolved_settings.local_lightweight_mode
            else RedisTokenCache(app.state.redis)
        )
        ezviz_client = EzvizClient(app.state.http_client, resolved_settings)
        token_manager = EzvizTokenManager(
            ezviz_client, token_cache, resolved_settings
        )
        app.state.device_service = DeviceService(
            ezviz_client, token_manager, resolved_settings
        )
        app.state.device_package_service = DevicePackageService(
            ezviz_client, token_manager, resolved_settings
        )

        if resolved_settings.auto_create_tables:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
        yield
        await app.state.http_client.aclose()
        await app.state.redis.aclose()
        await engine.dispose()

    app = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.app_version,
        description="老年人跌倒风险预测与分级预警平台 API",
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(system_router)
    app.include_router(auth_router, prefix=resolved_settings.api_v1_prefix)
    app.include_router(devices_router, prefix=resolved_settings.api_v1_prefix)
    app.include_router(device_packages_router, prefix=resolved_settings.api_v1_prefix)
    app.include_router(offline_videos_router, prefix=resolved_settings.api_v1_prefix)
    return app


logging.basicConfig(level=getattr(logging, get_settings().log_level.upper(), logging.INFO))
app = create_app()

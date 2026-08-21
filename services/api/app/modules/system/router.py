import asyncio
from datetime import UTC, datetime
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Request, Response, status
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.database import get_app_settings, get_db_session
from app.schemas.system import DependencyHealth, HealthResponse, ReadinessResponse

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
async def health(
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        timestamp=datetime.now(UTC),
    )


@router.get("/ready", response_model=ReadinessResponse)
async def readiness(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> ReadinessResponse:
    database_check = await _check_database(
        session, settings.health_check_timeout_seconds
    )
    if settings.local_lightweight_mode:
        redis_check = DependencyHealth(
            status="disabled", detail="disabled_in_local_lightweight_mode"
        )
        minio_check = DependencyHealth(
            status="disabled", detail="disabled_in_local_lightweight_mode"
        )
    else:
        redis: Redis = request.app.state.redis
        client: httpx.AsyncClient = request.app.state.http_client
        redis_check, minio_check = await asyncio.gather(
            _check_redis(redis, settings.health_check_timeout_seconds),
            _check_minio(client, settings),
        )
    checks = {
        "database": database_check,
        "redis": redis_check,
        "minio": minio_check,
    }

    ready = all(check.status != "error" for check in checks.values())
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(
        status="ready" if ready else "not_ready",
        mode="lightweight" if settings.local_lightweight_mode else "full",
        checks=checks,
        timestamp=datetime.now(UTC),
    )


async def _check_database(
    session: AsyncSession, timeout: float
) -> DependencyHealth:
    try:
        await asyncio.wait_for(session.execute(text("SELECT 1")), timeout=timeout)
        return DependencyHealth(status="ok")
    except Exception:
        return DependencyHealth(status="error", detail="unavailable")


async def _check_redis(redis: Redis, timeout: float) -> DependencyHealth:
    try:
        await asyncio.wait_for(redis.ping(), timeout=timeout)
        return DependencyHealth(status="ok")
    except Exception:
        return DependencyHealth(status="error", detail="unavailable")


async def _check_minio(
    client: httpx.AsyncClient, settings: Settings
) -> DependencyHealth:
    try:
        scheme = "https" if settings.minio_secure else "http"
        minio_response = await client.get(
            f"{scheme}://{settings.minio_endpoint}/minio/health/ready",
            timeout=settings.health_check_timeout_seconds,
        )
        minio_response.raise_for_status()
        return DependencyHealth(status="ok")
    except Exception:
        return DependencyHealth(status="error", detail="unavailable")

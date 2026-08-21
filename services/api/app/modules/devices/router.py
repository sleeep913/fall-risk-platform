from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.models.user import User
from app.modules.auth.dependencies import require_admin
from app.modules.devices.dependencies import get_device_service
from app.modules.devices.service import DeviceService
from app.modules.ezviz.errors import EzvizApiError, EzvizConfigurationError
from app.schemas.device import (
    DeviceRead,
    DeviceStatusRead,
    DeviceSyncResponse,
    EzvizIntegrationStatus,
)

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("/integration", response_model=EzvizIntegrationStatus)
async def integration_status(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[DeviceService, Depends(get_device_service)],
    _: Annotated[User, Depends(require_admin)],
) -> EzvizIntegrationStatus:
    return await service.integration_status(session)


@router.post("/sync", response_model=DeviceSyncResponse)
async def sync_devices(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[DeviceService, Depends(get_device_service)],
    _: Annotated[User, Depends(require_admin)],
) -> DeviceSyncResponse:
    try:
        return await service.sync(session)
    except EzvizConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "ezviz_not_configured", "message": str(exc)},
        ) from exc
    except (ConnectionError, TimeoutError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "token_cache_unavailable",
                "message": "EZVIZ token cache is temporarily unavailable",
            },
        ) from exc
    except EzvizApiError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": exc.platform_code or "ezviz_upstream_error",
                "message": _public_ezviz_error_message(exc),
                "retryable": exc.retryable,
            },
        ) from exc


@router.get("", response_model=list[DeviceRead])
async def list_devices(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[DeviceService, Depends(get_device_service)],
    _: Annotated[User, Depends(require_admin)],
) -> list[DeviceRead]:
    return await service.list_devices(session)


@router.get("/{device_id}", response_model=DeviceRead)
async def get_device(
    device_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[DeviceService, Depends(get_device_service)],
    _: Annotated[User, Depends(require_admin)],
) -> DeviceRead:
    device = await service.get_device(session, device_id)
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return device


@router.get("/{device_id}/status", response_model=DeviceStatusRead)
async def get_device_status(
    device_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[DeviceService, Depends(get_device_service)],
    _: Annotated[User, Depends(require_admin)],
) -> DeviceStatusRead:
    try:
        device_status = await service.get_status(session, device_id)
    except EzvizConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "ezviz_not_configured", "message": str(exc)},
        ) from exc
    except (ConnectionError, TimeoutError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "token_cache_unavailable",
                "message": "EZVIZ token cache is temporarily unavailable",
            },
        ) from exc
    except EzvizApiError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": exc.platform_code or "ezviz_upstream_error",
                "message": _public_ezviz_error_message(exc),
                "retryable": exc.retryable,
            },
        ) from exc
    if device_status is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return device_status


def _public_ezviz_error_message(error: EzvizApiError) -> str:
    if error.token_invalid:
        return "EZVIZ authentication failed after refreshing the server token"
    if error.retryable:
        return "EZVIZ is temporarily unavailable; retry later"
    return "EZVIZ rejected the server request; check platform configuration"

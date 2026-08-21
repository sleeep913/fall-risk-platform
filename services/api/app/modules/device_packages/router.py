from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.models.user import User
from app.modules.auth.dependencies import require_admin
from app.modules.device_packages.dependencies import get_device_package_service
from app.modules.device_packages.service import (
    DevicePackageService,
    PackageActivationConflictError,
    PackageActivationTargetError,
    PackageSlotNotConfiguredError,
)
from app.schemas.device_package import (
    PackageActivationRead,
    PackageActivationRequest,
    PackageEntitlementSummary,
    PackageSlotRead,
)

router = APIRouter(prefix="/admin/ezviz/packages", tags=["ezviz-packages"])


@router.get("/entitlements", response_model=PackageEntitlementSummary)
async def package_entitlements(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[DevicePackageService, Depends(get_device_package_service)],
    _: Annotated[User, Depends(require_admin)],
) -> PackageEntitlementSummary:
    return await service.entitlement_summary(session)


@router.get("", response_model=list[PackageSlotRead])
async def list_package_slots(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[DevicePackageService, Depends(get_device_package_service)],
    _: Annotated[User, Depends(require_admin)],
) -> list[PackageSlotRead]:
    return await service.list_slots(session)


@router.post("/activate", response_model=PackageActivationRead)
async def activate_package(
    activation: PackageActivationRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    service: Annotated[DevicePackageService, Depends(get_device_package_service)],
    administrator: Annotated[User, Depends(require_admin)],
) -> PackageActivationRead:
    try:
        return await service.activate(session, activation, administrator)
    except PackageSlotNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "package_slot_not_configured", "message": str(exc)},
        ) from exc
    except PackageActivationConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "package_activation_conflict", "message": str(exc)},
        ) from exc
    except PackageActivationTargetError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "package_target_invalid", "message": str(exc)},
        ) from exc

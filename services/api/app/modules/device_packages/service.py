from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.models.device import Device, DeviceChannel, DeviceOnlineStatus
from app.models.device_package import DevicePackageActivation, PackageActivationStatus
from app.models.user import User
from app.modules.devices.service import mask_device_serial
from app.modules.ezviz.client import EzvizClient
from app.modules.ezviz.errors import EzvizApiError
from app.modules.ezviz.token_manager import EzvizTokenManager
from app.schemas.device_package import (
    PackageActivationRead,
    PackageActivationRequest,
    PackageEntitlementSummary,
    PackageSlotRead,
)


class PackageSlotNotConfiguredError(Exception):
    pass


class PackageActivationConflictError(Exception):
    pass


class PackageActivationTargetError(Exception):
    pass


class DevicePackageService:
    def __init__(
        self,
        client: EzvizClient,
        token_manager: EzvizTokenManager,
        settings: Settings,
    ) -> None:
        self._client = client
        self._token_manager = token_manager
        self._settings = settings

    async def list_slots(self, session: AsyncSession) -> list[PackageSlotRead]:
        records = (
            await session.scalars(
                select(DevicePackageActivation)
                .options(selectinload(DevicePackageActivation.device))
                .order_by(DevicePackageActivation.package_slot)
            )
        ).all()
        records_by_slot = {record.package_slot: record for record in records}
        configured_slots = self._settings.ezviz_package_codes
        return [
            PackageSlotRead(
                slot=slot,
                configured=slot in configured_slots,
                activation=(
                    to_package_activation_read(records_by_slot[slot])
                    if slot in records_by_slot
                    else None
                ),
            )
            for slot in range(1, 6)
        ]

    async def entitlement_summary(
        self, session: AsyncSession
    ) -> PackageEntitlementSummary:
        token_status = await self._token_manager.cache_status()
        configured_count = len(self._settings.ezviz_package_codes)
        activated_count = await session.scalar(
            select(func.count())
            .select_from(DevicePackageActivation)
            .where(
                DevicePackageActivation.activation_status
                == PackageActivationStatus.SUCCEEDED
            )
        )
        online_device_count = await session.scalar(
            select(func.count())
            .select_from(Device)
            .where(
                Device.is_present.is_(True),
                Device.online_status == DeviceOnlineStatus.ONLINE,
            )
        )
        blockers: list[str] = []
        if not self._settings.ezviz_credentials_configured:
            blockers.append("ezviz_credentials_not_configured")
        elif token_status.state != "valid":
            blockers.append("token_not_authenticated")
        if configured_count == 0:
            blockers.append("no_package_codes_configured")
        if not online_device_count:
            blockers.append("no_online_devices")
        return PackageEntitlementSummary(
            configured_slot_count=configured_count,
            activated_slot_count=activated_count or 0,
            coupon_redeemed=self._settings.ezviz_coupon_redeemed,
            token_status=token_status.state,
            online_device_count=online_device_count or 0,
            activation_ready=not blockers,
            blockers=blockers,
        )

    async def activate(
        self,
        session: AsyncSession,
        request: PackageActivationRequest,
        administrator: User,
    ) -> PackageActivationRead:
        package_code = self._settings.ezviz_package_codes.get(request.package_slot)
        if not package_code:
            raise PackageSlotNotConfiguredError(
                f"Package slot {request.package_slot} is not configured"
            )

        device = await session.scalar(
            select(Device)
            .where(Device.id == request.device_id)
            .options(selectinload(Device.channels))
        )
        if device is None or not device.is_present:
            raise PackageActivationTargetError("Selected device is not available")
        channel = next(
            (
                item
                for item in device.channels
                if item.channel_no == request.channel_no and item.is_present
            ),
            None,
        )
        if channel is None:
            raise PackageActivationTargetError("Selected device channel is not available")
        if not _target_is_online(device, channel):
            raise PackageActivationTargetError(
                "Device and channel must be online before package activation"
            )

        existing_slot = await self._record_for_slot(session, request.package_slot)
        if existing_slot:
            if (
                existing_slot.device_id == device.id
                and existing_slot.channel_no == request.channel_no
            ):
                return to_package_activation_read(existing_slot)
            raise PackageActivationConflictError(
                "This package slot already has an activation record"
            )

        existing_channel = await session.scalar(
            select(DevicePackageActivation)
            .where(
                DevicePackageActivation.device_id == device.id,
                DevicePackageActivation.channel_no == request.channel_no,
            )
            .options(selectinload(DevicePackageActivation.device))
        )
        if existing_channel:
            raise PackageActivationConflictError(
                "This device channel already has a package activation record"
            )

        record = DevicePackageActivation(
            package_slot=request.package_slot,
            package_code_suffix=package_code[-4:],
            device_id=device.id,
            channel_no=request.channel_no,
            activation_status=PackageActivationStatus.PENDING,
            activated_by=administrator.id,
            retry_count=0,
        )
        session.add(record)
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            existing_slot = await self._record_for_slot(session, request.package_slot)
            if existing_slot and (
                existing_slot.device_id == device.id
                and existing_slot.channel_no == request.channel_no
            ):
                return to_package_activation_read(existing_slot)
            raise PackageActivationConflictError(
                "Package slot or device channel was activated concurrently"
            ) from exc

        await session.refresh(record)
        await self._call_activation(record, device, package_code)
        await session.commit()
        await session.refresh(record)
        record.device = device
        return to_package_activation_read(record)

    async def _call_activation(
        self,
        record: DevicePackageActivation,
        device: Device,
        package_code: str,
    ) -> None:
        token: str | None = None
        try:
            token = await self._token_manager.get_valid_token()
            result = await self._client.activate_device_package(
                token, package_code, device.device_serial, record.channel_no
            )
        except EzvizApiError as exc:
            if exc.token_invalid:
                record.retry_count += 1
                try:
                    token = await self._token_manager.get_valid_token(
                        force_refresh=True, stale_token=token
                    )
                    result = await self._client.activate_device_package(
                        token, package_code, device.device_serial, record.channel_no
                    )
                except EzvizApiError as retry_exc:
                    _record_api_error(record, retry_exc, package_code)
                    return
                except (ConnectionError, TimeoutError):
                    _record_transport_error(record)
                    return
            else:
                _record_api_error(record, exc, package_code)
                return
        except (ConnectionError, TimeoutError):
            _record_transport_error(record)
            return

        record.official_code = str(result.active_code)
        record.official_message = _sanitize_message(result.message, package_code)
        if result.active_code == 0:
            record.activation_status = PackageActivationStatus.SUCCEEDED
            record.activated_at = datetime.now(UTC)
        elif result.active_code in {10005, 40001}:
            record.activation_status = PackageActivationStatus.REJECTED
        else:
            record.activation_status = PackageActivationStatus.FAILED

    async def _record_for_slot(
        self, session: AsyncSession, slot: int
    ) -> DevicePackageActivation | None:
        return await session.scalar(
            select(DevicePackageActivation)
            .where(DevicePackageActivation.package_slot == slot)
            .options(selectinload(DevicePackageActivation.device))
        )


def _target_is_online(device: Device, channel: DeviceChannel) -> bool:
    return (
        device.online_status == DeviceOnlineStatus.ONLINE
        and channel.online_status == DeviceOnlineStatus.ONLINE
    )


def _record_api_error(
    record: DevicePackageActivation, error: EzvizApiError, package_code: str
) -> None:
    record.activation_status = (
        PackageActivationStatus.FAILED
        if error.retryable or error.token_invalid
        else PackageActivationStatus.REJECTED
    )
    record.official_code = error.platform_code or (
        str(error.http_status) if error.http_status else "upstream_error"
    )
    record.official_message = _sanitize_message(str(error), package_code)


def _record_transport_error(record: DevicePackageActivation) -> None:
    record.activation_status = PackageActivationStatus.FAILED
    record.official_code = "token_cache_unavailable"
    record.official_message = "萤石 Token 缓存暂时不可用，未确认套餐激活结果"


def _sanitize_message(message: str, package_code: str) -> str:
    return message.replace(package_code, "[redacted]")[:300]


def to_package_activation_read(
    record: DevicePackageActivation,
) -> PackageActivationRead:
    return PackageActivationRead(
        id=record.id,
        package_slot=record.package_slot,
        package_code_suffix=record.package_code_suffix,
        device_id=record.device_id,
        device_name=record.device.name,
        device_serial_masked=mask_device_serial(record.device.device_serial),
        channel_no=record.channel_no,
        activation_status=record.activation_status,
        official_code=record.official_code,
        official_message=record.official_message,
        activated_at=record.activated_at,
        activated_by=record.activated_by,
        retry_count=record.retry_count,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )

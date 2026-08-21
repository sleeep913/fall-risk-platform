from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.models.device import Device, DeviceChannel, DeviceOnlineStatus
from app.modules.ezviz.client import EzvizClient
from app.modules.ezviz.errors import EzvizApiError
from app.modules.ezviz.token_manager import EzvizTokenManager
from app.schemas.device import (
    DeviceChannelRead,
    DeviceRead,
    DeviceStatusRead,
    DeviceSyncResponse,
    EzvizIntegrationStatus,
)


@dataclass(frozen=True)
class RemoteDevice:
    serial: str
    name: str
    model: str | None
    status: DeviceOnlineStatus
    is_encrypted: bool | None
    channel_count: int


@dataclass(frozen=True)
class RemoteChannel:
    serial: str
    channel_no: int
    name: str
    status: DeviceOnlineStatus
    is_encrypted: bool | None
    video_level: int | None


class DeviceService:
    def __init__(
        self,
        client: EzvizClient,
        token_manager: EzvizTokenManager,
        settings: Settings,
    ) -> None:
        self._client = client
        self._token_manager = token_manager
        self._settings = settings

    async def list_devices(self, session: AsyncSession) -> list[DeviceRead]:
        result = await session.scalars(
            select(Device)
            .options(selectinload(Device.channels))
            .order_by(Device.name, Device.id)
        )
        return [to_device_read(device) for device in result.unique().all()]

    async def get_device(self, session: AsyncSession, device_id: int) -> DeviceRead | None:
        device = await session.scalar(
            select(Device)
            .where(Device.id == device_id)
            .options(selectinload(Device.channels))
        )
        return to_device_read(device) if device else None

    async def get_status(
        self, session: AsyncSession, device_id: int
    ) -> DeviceStatusRead | None:
        device = await session.get(Device, device_id)
        if not device:
            return None
        token = await self._token_manager.get_valid_token()
        try:
            payload = await self._client.get_device_info(token, device.device_serial)
        except EzvizApiError as exc:
            if not exc.token_invalid:
                raise
            token = await self._token_manager.get_valid_token(
                force_refresh=True, stale_token=token
            )
            payload = await self._client.get_device_info(token, device.device_serial)
        now = datetime.now(UTC)
        device.online_status = map_online_status(payload.get("status"))
        encryption = _optional_bool(payload.get("isEncrypt"))
        if encryption is not None:
            device.is_encrypted = encryption
        device.last_synced_at = now
        if device.online_status == DeviceOnlineStatus.ONLINE:
            device.last_online_at = now
        await session.commit()
        return DeviceStatusRead(
            id=device.id,
            serial_masked=mask_device_serial(device.device_serial),
            online_status=device.online_status,
            is_encrypted=device.is_encrypted,
            is_present=device.is_present,
            last_online_at=device.last_online_at,
            last_synced_at=device.last_synced_at,
        )

    async def integration_status(
        self, session: AsyncSession
    ) -> EzvizIntegrationStatus:
        token_status = await self._token_manager.cache_status()
        device_count = await session.scalar(
            select(func.count()).select_from(Device).where(Device.is_present.is_(True))
        )
        online_count = await session.scalar(
            select(func.count())
            .select_from(Device)
            .where(
                Device.is_present.is_(True),
                Device.online_status == DeviceOnlineStatus.ONLINE,
            )
        )
        last_synced_at = await session.scalar(select(func.max(Device.last_synced_at)))
        return EzvizIntegrationStatus(
            configured=self._token_manager.configured,
            token_cache=(
                "memory" if self._settings.local_lightweight_mode else "redis"
            ),
            token_status=token_status.state,
            token_expires_at=token_status.expires_at,
            token_refreshed_at=token_status.refreshed_at,
            device_count=device_count or 0,
            online_count=online_count or 0,
            last_synced_at=last_synced_at,
        )

    async def sync(self, session: AsyncSession) -> DeviceSyncResponse:
        device_payloads = await self._fetch_all(self._client.list_devices)
        channel_payloads = await self._fetch_all(self._client.list_channels)
        remote_devices = [parse_device(item) for item in device_payloads]
        remote_channels = [parse_channel(item) for item in channel_payloads]
        return await self._persist(session, remote_devices, remote_channels)

    async def _fetch_all(
        self,
        fetch_page: Callable[
            [str, int, int], Awaitable[tuple[list[dict[str, Any]], int | None]]
        ],
    ) -> list[dict[str, Any]]:
        page_size = self._settings.ezviz_device_sync_page_size
        items: list[dict[str, Any]] = []
        page_start = 0
        token = await self._token_manager.get_valid_token()
        token_was_retried = False
        while page_start < 100:
            try:
                page_items, total = await fetch_page(token, page_start, page_size)
            except EzvizApiError as exc:
                if not exc.token_invalid or token_was_retried:
                    raise
                token = await self._token_manager.get_valid_token(
                    force_refresh=True, stale_token=token
                )
                token_was_retried = True
                continue
            items.extend(page_items)
            if not page_items or len(page_items) < page_size:
                break
            if total is not None and len(items) >= total:
                break
            page_start += 1
        else:
            raise EzvizApiError("EZVIZ pagination exceeded the safety limit")
        return items

    async def _persist(
        self,
        session: AsyncSession,
        remote_devices: list[RemoteDevice],
        remote_channels: list[RemoteChannel],
    ) -> DeviceSyncResponse:
        now = datetime.now(UTC)
        existing = {
            device.device_serial: device
            for device in (
                await session.scalars(
                    select(Device).where(Device.provider == "ezviz")
                )
            ).all()
        }
        for device in existing.values():
            device.is_present = False

        channels_by_serial: dict[str, list[RemoteChannel]] = defaultdict(list)
        for channel in remote_channels:
            channels_by_serial[channel.serial].append(channel)

        remote_by_serial = {device.serial: device for device in remote_devices}
        for serial, channels in channels_by_serial.items():
            if serial not in remote_by_serial:
                remote_by_serial[serial] = RemoteDevice(
                    serial=serial,
                    name=f"EZVIZ {mask_device_serial(serial)}",
                    model=None,
                    status=DeviceOnlineStatus.UNKNOWN,
                    is_encrypted=None,
                    channel_count=len(channels),
                )

        created = 0
        updated = 0
        for serial, remote in remote_by_serial.items():
            device = existing.get(serial)
            if device is None:
                device = Device(
                    provider="ezviz",
                    device_serial=serial,
                    name=remote.name,
                    model=remote.model,
                    online_status=remote.status,
                    is_encrypted=remote.is_encrypted,
                    channel_count=max(
                        remote.channel_count, len(channels_by_serial[serial])
                    ),
                    is_present=True,
                    last_synced_at=now,
                )
                session.add(device)
                existing[serial] = device
                created += 1
            else:
                device.name = remote.name
                device.model = remote.model
                device.online_status = remote.status
                device.is_encrypted = remote.is_encrypted
                device.channel_count = max(
                    remote.channel_count, len(channels_by_serial[serial])
                )
                device.is_present = True
                device.last_synced_at = now
                updated += 1
            if remote.status == DeviceOnlineStatus.ONLINE:
                device.last_online_at = now

        await session.flush()
        existing_channels = {
            (channel.device_id, channel.channel_no): channel
            for channel in (
                await session.scalars(
                    select(DeviceChannel)
                    .join(Device)
                    .where(Device.provider == "ezviz")
                )
            ).all()
        }
        for channel in existing_channels.values():
            channel.is_present = False

        for remote in remote_channels:
            device = existing[remote.serial]
            key = (device.id, remote.channel_no)
            channel = existing_channels.get(key)
            if channel is None:
                channel = DeviceChannel(
                    device_id=device.id,
                    channel_no=remote.channel_no,
                    name=remote.name,
                    online_status=remote.status,
                    is_encrypted=remote.is_encrypted,
                    video_level=remote.video_level,
                    is_present=True,
                    last_synced_at=now,
                )
                session.add(channel)
            else:
                channel.name = remote.name
                channel.online_status = remote.status
                channel.is_encrypted = remote.is_encrypted
                channel.video_level = remote.video_level
                channel.is_present = True
                channel.last_synced_at = now
            if remote.status == DeviceOnlineStatus.ONLINE:
                channel.last_online_at = now

        await session.commit()
        return DeviceSyncResponse(
            created=created,
            updated=updated,
            missing=sum(not device.is_present for device in existing.values()),
            channel_count=len(remote_channels),
            synced_at=now,
        )


def parse_device(item: dict[str, Any]) -> RemoteDevice:
    serial = _required_text(item.get("deviceSerial"), "deviceSerial")
    channel_count = _optional_int(item.get("cameraNum")) or 0
    return RemoteDevice(
        serial=serial,
        name=_optional_text(item.get("deviceName")) or f"EZVIZ {mask_device_serial(serial)}",
        model=_optional_text(item.get("deviceType")),
        status=map_online_status(item.get("status")),
        is_encrypted=_optional_bool(item.get("isEncrypt")),
        channel_count=max(0, channel_count),
    )


def parse_channel(item: dict[str, Any]) -> RemoteChannel:
    serial = _required_text(item.get("deviceSerial"), "deviceSerial")
    channel_no = _optional_int(item.get("channelNo"))
    if channel_no is None or channel_no < 1:
        raise EzvizApiError("EZVIZ channel response contained invalid channelNo")
    return RemoteChannel(
        serial=serial,
        channel_no=channel_no,
        name=_optional_text(item.get("channelName")) or f"通道 {channel_no}",
        status=map_online_status(item.get("status")),
        is_encrypted=_optional_bool(item.get("isEncrypt")),
        video_level=_optional_int(item.get("videoLevel")),
    )


def map_online_status(value: object) -> DeviceOnlineStatus:
    if value in (1, "1", True, "online"):
        return DeviceOnlineStatus.ONLINE
    if value in (0, "0", 2, "2", False, "offline"):
        return DeviceOnlineStatus.OFFLINE
    return DeviceOnlineStatus.UNKNOWN


def mask_device_serial(serial: str) -> str:
    if len(serial) <= 4:
        return "*" * len(serial)
    if len(serial) <= 8:
        return f"{serial[:2]}{'*' * (len(serial) - 4)}{serial[-2:]}"
    return f"{serial[:3]}{'*' * (len(serial) - 7)}{serial[-4:]}"


def to_device_read(device: Device) -> DeviceRead:
    return DeviceRead(
        id=device.id,
        provider=device.provider,
        serial_masked=mask_device_serial(device.device_serial),
        name=device.name,
        model=device.model,
        online_status=device.online_status,
        is_encrypted=device.is_encrypted,
        channel_count=device.channel_count,
        is_present=device.is_present,
        last_online_at=device.last_online_at,
        last_synced_at=device.last_synced_at,
        channels=[DeviceChannelRead.model_validate(channel) for channel in device.channels],
    )


def _required_text(value: object, field: str) -> str:
    text = _optional_text(value)
    if not text:
        raise EzvizApiError(f"EZVIZ response omitted {field}")
    return text


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _optional_bool(value: object) -> bool | None:
    if value in (1, "1", True, "true"):
        return True
    if value in (0, "0", False, "false"):
        return False
    return None

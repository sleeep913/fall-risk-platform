from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.device import DeviceOnlineStatus


class DeviceChannelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    channel_no: int
    name: str
    online_status: DeviceOnlineStatus
    is_encrypted: bool | None
    video_level: int | None
    is_present: bool
    last_online_at: datetime | None
    last_synced_at: datetime


class DeviceRead(BaseModel):
    id: int
    provider: str
    serial_masked: str
    name: str
    model: str | None
    online_status: DeviceOnlineStatus
    is_encrypted: bool | None
    channel_count: int
    is_present: bool
    last_online_at: datetime | None
    last_synced_at: datetime
    channels: list[DeviceChannelRead]


class DeviceStatusRead(BaseModel):
    id: int
    serial_masked: str
    online_status: DeviceOnlineStatus
    is_encrypted: bool | None
    is_present: bool
    last_online_at: datetime | None
    last_synced_at: datetime


class DeviceSyncResponse(BaseModel):
    created: int
    updated: int
    missing: int
    channel_count: int
    synced_at: datetime


class EzvizIntegrationStatus(BaseModel):
    configured: bool
    token_cache: str
    token_status: str
    token_expires_at: datetime | None
    token_refreshed_at: datetime | None
    device_count: int
    online_count: int
    last_synced_at: datetime | None

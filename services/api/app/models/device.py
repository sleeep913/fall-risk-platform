from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class DeviceOnlineStatus(StrEnum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class Device(TimestampMixin, Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(32), default="ezviz", nullable=False)
    device_serial: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    online_status: Mapped[DeviceOnlineStatus] = mapped_column(
        SqlEnum(
            DeviceOnlineStatus,
            name="device_online_status",
            native_enum=False,
            values_callable=lambda members: [member.value for member in members],
        ),
        default=DeviceOnlineStatus.UNKNOWN,
        nullable=False,
    )
    is_encrypted: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    channel_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_present: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_online_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    channels: Mapped[list["DeviceChannel"]] = relationship(
        back_populates="device", cascade="all, delete-orphan"
    )


class DeviceChannel(TimestampMixin, Base):
    __tablename__ = "device_channels"
    __table_args__ = (
        UniqueConstraint("device_id", "channel_no", name="uq_device_channel"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    device_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), index=True, nullable=False
    )
    channel_no: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    online_status: Mapped[DeviceOnlineStatus] = mapped_column(
        SqlEnum(
            DeviceOnlineStatus,
            name="channel_online_status",
            native_enum=False,
            values_callable=lambda members: [member.value for member in members],
        ),
        default=DeviceOnlineStatus.UNKNOWN,
        nullable=False,
    )
    is_encrypted: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    video_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_present: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_online_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    device: Mapped[Device] = relationship(back_populates="channels")

from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class PackageActivationStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    REJECTED = "rejected"
    FAILED = "failed"


class DevicePackageActivation(TimestampMixin, Base):
    __tablename__ = "device_package_activations"
    __table_args__ = (
        UniqueConstraint("package_slot", name="uq_device_package_slot"),
        UniqueConstraint("device_id", "channel_no", name="uq_device_package_channel"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    package_slot: Mapped[int] = mapped_column(Integer, nullable=False)
    package_code_suffix: Mapped[str] = mapped_column(String(4), nullable=False)
    device_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    channel_no: Mapped[int] = mapped_column(Integer, nullable=False)
    activation_status: Mapped[PackageActivationStatus] = mapped_column(
        SqlEnum(
            PackageActivationStatus,
            name="package_activation_status",
            native_enum=False,
            values_callable=lambda members: [member.value for member in members],
        ),
        default=PackageActivationStatus.PENDING,
        nullable=False,
    )
    official_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    official_message: Mapped[str | None] = mapped_column(String(300), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    activated_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    device = relationship("Device")
    administrator = relationship("User")

from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, Boolean, DateTime, String, Text
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class OfflineVideoOrigin(StrEnum):
    PUBLIC_DATASET = "public_dataset"
    SELF_RECORDED = "self_recorded"
    SYNTHETIC = "synthetic"
    OTHER = "other"


class OfflineVideoLabel(StrEnum):
    FALL = "fall"
    ADL = "adl"
    NEAR_FALL = "near_fall"
    UNKNOWN = "unknown"


class OfflineVideo(TimestampMixin, Base):
    __tablename__ = "offline_videos"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    relative_path: Mapped[str] = mapped_column(
        String(512), unique=True, index=True, nullable=False
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    dataset_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    origin: Mapped[OfflineVideoOrigin] = mapped_column(
        SqlEnum(
            OfflineVideoOrigin,
            name="offline_video_origin",
            native_enum=False,
            values_callable=lambda members: [member.value for member in members],
        ),
        default=OfflineVideoOrigin.OTHER,
        nullable=False,
    )
    label: Mapped[OfflineVideoLabel] = mapped_column(
        SqlEnum(
            OfflineVideoLabel,
            name="offline_video_label",
            native_enum=False,
            values_callable=lambda members: [member.value for member in members],
        ),
        default=OfflineVideoLabel.UNKNOWN,
        nullable=False,
    )
    media_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    license_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    file_modified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_scanned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

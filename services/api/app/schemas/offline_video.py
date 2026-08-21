from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.offline_video import OfflineVideoLabel, OfflineVideoOrigin


class OfflineVideoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    relative_path: str
    file_name: str
    display_name: str
    dataset_name: str | None
    origin: OfflineVideoOrigin
    label: OfflineVideoLabel
    media_type: str
    size_bytes: int
    source_url: str | None
    license_note: str | None
    is_available: bool
    file_modified_at: datetime
    last_scanned_at: datetime
    created_at: datetime
    updated_at: datetime
    requires_transcoding: bool


class OfflineVideoUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    dataset_name: str | None = Field(default=None, max_length=120)
    origin: OfflineVideoOrigin | None = None
    label: OfflineVideoLabel | None = None
    source_url: str | None = Field(default=None, max_length=500)
    license_note: str | None = Field(default=None, max_length=1000)

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str | None) -> str:
        if value is None or not value.strip():
            raise ValueError("display_name cannot be empty")
        return value.strip()

    @field_validator("dataset_name", "source_url", "license_note")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class OfflineVideoLibraryStatus(BaseModel):
    root_hint: str
    supported_extensions: list[str]
    total_count: int
    available_count: int
    labeled_count: int
    dataset_count: int
    last_scanned_at: datetime | None
    inference_enabled: bool = False
    transcoding_enabled: bool = True


class OfflineVideoScanResponse(BaseModel):
    created: int
    updated: int
    missing: int
    total: int
    scanned_at: datetime


class OfflineVideoPlaybackTicket(BaseModel):
    url: str
    expires_at: datetime
    transcoded: bool

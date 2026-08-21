from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: Literal["development", "test", "production"] = "development"
    app_name: str = "Fall Risk Platform"
    app_version: str = "0.1.0"
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://localhost:8080"]
    )

    jwt_secret: str = "development-only-secret-change-before-deploy"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    refresh_cookie_name: str = "fall_risk_refresh"
    cookie_secure: bool = False
    initial_admin_username: str | None = None
    initial_admin_password: str | None = None

    database_url: str = "sqlite+aiosqlite:///./fall_risk.db"
    auto_create_tables: bool = False
    local_lightweight_mode: bool = False
    redis_url: str = "redis://localhost:6379/0"
    minio_endpoint: str = "localhost:9000"
    minio_secure: bool = False
    health_check_timeout_seconds: float = 2.0

    ezviz_api_base_url: str = "https://open.ys7.com"
    ezviz_app_key: SecretStr | None = None
    ezviz_app_secret: SecretStr | None = None
    ezviz_request_timeout_seconds: float = 10.0
    ezviz_token_refresh_skew_seconds: int = 600
    ezviz_token_lock_timeout_seconds: int = 15
    ezviz_device_sync_page_size: int = 50
    ezviz_package_code_01: SecretStr | None = None
    ezviz_package_code_02: SecretStr | None = None
    ezviz_package_code_03: SecretStr | None = None
    ezviz_package_code_04: SecretStr | None = None
    ezviz_package_code_05: SecretStr | None = None
    ezviz_coupon_redeemed: bool = False

    offline_video_root: Path = Path("../../data/offline-videos")
    offline_video_cache_root: Path = Path("../../data/local/offline-video-cache")
    offline_playback_ticket_expire_seconds: int = 1800
    offline_video_transcode_timeout_seconds: int = 300

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        if len(self.jwt_secret) < 32:
            raise ValueError("JWT_SECRET must contain at least 32 characters")
        if self.app_env == "production" and self.jwt_secret.startswith("development-only"):
            raise ValueError("Production requires a unique JWT_SECRET")
        if self.app_env == "production" and not self.cookie_secure:
            raise ValueError("Production requires COOKIE_SECURE=true")
        if bool(self.initial_admin_username) != bool(self.initial_admin_password):
            raise ValueError(
                "INITIAL_ADMIN_USERNAME and INITIAL_ADMIN_PASSWORD must be configured together"
            )
        if self.initial_admin_password and len(self.initial_admin_password) < 12:
            raise ValueError("INITIAL_ADMIN_PASSWORD must contain at least 12 characters")
        has_ezviz_key = bool(
            self.ezviz_app_key and self.ezviz_app_key.get_secret_value().strip()
        )
        has_ezviz_secret = bool(
            self.ezviz_app_secret and self.ezviz_app_secret.get_secret_value().strip()
        )
        if has_ezviz_key != has_ezviz_secret:
            raise ValueError("EZVIZ_APP_KEY and EZVIZ_APP_SECRET must be configured together")
        if not 1 <= self.ezviz_device_sync_page_size <= 50:
            raise ValueError("EZVIZ_DEVICE_SYNC_PAGE_SIZE must be between 1 and 50")
        if not 60 <= self.offline_playback_ticket_expire_seconds <= 3600:
            raise ValueError(
                "OFFLINE_PLAYBACK_TICKET_EXPIRE_SECONDS must be between 60 and 3600"
            )
        if not 30 <= self.offline_video_transcode_timeout_seconds <= 1800:
            raise ValueError(
                "OFFLINE_VIDEO_TRANSCODE_TIMEOUT_SECONDS must be between 30 and 1800"
            )
        return self

    @property
    def ezviz_credentials_configured(self) -> bool:
        return bool(
            self.ezviz_app_key
            and self.ezviz_app_key.get_secret_value().strip()
            and self.ezviz_app_secret
            and self.ezviz_app_secret.get_secret_value().strip()
        )

    @property
    def ezviz_package_codes(self) -> dict[int, str]:
        values = (
            self.ezviz_package_code_01,
            self.ezviz_package_code_02,
            self.ezviz_package_code_03,
            self.ezviz_package_code_04,
            self.ezviz_package_code_05,
        )
        return {
            slot: secret.get_secret_value().strip()
            for slot, secret in enumerate(values, start=1)
            if secret and secret.get_secret_value().strip()
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()

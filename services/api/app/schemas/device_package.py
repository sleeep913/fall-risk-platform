from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.device_package import PackageActivationStatus


class PackageActivationRead(BaseModel):
    id: int
    package_slot: int
    package_code_suffix: str
    device_id: int
    device_name: str
    device_serial_masked: str
    channel_no: int
    activation_status: PackageActivationStatus
    official_code: str | None
    official_message: str | None
    activated_at: datetime | None
    activated_by: int
    retry_count: int
    created_at: datetime
    updated_at: datetime


class PackageSlotRead(BaseModel):
    slot: int
    configured: bool
    activation: PackageActivationRead | None


class PackageEntitlementSummary(BaseModel):
    source: Literal["competition_notice"] = "competition_notice"
    package_slots_total: int = 5
    configured_slot_count: int
    activated_slot_count: int
    validity_months: int = 6
    coupon_redeemed: bool
    token_status: str
    online_device_count: int
    activation_ready: bool
    blockers: list[str]


class PackageActivationRequest(BaseModel):
    package_slot: int = Field(ge=1, le=5)
    device_id: int = Field(gt=0)
    channel_no: int = Field(gt=0)
    confirmed: Literal[True]

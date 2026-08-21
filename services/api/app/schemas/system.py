from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    version: str
    timestamp: datetime


class DependencyHealth(BaseModel):
    status: Literal["ok", "error", "disabled"]
    detail: str | None = None


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    mode: Literal["full", "lightweight"]
    checks: dict[str, DependencyHealth]
    timestamp: datetime

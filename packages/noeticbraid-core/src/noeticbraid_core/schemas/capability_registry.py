"""Capability registry schemas for SDD-D2-02/D2-03 first-stage health checks."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from ._common import COMMON_MODEL_CONFIG, empty_str_to_none, ensure_optional_utc_datetime

HealthMode = Literal["mock", "live_opt_in"]
CapabilityStatus = Literal[
    "unknown",
    "available",
    "degraded",
    "unavailable",
    "healthy",
    "unhealthy",
    "not_implemented",
]
EndType = Literal["cli", "web"]


class CapabilityHealthResult(BaseModel):
    """Single health-check result, mock by default and live only after env opt-in."""

    model_config = COMMON_MODEL_CONFIG

    capability_id: str = Field(..., min_length=1, max_length=128)
    mode: HealthMode
    status: CapabilityStatus
    checked_at: datetime
    summary: str = Field(..., min_length=1, max_length=1024)
    artifact_ref: Optional[str] = Field(default=None, max_length=1024)
    version: Optional[str] = Field(default=None, max_length=256)
    last_checked: Optional[datetime] = None
    error_msg: Optional[str] = Field(default=None, max_length=256)

    @field_validator("checked_at")
    @classmethod
    def _checked_at_utc(cls, value: datetime) -> datetime:
        normalized = ensure_optional_utc_datetime(value)
        assert normalized is not None
        return normalized

    @field_validator("last_checked")
    @classmethod
    def _last_checked_utc(cls, value: Optional[datetime]) -> Optional[datetime]:
        return ensure_optional_utc_datetime(value)

    @field_validator("artifact_ref", "version", "error_msg", mode="before")
    @classmethod
    def _blank_optional_text_to_none(cls, value: object) -> object:
        return empty_str_to_none(value)


class CapabilityRegistryEntry(BaseModel):
    """First-stage provider capability registry entry."""

    model_config = COMMON_MODEL_CONFIG

    capability_id: str = Field(..., min_length=1, max_length=128)
    display_name: str = Field(..., min_length=1, max_length=128)
    provider: str = Field(..., min_length=1, max_length=64)
    end_type: EndType
    status: CapabilityStatus = "unknown"
    health_mode: HealthMode = "mock"
    last_checked_at: Optional[datetime] = None
    last_result: Optional[CapabilityHealthResult] = None
    source_ref: str = Field(..., min_length=1, max_length=256)
    first_stage: bool = True

    @field_validator("last_checked_at")
    @classmethod
    def _last_checked_at_utc(cls, value: Optional[datetime]) -> Optional[datetime]:
        return ensure_optional_utc_datetime(value)

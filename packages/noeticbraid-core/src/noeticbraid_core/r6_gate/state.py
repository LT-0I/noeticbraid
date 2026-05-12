"""Shared R-6 candidate gate state for embeddable candidate schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from noeticbraid_core.schemas._common import COMMON_MODEL_CONFIG, ensure_optional_utc_datetime


class R6GateState(BaseModel):
    """Embeddable R-6 candidate→confirmed gate state."""

    model_config = COMMON_MODEL_CONFIG

    reuse_count: int = Field(default=0, ge=0)
    ledger_evidence_refs: list[str] = Field(default_factory=list, max_length=100)
    adopted_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    r6_gate_schema_version: Literal["1.0.0"] = "1.0.0"

    @field_validator("adopted_at", "expires_at")
    @classmethod
    def _optional_datetimes_utc(cls, value: Optional[datetime]) -> Optional[datetime]:
        return ensure_optional_utc_datetime(value)

    @field_validator("ledger_evidence_refs")
    @classmethod
    def _dedupe_non_blank_refs(cls, value: list[str]) -> list[str]:
        refs: list[str] = []
        seen: set[str] = set()
        for item in value:
            text = str(item).strip()
            if not text:
                raise ValueError("ledger_evidence_refs must not contain blank values")
            if text not in seen:
                refs.append(text)
                seen.add(text)
        return refs

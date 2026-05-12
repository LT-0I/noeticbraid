"""SideNote opt-out state for SDD-D2-05.

This schema is intentionally separate from the frozen SideNote v2 contract. It
represents user-side program state only and must not be written into the
Obsidian vault or raw user notes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ._common import COMMON_MODEL_CONFIG, ensure_utc_datetime, utc_now

SideNoteOptOutNoteType = Literal["fact", "hypothesis", "action_suggestion"]

THROTTLE_REBUT_THRESHOLD = 3
THROTTLE_ROLLING_WINDOW_DAYS = 30
THROTTLE_COOLDOWN_DAYS = 30
DEFAULT_B1_COOLDOWN_DAYS = 14


class RebutRecord(BaseModel):
    """One explicit user rebuttal of a SideNote."""

    model_config = COMMON_MODEL_CONFIG

    note_id: str = Field(..., min_length=1)
    note_type: SideNoteOptOutNoteType
    timestamp: datetime = Field(default_factory=utc_now)

    @field_validator("timestamp")
    @classmethod
    def _ensure_timestamp_utc(cls, value: datetime) -> datetime:
        return ensure_utc_datetime(value)


class SideNoteOptOutState(BaseModel):
    """Persisted opt-out controls for b-1 SideNote generation."""

    model_config = COMMON_MODEL_CONFIG

    disabled_note_types: list[SideNoteOptOutNoteType] = Field(default_factory=list)
    throttled_note_types: list[SideNoteOptOutNoteType] = Field(default_factory=list)
    rebut_history: list[RebutRecord] = Field(default_factory=list)
    paused: bool = False
    last_updated: datetime = Field(default_factory=utc_now)
    opt_out_schema_version: Literal["1.0.0"] = "1.0.0"

    @field_validator("last_updated")
    @classmethod
    def _ensure_last_updated_utc(cls, value: datetime) -> datetime:
        return ensure_utc_datetime(value)

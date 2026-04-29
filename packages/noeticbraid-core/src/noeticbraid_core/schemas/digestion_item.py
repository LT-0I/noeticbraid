"""DigestionItem model (Stage 1 GPT-A full implementation, candidate_for: 1.0.0)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from ._common import (
    COMMON_MODEL_CONFIG,
    empty_str_to_none,
    ensure_optional_utc_datetime,
    ensure_utc_datetime,
    utc_now,
)


class DigestionItem(BaseModel):
    """A spaced-review item derived from a SideNote."""

    model_config = COMMON_MODEL_CONFIG

    digestion_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        pattern=r"^digestion_[A-Za-z0-9_]+$",
        description="Stable digestion identifier prefixed with 'digestion_'.",
    )
    side_note_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        pattern=r"^note_[A-Za-z0-9_]+$",
        description="Side note from which this digestion item was created.",
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        description="Digestion item creation timestamp normalized to UTC.",
    )
    c_status: Literal["c0", "c1", "c2", "c3", "c4", "cX"] = Field(
        default="c0", description="Review cadence state."
    )
    user_response_ref: Optional[str] = Field(
        default=None,
        max_length=128,
        description="Optional reference to the user response that updated this item.",
    )
    next_review_at: Optional[datetime] = Field(
        default=None,
        description="Optional next review timestamp normalized to UTC.",
    )
    status: Literal["open", "closed", "rejected", "snoozed"] = Field(
        default="open", description="Current digestion workflow status."
    )

    @field_validator("created_at")
    @classmethod
    def _ensure_created_at_utc(cls, value: datetime) -> datetime:
        return ensure_utc_datetime(value)

    @field_validator("next_review_at")
    @classmethod
    def _ensure_next_review_at_utc(cls, value: Optional[datetime]) -> Optional[datetime]:
        return ensure_optional_utc_datetime(value)

    @field_validator("user_response_ref", mode="before")
    @classmethod
    def _blank_user_response_ref_to_none(cls, value: object) -> object:
        return empty_str_to_none(value)

    def is_overdue(self, now: datetime) -> bool:
        """Whether an open or snoozed item is past its next review timestamp."""

        if self.next_review_at is None or self.status not in ("open", "snoozed"):
            return False
        return self.next_review_at <= ensure_utc_datetime(now)

    def is_closed(self) -> bool:
        """Whether the item is no longer active."""

        return self.status in ("closed", "rejected")

    def needs_review(self, now: datetime) -> bool:
        """Whether the item is open and due for review now."""

        return self.status == "open" and self.is_overdue(now)

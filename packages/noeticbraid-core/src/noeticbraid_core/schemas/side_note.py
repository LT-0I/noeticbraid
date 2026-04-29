"""SideNote model (Stage 1 GPT-A full implementation, candidate_for: 1.0.0)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from ._common import (
    COMMON_MODEL_CONFIG,
    empty_str_to_none,
    ensure_utc_datetime,
    utc_now,
    validate_ref_list,
)


class SideNote(BaseModel):
    """A lightweight note or challenge surfaced during work on a task."""

    model_config = COMMON_MODEL_CONFIG

    note_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        pattern=r"^note_[A-Za-z0-9_]+$",
        description="Stable note identifier prefixed with 'note_'.",
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        description="Note creation timestamp normalized to UTC.",
    )
    linked_source_refs: list[str] = Field(
        default_factory=list,
        max_length=100,
        description="Source references supporting or challenging the note.",
    )
    note_type: Literal["fact", "hypothesis", "challenge", "action"] = Field(
        ..., description="Type of side note."
    )
    claim: str = Field(..., min_length=1, max_length=4096, description="Claim or action text.")
    confidence: Literal["low", "medium", "high"] = Field(
        ..., description="Confidence in the claim."
    )
    user_response: Literal["unread", "accepted", "rejected", "modified"] = Field(
        default="unread", description="User handling state for the note."
    )
    follow_up_ref: Optional[str] = Field(
        default=None,
        max_length=128,
        description="Optional follow-up task, approval, note, or digestion reference.",
    )

    @field_validator("created_at")
    @classmethod
    def _ensure_created_at_utc(cls, value: datetime) -> datetime:
        return ensure_utc_datetime(value)

    @field_validator("linked_source_refs")
    @classmethod
    def _validate_source_refs(cls, value: list[str]) -> list[str]:
        return validate_ref_list(value, prefix="source_", field_name="linked_source_refs")

    @field_validator("follow_up_ref", mode="before")
    @classmethod
    def _blank_follow_up_ref_to_none(cls, value: object) -> object:
        return empty_str_to_none(value)

    def has_sources(self) -> bool:
        """Whether the side note links at least one source record."""

        return bool(self.linked_source_refs)

    def is_actionable(self) -> bool:
        """Whether this note likely needs follow-up work."""

        return self.note_type in ("challenge", "action") and self.user_response in (
            "unread",
            "modified",
        )

    def is_user_resolved(self) -> bool:
        """Whether the user has accepted, rejected, or modified the note."""

        return self.user_response in ("accepted", "rejected", "modified")

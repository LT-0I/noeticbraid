"""SideNote models.

``SideNote`` is the breaking contract 2.0.0 schema introduced by SDD-D1-01.
``SideNoteV1`` preserves the frozen 1.2.0 backend contract shape for callers
that must not inherit the v2 metadata requirements.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from ._common import (
    COMMON_MODEL_CONFIG,
    empty_str_to_none,
    ensure_utc_datetime,
    utc_now,
    validate_ref_list,
)

TONE_CONSTRAINT_LITERAL = "不审判用户 / 不羞辱用户 / 不替用户解释自己；违反任一构成 fatal"
USER_RESPONSE_CHANNEL_VALUES = ("accept", "rebut", "mark_inaccurate", "disable_this_type")
SOURCE_OR_PATH_LINE_REF_PATTERN = re.compile(r"^(?:source_[A-Za-z0-9_]+|\S+:\d+)$")


def _validate_source_or_path_line_refs(values: list[str], *, field_name: str) -> list[str]:
    """Validate source_ references or path:line evidence references without duplicates."""

    seen: set[str] = set()
    for item in values:
        if not SOURCE_OR_PATH_LINE_REF_PATTERN.fullmatch(item):
            raise ValueError(
                f"{field_name} must match source_[A-Za-z0-9_]+ or non-space path:line"
            )
        if item in seen:
            raise ValueError(f"{field_name} must not contain duplicate references")
        seen.add(item)
    return values


class SideNoteV1(BaseModel):
    """Frozen backend contract 1.2.0 SideNote shape."""

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


class SideNote(BaseModel):
    """Contract 2.0.0 side note with required §11.b.S safety metadata."""

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
    evidence_source: list[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Required source references mirrored from linked_source_refs.",
    )
    note_type: Literal["fact", "hypothesis", "action_suggestion"] = Field(
        ..., description="Type of side note."
    )
    claim: str = Field(..., min_length=1, max_length=4096, description="Claim or action text.")
    confidence: Literal["low", "medium", "high"] = Field(
        ..., description="Confidence in the claim."
    )
    user_response: Literal["unread", "accepted", "rejected", "modified"] = Field(
        default="unread", description="User handling state for the note."
    )
    tone_constraint: Literal[
        "不审判用户 / 不羞辱用户 / 不替用户解释自己；违反任一构成 fatal"
    ] = Field(..., description="Canonical non-judgment safety commitment.")
    user_response_channel: list[
        Literal["accept", "rebut", "mark_inaccurate", "disable_this_type"]
    ] = Field(
        ...,
        min_length=4,
        max_length=4,
        description="Visible user response capabilities for this side note.",
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
        return _validate_source_or_path_line_refs(value, field_name="linked_source_refs")

    @field_validator("evidence_source")
    @classmethod
    def _validate_evidence_source_refs(cls, value: list[str]) -> list[str]:
        return _validate_source_or_path_line_refs(value, field_name="evidence_source")

    @field_validator("user_response_channel")
    @classmethod
    def _validate_user_response_channel(
        cls,
        value: list[Literal["accept", "rebut", "mark_inaccurate", "disable_this_type"]],
    ) -> list[Literal["accept", "rebut", "mark_inaccurate", "disable_this_type"]]:
        if len(set(value)) != len(value):
            raise ValueError("user_response_channel must not contain duplicate actions")
        if set(value) != set(USER_RESPONSE_CHANNEL_VALUES):
            raise ValueError("user_response_channel must include all required actions")
        return value

    @field_validator("follow_up_ref", mode="before")
    @classmethod
    def _blank_follow_up_ref_to_none(cls, value: object) -> object:
        return empty_str_to_none(value)

    @model_validator(mode="after")
    def _evidence_source_mirrors_linked_refs(self) -> "SideNote":
        if self.evidence_source != self.linked_source_refs:
            raise ValueError("evidence_source must exactly match linked_source_refs")
        return self

    def has_sources(self) -> bool:
        """Whether the side note links at least one source record."""

        return bool(self.linked_source_refs)

    def is_actionable(self) -> bool:
        """Whether this note likely needs follow-up work."""

        return self.note_type in ("hypothesis", "action_suggestion") and self.user_response in (
            "unread",
            "modified",
        )

    def is_user_resolved(self) -> bool:
        """Whether the user has accepted, rejected, or modified the note."""

        return self.user_response in ("accepted", "rejected", "modified")

"""ApprovalRequest model (Stage 1 GPT-A full implementation, candidate_for: 1.0.0)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from ._common import COMMON_MODEL_CONFIG, empty_str_to_none, ensure_utc_datetime, utc_now


class ApprovalRequest(BaseModel):
    """A request for user approval before performing a sensitive action."""

    model_config = COMMON_MODEL_CONFIG

    approval_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        pattern=r"^approval_[A-Za-z0-9_]+$",
        description="Stable approval identifier prefixed with 'approval_'.",
    )
    task_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        pattern=r"^task_[A-Za-z0-9_]+$",
        description="Task requesting approval.",
    )
    run_id: Optional[str] = Field(
        default=None,
        max_length=128,
        pattern=r"^run_[A-Za-z0-9_]+$",
        description="Optional run identifier that raised this request.",
    )
    approval_level: Literal["none", "light", "strong", "forbidden"] = Field(
        ..., description="Approval strength needed for the requested action."
    )
    requested_at: datetime = Field(
        default_factory=utc_now,
        description="Approval request timestamp normalized to UTC.",
    )
    requested_action: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        description="Action that requires approval.",
    )
    reason: str = Field(
        ...,
        min_length=1,
        max_length=4096,
        description="Reason the action requires approval or is blocked.",
    )
    diff_ref: Optional[str] = Field(
        default=None,
        max_length=256,
        description="Optional diff or artifact reference for user review.",
    )
    status: Literal["pending", "approved", "rejected", "blocked"] = Field(
        default="pending", description="Current approval decision status."
    )

    @field_validator("requested_at")
    @classmethod
    def _ensure_requested_at_utc(cls, value: datetime) -> datetime:
        return ensure_utc_datetime(value)

    @field_validator("run_id", "diff_ref", mode="before")
    @classmethod
    def _blank_optional_strings_to_none(cls, value: object) -> object:
        return empty_str_to_none(value)

    def is_resolved(self) -> bool:
        """Whether a pending user decision is no longer outstanding."""

        return self.status in ("approved", "rejected", "blocked")

    def is_approved(self) -> bool:
        """Whether the requested action has been approved."""

        return self.status == "approved"

    def needs_user_decision(self) -> bool:
        """Whether the request is still pending and can be shown in an approval queue."""

        return self.status == "pending" and self.approval_level not in ("none", "forbidden")

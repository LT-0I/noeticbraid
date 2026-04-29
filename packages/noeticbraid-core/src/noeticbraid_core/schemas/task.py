"""Task model (Stage 1 GPT-A full implementation, candidate_for: 1.0.0)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from ._common import COMMON_MODEL_CONFIG, empty_str_to_none, ensure_utc_datetime, utc_now


class Task(BaseModel):
    """A user-facing unit of work in the Project Conversation Workspace.

    Stage 1 candidate. Contract remains 0.1.0 until the local main session
    completes double review and the freeze flow.
    """

    model_config = COMMON_MODEL_CONFIG

    task_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        pattern=r"^task_[A-Za-z0-9_]+$",
        description="Stable task identifier prefixed with 'task_'.",
    )
    task_type: Literal["project_planning", "research", "code_review"] = Field(
        ..., description="Phase 1.1 supported task categories."
    )
    risk_level: Literal["low", "medium", "high"] = Field(
        ..., description="Estimated risk level for routing and approval."
    )
    approval_level: Literal["none", "light", "strong", "forbidden"] = Field(
        ..., description="Required user approval level before execution."
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        description="Task creation timestamp normalized to UTC.",
    )
    status: Literal[
        "draft",
        "ready",
        "queued",
        "running",
        "waiting_for_user",
        "failed",
        "completed",
    ] = Field(default="draft", description="Current lifecycle status of the task.")
    user_request: str = Field(
        ...,
        min_length=1,
        max_length=8192,
        description="Original user request text that initiated the task.",
    )
    source_channel: Literal["console", "obsidian", "im", "schedule", "local"] = Field(
        ..., description="Channel from which the request entered NoeticBraid."
    )
    account_hint: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Optional non-authoritative account routing hint.",
    )
    project_ref: Optional[str] = Field(
        default=None,
        max_length=128,
        description="Optional project or workspace reference.",
    )

    @field_validator("created_at")
    @classmethod
    def _ensure_created_at_utc(cls, value: datetime) -> datetime:
        return ensure_utc_datetime(value)

    @field_validator("account_hint", "project_ref", mode="before")
    @classmethod
    def _blank_optional_strings_to_none(cls, value: object) -> object:
        return empty_str_to_none(value)

    def is_terminal(self) -> bool:
        """Whether the task reached a terminal status."""

        return self.status in ("failed", "completed")

    def requires_user_approval(self) -> bool:
        """Whether the task requires an explicit user approval workflow."""

        return self.approval_level in ("light", "strong", "forbidden")

    def to_event_dict(self) -> dict[str, str]:
        """Return the minimal event payload needed by a future run ledger."""

        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status,
            "source_channel": self.source_channel,
        }

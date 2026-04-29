"""RunRecord model (Stage 1 GPT-A full implementation, candidate_for: 1.0.0)."""

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


class RunRecord(BaseModel):
    """An append-only ledger event produced while a task moves through Phase 1.1."""

    model_config = COMMON_MODEL_CONFIG

    run_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        pattern=r"^run_[A-Za-z0-9_]+$",
        description="Stable run identifier prefixed with 'run_'.",
    )
    task_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        pattern=r"^task_[A-Za-z0-9_]+$",
        description="Task identifier linked to this event.",
    )
    event_type: Literal[
        "task_created",
        "task_classified",
        "context_built",
        "approval_requested",
        "approval_decision_recorded",
        "web_ai_call_requested",
        "profile_health_checked",
        "source_record_linked",
        "artifact_created",
        "security_violation",
        "lesson_candidate_created",
        "routing_advice_recorded",
        "task_completed",
        "task_failed",
    ] = Field(..., description="Allowed Phase 1.1 run ledger event type.")
    created_at: datetime = Field(
        default_factory=utc_now,
        description="Run event timestamp normalized to UTC.",
    )
    actor: Literal["user", "system", "model", "local_review"] = Field(
        ..., description="Actor responsible for the event."
    )
    model_refs: list[str] = Field(
        default_factory=list,
        max_length=100,
        description="Model references involved in this run event.",
    )
    source_refs: list[str] = Field(
        default_factory=list,
        max_length=100,
        description="Source record references linked to this run event.",
    )
    artifact_refs: list[str] = Field(
        default_factory=list,
        max_length=100,
        description="Artifact references produced or used by this run event.",
    )
    routing_advice: Optional[str] = Field(
        default=None,
        max_length=4096,
        description="Optional routing advice captured during orchestration.",
    )
    status: Literal["draft", "recorded", "failed"] = Field(
        default="draft", description="Persistence status for the ledger entry."
    )

    @field_validator("created_at")
    @classmethod
    def _ensure_created_at_utc(cls, value: datetime) -> datetime:
        return ensure_utc_datetime(value)

    @field_validator("model_refs")
    @classmethod
    def _validate_model_refs(cls, value: list[str]) -> list[str]:
        return validate_ref_list(value, prefix="model_", field_name="model_refs")

    @field_validator("source_refs")
    @classmethod
    def _validate_source_refs(cls, value: list[str]) -> list[str]:
        return validate_ref_list(value, prefix="source_", field_name="source_refs")

    @field_validator("artifact_refs")
    @classmethod
    def _validate_artifact_refs(cls, value: list[str]) -> list[str]:
        return validate_ref_list(value, prefix="artifact_", field_name="artifact_refs")

    @field_validator("routing_advice", mode="before")
    @classmethod
    def _blank_routing_advice_to_none(cls, value: object) -> object:
        return empty_str_to_none(value)

    def is_failure(self) -> bool:
        """Whether this record represents a failed persistence or failed task event."""

        return self.status == "failed" or self.event_type in ("task_failed", "security_violation")

    def has_external_refs(self) -> bool:
        """Whether the event links any model, source, or artifact references."""

        return bool(self.model_refs or self.source_refs or self.artifact_refs)

    def to_ledger_event_dict(self) -> dict[str, object]:
        """Return a compact ledger payload for downstream append-only storage."""

        return {
            "run_id": self.run_id,
            "task_id": self.task_id,
            "event_type": self.event_type,
            "actor": self.actor,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }

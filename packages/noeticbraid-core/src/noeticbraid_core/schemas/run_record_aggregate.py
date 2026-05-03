"""RunRecordAggregate schema for contract 1.2.0."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from ._common import COMMON_MODEL_CONFIG, ensure_optional_utc_datetime, validate_ref_list


class AggregateArtifact(BaseModel):
    """Artifact emitted by a run event."""

    model_config = COMMON_MODEL_CONFIG

    event_id: str
    artifact_ref: str


class AggregateError(BaseModel):
    """Failure entry summarized from a run event."""

    model_config = COMMON_MODEL_CONFIG

    event_id: str
    error_kind: Optional[str] = None
    message: Optional[str] = Field(default=None, max_length=4096)


class AggregateLesson(BaseModel):
    """Lesson candidate entry summarized from a run event."""

    model_config = COMMON_MODEL_CONFIG

    event_id: str
    lesson_candidate_text: Optional[str] = Field(default=None, max_length=4096)


class RunRecordAggregate(BaseModel):
    """Aggregate view over RunRecord events sharing one run_id."""

    model_config = COMMON_MODEL_CONFIG

    run_id: str = Field(..., max_length=128, pattern=r"^run_[A-Za-z0-9_]+$")
    task_id: Optional[str] = Field(..., max_length=128, pattern=r"^task_[A-Za-z0-9_]+$")
    event_count: int = Field(..., ge=0, le=100000)
    first_event_at: Optional[datetime] = None
    last_event_at: Optional[datetime] = None
    models_used: list[str] = Field(default_factory=list, max_length=64)
    artifacts: list[AggregateArtifact] = Field(default_factory=list, max_length=1000)
    errors: list[AggregateError] = Field(default_factory=list, max_length=1000)
    lessons_summary: list[AggregateLesson] = Field(default_factory=list, max_length=1000)

    @field_validator("first_event_at", "last_event_at")
    @classmethod
    def _ensure_optional_timestamps_utc(cls, value: Optional[datetime]) -> Optional[datetime]:
        return ensure_optional_utc_datetime(value)

    @field_validator("models_used")
    @classmethod
    def _validate_models_used(cls, value: list[str]) -> list[str]:
        return validate_ref_list(value, prefix="model_", field_name="models_used")

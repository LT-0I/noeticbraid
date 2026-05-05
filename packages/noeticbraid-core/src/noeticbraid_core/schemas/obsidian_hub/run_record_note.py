"""Run record note frontmatter schema for contract 1.3.0."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

from .._common import COMMON_MODEL_CONFIG, ensure_utc_datetime, validate_ref_list

NoeticTag = Annotated[str, Field(pattern=r"^noeticbraid/")]
ModelRef = Annotated[str, Field(pattern=r"^model_[A-Za-z0-9_]+$")]
SourceRef = Annotated[str, Field(pattern=r"^source_[A-Za-z0-9_]+$")]
ArtifactRef = Annotated[str, Field(pattern=r"^artifact_[A-Za-z0-9_]+$")]


class RunRecordNote(BaseModel):
    """Obsidian run record frontmatter aligned to a 9-value RunRecord event subset."""

    model_config = COMMON_MODEL_CONFIG

    nb_type: Literal["run_record"] = Field(..., description="Vault note type marker.")
    schema_version: Literal["obsidian-hub-0.1"] = Field(
        ..., description="Obsidian hub schema family version."
    )
    contract_version: Literal["1.3.0"] = Field(
        ..., description="Contract freeze version for this vault note wrapper."
    )
    run_id: str = Field(..., max_length=128, pattern=r"^run_[A-Za-z0-9_]+$")
    task_id: str = Field(..., max_length=128, pattern=r"^task_[A-Za-z0-9_]+$")
    event_type: Literal[
        "task_created",
        "task_completed",
        "artifact_created",
        "source_record_linked",
        "approval_requested",
        "security_violation",
        "routing_advice_recorded",
        "lesson_candidate_created",
        "task_failed",
    ]
    actor: Literal["user", "system", "model", "local_review"]
    status: Literal["draft", "recorded", "failed"]
    created_at: datetime = Field(..., description="Run event timestamp normalized to UTC.")
    tags: list[NoeticTag] = Field(..., min_length=1, max_length=16)
    model_refs: list[ModelRef] = Field(default_factory=list, max_length=16)
    source_refs: list[SourceRef] = Field(default_factory=list, max_length=64)
    artifact_refs: list[ArtifactRef] = Field(default_factory=list, max_length=64)

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

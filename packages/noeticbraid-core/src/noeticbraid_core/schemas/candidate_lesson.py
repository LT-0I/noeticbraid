"""Candidate lesson schema for the SDD-D2-02 OMC ingestion workbench."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from noeticbraid_core.r6_gate import R6GateState

from ._common import COMMON_MODEL_CONFIG, empty_str_to_none, ensure_optional_utc_datetime

CandidateStatus = Literal["candidate", "adopted", "confirmed", "archived"]
R6_UPGRADE_PHRASES = ("explicit", "adoption", "reuse >=3", "ledger", "never sufficient")


class CandidateLesson(BaseModel):
    """Program-memory lesson candidate with explicit R-6 adoption evidence fields."""

    model_config = COMMON_MODEL_CONFIG

    candidate_id: str = Field(..., min_length=1, max_length=128)
    project_id: Literal["omc-ingest"] = "omc-ingest"
    source_sdd_ids: list[str] = Field(..., min_length=1, max_length=16)
    summary: str = Field(..., min_length=1, max_length=4096)
    status: CandidateStatus = "candidate"
    upgrade_rule: str = Field(..., min_length=1, max_length=1024)
    adopted_at: Optional[datetime] = None
    adopted_by: Optional[str] = Field(default=None, max_length=128)
    run_record_ref: Optional[str] = Field(default=None, max_length=128)
    reuse_evidence_refs: list[str] = Field(default_factory=list, max_length=100)
    artifact_refs: list[str] = Field(default_factory=list, max_length=100)
    source_refs: list[str] = Field(default_factory=list, max_length=100)
    r6_gate: R6GateState | None = None

    @field_validator("adopted_at")
    @classmethod
    def _adopted_at_utc(cls, value: Optional[datetime]) -> Optional[datetime]:
        return ensure_optional_utc_datetime(value)

    @field_validator("adopted_by", "run_record_ref", mode="before")
    @classmethod
    def _blank_optional_strings_to_none(cls, value: object) -> object:
        return empty_str_to_none(value)

    @field_validator("upgrade_rule")
    @classmethod
    def _requires_r6_upgrade_rule(cls, value: str) -> str:
        normalized = value.lower()
        missing = [phrase for phrase in R6_UPGRADE_PHRASES if phrase not in normalized]
        if missing:
            raise ValueError("upgrade_rule must encode explicit adoption OR reuse >=3 with ledger evidence; not rejected is never sufficient")
        return value

    @field_validator("source_sdd_ids", "reuse_evidence_refs", "artifact_refs", "source_refs")
    @classmethod
    def _dedupe_non_blank_refs(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        for item in value:
            if not item.strip():
                raise ValueError("refs must not contain blank values")
            if item in seen:
                raise ValueError("refs must not contain duplicate values")
            seen.add(item)
        return value

    @model_validator(mode="after")
    def _explicit_adoption_evidence_required(self) -> "CandidateLesson":
        if self.status in {"adopted", "confirmed"}:
            if self.adopted_at is None:
                raise ValueError("adopted candidates require adopted_at")
            if not self.run_record_ref:
                raise ValueError("adopted candidates require run_record_ref")
            if not any(ref.endswith(".md") and "candidate-adoption-" in ref for ref in self.artifact_refs):
                raise ValueError("adopted candidates require narrative candidate-adoption markdown artifact")
        return self

    def adoption_artifact_refs(self) -> list[str]:
        """Return narrative markdown adoption artifacts without implying a new RunRecord event type."""

        return [ref for ref in self.artifact_refs if ref.endswith(".md") and "candidate-adoption-" in ref]

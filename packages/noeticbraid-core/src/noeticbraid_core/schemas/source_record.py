"""SourceRecord model (Stage 1 GPT-A full implementation, candidate_for: 1.0.0)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from ._common import COMMON_MODEL_CONFIG, empty_str_to_none, ensure_utc_datetime, utc_now


class SourceRecord(BaseModel):
    """A provenance record for user notes, web material, AI outputs, or references."""

    model_config = COMMON_MODEL_CONFIG

    source_ref_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        pattern=r"^source_[A-Za-z0-9_]+$",
        description="Stable source identifier prefixed with 'source_'.",
    )
    source_type: Literal[
        "user_note",
        "web_page",
        "github_repo",
        "paper",
        "patent",
        "video",
        "ai_output",
        "paid_database",
    ] = Field(..., description="Kind of source captured for grounding or memory.")
    title: str = Field(..., min_length=1, max_length=512, description="Source title.")
    canonical_url: Optional[str] = Field(
        default=None,
        max_length=2048,
        description="Optional canonical HTTP(S) URL for web-accessible sources.",
    )
    local_path: Optional[str] = Field(
        default=None,
        max_length=1024,
        description="Optional local path for local-only or mirrored source material.",
    )
    author: Optional[str] = Field(
        default=None,
        max_length=256,
        description="Optional author, organization, or account label.",
    )
    captured_at: datetime = Field(
        default_factory=utc_now,
        description="Capture timestamp normalized to UTC.",
    )
    retrieved_by_run_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        pattern=r"^run_[A-Za-z0-9_]+$",
        description="Run identifier that retrieved or linked this source.",
    )
    content_hash: str = Field(
        ...,
        min_length=71,
        max_length=71,
        pattern=r"^sha256:[A-Fa-f0-9]{64}$",
        description="sha256-prefixed content hash.",
    )
    source_fingerprint: str = Field(
        ...,
        min_length=1,
        max_length=128,
        pattern=r"^fingerprint_[A-Za-z0-9_]+$",
        description="Stable deduplication fingerprint prefixed with 'fingerprint_'.",
    )
    quality_score: Literal["low", "medium", "high", "unknown"] = Field(
        default="unknown", description="Quality assessment for the source."
    )
    relevance_score: Literal["low", "medium", "high", "unknown"] = Field(
        default="unknown", description="Relevance assessment for the current task."
    )
    evidence_role: Literal[
        "user_context",
        "reference_project",
        "source_grounding",
        "contradiction",
        "memory_update_evidence",
    ] = Field(..., description="Role this source plays in evidence handling.")
    used_for_purpose: Literal[
        "project_positioning",
        "constraint_extraction",
        "source_grounding",
        "prior_art_check",
        "other",
    ] = Field(..., description="Purpose for which the source was used.")

    @field_validator("captured_at")
    @classmethod
    def _ensure_captured_at_utc(cls, value: datetime) -> datetime:
        return ensure_utc_datetime(value)

    @field_validator("canonical_url", "local_path", "author", mode="before")
    @classmethod
    def _blank_optional_strings_to_none(cls, value: object) -> object:
        return empty_str_to_none(value)

    @field_validator("canonical_url")
    @classmethod
    def _canonical_url_http_only(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if not value.startswith(("http://", "https://")):
            raise ValueError("canonical_url must start with http:// or https://")
        return value

    @field_validator("content_hash")
    @classmethod
    def _normalize_content_hash(cls, value: str) -> str:
        return value.lower()

    def has_location(self) -> bool:
        """Whether the source has either a canonical URL or local path."""

        return bool(self.canonical_url or self.local_path)

    def is_high_value(self) -> bool:
        """Whether the source is both high quality and high relevance."""

        return self.quality_score == "high" and self.relevance_score == "high"

    def to_evidence_key(self) -> str:
        """Return a concise evidence key for notes and ledger records."""

        return f"{self.source_ref_id}:{self.source_fingerprint}"

"""Source record note frontmatter schema for contract 1.3.0."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from .._common import COMMON_MODEL_CONFIG, empty_str_to_none, ensure_utc_datetime

NoeticTag = Annotated[str, Field(pattern=r"^noeticbraid/")]
CredentialQueryPattern = re.compile(
    r"[?&](?:token|access_token|api[_-]?key|apikey|secret|password|passwd|cookie|session|auth|authorization)=",
    re.IGNORECASE,
)


class SourceRecordNote(BaseModel):
    """Obsidian source record frontmatter aligned to a SourceRecord source subset."""

    model_config = COMMON_MODEL_CONFIG

    nb_type: Literal["source_record"] = Field(..., description="Vault note type marker.")
    schema_version: Literal["obsidian-hub-0.1"] = Field(
        ..., description="Obsidian hub schema family version."
    )
    contract_version: Literal["1.3.0"] = Field(
        ..., description="Contract freeze version for this vault note wrapper."
    )
    source_ref_id: str = Field(..., max_length=128, pattern=r"^source_[A-Za-z0-9_]+$")
    source_type: Literal["user_note", "web_page", "github_repo", "paper", "ai_output"]
    # NO-LEAK: title is frontmatter, not a place for secret-bearing body text.
    title: str = Field(..., min_length=1, max_length=512)
    captured_at: datetime = Field(..., description="Capture timestamp normalized to UTC.")
    quality_score: Literal["low", "medium", "high", "unknown"]
    relevance_score: Literal["low", "medium", "high", "unknown"]
    tags: list[NoeticTag] = Field(..., min_length=1, max_length=16)
    # NO-LEAK: URLs must not include credential query parameters.
    canonical_url: Optional[str] = Field(default=None, max_length=2048, pattern=r"^https?://")
    local_path: Optional[str] = Field(default=None, max_length=1024)
    source_ref: Optional[str] = Field(default=None, max_length=256)
    # NO-LEAK: external URLs follow the same credential-query guard.
    external_url: Optional[str] = Field(default=None, max_length=2048, pattern=r"^https?://")
    # NO-LEAK: author labels must not contain secret-bearing body content.
    author: Optional[str] = Field(default=None, max_length=256)
    retrieved_by_run_id: Optional[str] = Field(default=None, pattern=r"^run_[A-Za-z0-9_]+$")
    content_hash: Optional[str] = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    source_fingerprint: Optional[str] = Field(default=None, max_length=256)
    evidence_role: Optional[
        Literal[
            "user_context",
            "reference_project",
            "source_grounding",
            "contradiction",
            "memory_update_evidence",
        ]
    ] = None
    used_for_purpose: Optional[
        Literal[
            "project_positioning",
            "constraint_extraction",
            "source_grounding",
            "prior_art_check",
            "other",
        ]
    ] = None

    @field_validator("captured_at")
    @classmethod
    def _ensure_captured_at_utc(cls, value: datetime) -> datetime:
        return ensure_utc_datetime(value)

    @field_validator(
        "canonical_url",
        "local_path",
        "source_ref",
        "external_url",
        "author",
        "retrieved_by_run_id",
        "content_hash",
        "source_fingerprint",
        mode="before",
    )
    @classmethod
    def _blank_optional_strings_to_none(cls, value: object) -> object:
        return empty_str_to_none(value)

    @field_validator("canonical_url", "external_url")
    @classmethod
    def _reject_credential_query_params(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if CredentialQueryPattern.search(value):
            raise ValueError("URL must not include credential query parameters")
        return value

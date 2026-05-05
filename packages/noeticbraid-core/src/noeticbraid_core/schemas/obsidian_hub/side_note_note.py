"""Side note frontmatter schema for contract 1.3.0."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from .._common import COMMON_MODEL_CONFIG, empty_str_to_none, ensure_utc_datetime, validate_ref_list

NoeticTag = Annotated[str, Field(pattern=r"^noeticbraid/")]
SourceRef = Annotated[str, Field(pattern=r"^source_[A-Za-z0-9_]+$")]


class SideNoteNote(BaseModel):
    """Obsidian side note frontmatter with vault-only snoozed response."""

    model_config = COMMON_MODEL_CONFIG

    nb_type: Literal["side_note"] = Field(..., description="Vault note type marker.")
    schema_version: Literal["obsidian-hub-0.1"] = Field(
        ..., description="Obsidian hub schema family version."
    )
    contract_version: Literal["1.3.0"] = Field(
        ..., description="Contract freeze version for this vault note wrapper."
    )
    note_id: str = Field(..., max_length=128, pattern=r"^note_[A-Za-z0-9_]+$")
    created_at: datetime = Field(..., description="Note creation timestamp normalized to UTC.")
    linked_source_refs: list[SourceRef] = Field(..., min_length=1, max_length=64)
    note_type: Literal["fact", "hypothesis", "challenge", "action"]
    confidence: Literal["low", "medium", "high"]
    user_response: Literal["unread", "accepted", "rejected", "modified", "snoozed"]
    tags: list[NoeticTag] = Field(..., min_length=1, max_length=16)
    follow_up_ref: Optional[str] = Field(default=None, pattern=r"^digestion_[A-Za-z0-9_]+$")
    project_ref: Optional[str] = Field(default=None, max_length=256)

    @field_validator("created_at")
    @classmethod
    def _ensure_created_at_utc(cls, value: datetime) -> datetime:
        return ensure_utc_datetime(value)

    @field_validator("linked_source_refs")
    @classmethod
    def _validate_source_refs(cls, value: list[str]) -> list[str]:
        return validate_ref_list(value, prefix="source_", field_name="linked_source_refs")

    @field_validator("follow_up_ref", "project_ref", mode="before")
    @classmethod
    def _blank_optional_strings_to_none(cls, value: object) -> object:
        return empty_str_to_none(value)

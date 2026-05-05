"""Digestion item note frontmatter schema for contract 1.3.0."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from .._common import (
    COMMON_MODEL_CONFIG,
    empty_str_to_none,
    ensure_optional_utc_datetime,
    ensure_utc_datetime,
)

NoeticTag = Annotated[str, Field(pattern=r"^noeticbraid/")]


class DigestionItemNote(BaseModel):
    """Obsidian digestion item frontmatter aligned to frozen DigestionItem enums."""

    model_config = COMMON_MODEL_CONFIG

    nb_type: Literal["digestion_item"] = Field(..., description="Vault note type marker.")
    schema_version: Literal["obsidian-hub-0.1"] = Field(
        ..., description="Obsidian hub schema family version."
    )
    contract_version: Literal["1.3.0"] = Field(
        ..., description="Contract freeze version for this vault note wrapper."
    )
    digestion_id: str = Field(..., max_length=128, pattern=r"^digestion_[A-Za-z0-9_]+$")
    side_note_id: str = Field(..., max_length=128, pattern=r"^note_[A-Za-z0-9_]+$")
    created_at: datetime = Field(..., description="Creation timestamp normalized to UTC.")
    c_status: Literal["c0", "c1", "c2", "c3", "c4", "cX"]
    status: Literal["open", "closed", "rejected", "snoozed"]
    tags: list[NoeticTag] = Field(..., min_length=1, max_length=16)
    # NO-LEAK: this is a reference string only, not user response body content.
    user_response_ref: Optional[str] = Field(default=None, max_length=128)
    next_review_at: Optional[datetime] = None

    @field_validator("created_at")
    @classmethod
    def _ensure_created_at_utc(cls, value: datetime) -> datetime:
        return ensure_utc_datetime(value)

    @field_validator("next_review_at")
    @classmethod
    def _ensure_next_review_at_utc(cls, value: Optional[datetime]) -> Optional[datetime]:
        return ensure_optional_utc_datetime(value)

    @field_validator("user_response_ref", mode="before")
    @classmethod
    def _blank_user_response_ref_to_none(cls, value: object) -> object:
        return empty_str_to_none(value)

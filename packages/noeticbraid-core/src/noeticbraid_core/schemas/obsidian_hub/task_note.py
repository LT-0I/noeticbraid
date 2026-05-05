"""Task note frontmatter schema for contract 1.3.0."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from .._common import COMMON_MODEL_CONFIG, empty_str_to_none, ensure_utc_datetime

NoeticTag = Annotated[str, Field(pattern=r"^noeticbraid/")]


class TaskNote(BaseModel):
    """Obsidian task note frontmatter aligned to frozen Task 1.0.0."""

    model_config = COMMON_MODEL_CONFIG

    nb_type: Literal["task"] = Field(..., description="Vault note type marker.")
    schema_version: Literal["obsidian-hub-0.1"] = Field(
        ..., description="Obsidian hub schema family version."
    )
    contract_version: Literal["1.3.0"] = Field(
        ..., description="Contract freeze version for this vault note wrapper."
    )
    task_id: str = Field(..., max_length=128, pattern=r"^task_[A-Za-z0-9_]+$")
    task_type: Literal["project_planning", "research", "code_review"]
    risk_level: Literal["low", "medium", "high"]
    approval_level: Literal["none", "light", "strong", "forbidden"]
    status: Literal["draft", "ready", "queued", "running", "waiting_for_user", "failed", "completed"]
    source_channel: Literal["console", "obsidian", "im", "schedule", "local"]
    created_at: datetime = Field(..., description="Task creation timestamp normalized to UTC.")
    tags: list[NoeticTag] = Field(..., min_length=1, max_length=16)
    # NO-LEAK: routing hints must not carry account secrets or credential body text.
    account_hint: Optional[str] = Field(default=None, max_length=64)
    project_ref: Optional[str] = Field(default=None, max_length=128)

    @field_validator("created_at")
    @classmethod
    def _ensure_created_at_utc(cls, value: datetime) -> datetime:
        return ensure_utc_datetime(value)

    @field_validator("account_hint", "project_ref", mode="before")
    @classmethod
    def _blank_optional_strings_to_none(cls, value: object) -> object:
        return empty_str_to_none(value)

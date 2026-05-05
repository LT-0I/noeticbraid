"""Dashboard frontmatter schema for contract 1.3.0."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from .._common import COMMON_MODEL_CONFIG, empty_str_to_none, ensure_utc_datetime

NoeticTag = Annotated[str, Field(pattern=r"^noeticbraid/")]


class Dashboard(BaseModel):
    """Generated Obsidian dashboard frontmatter."""

    model_config = COMMON_MODEL_CONFIG

    nb_type: Literal["dashboard"] = Field(..., description="Vault note type marker.")
    schema_version: Literal["obsidian-hub-0.1"] = Field(
        ..., description="Obsidian hub schema family version."
    )
    contract_version: Literal["1.3.0"] = Field(
        ..., description="Contract freeze version for this vault note wrapper."
    )
    dashboard_id: str = Field(..., max_length=128, pattern=r"^dashboard_[A-Za-z0-9_]+$")
    # NO-LEAK: generated title must not carry secret-bearing body content.
    title: str = Field(..., min_length=1, max_length=256)
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    generated: Literal[True] = Field(..., description="Generated dashboards declare true.")
    generated_at: datetime = Field(..., description="Generation timestamp normalized to UTC.")
    tags: list[NoeticTag] = Field(..., min_length=1, max_length=16)
    source_run_id: Optional[str] = Field(default=None, pattern=r"^run_[A-Za-z0-9_]+$")

    @field_validator("generated_at")
    @classmethod
    def _ensure_generated_at_utc(cls, value: datetime) -> datetime:
        return ensure_utc_datetime(value)

    @field_validator("source_run_id", mode="before")
    @classmethod
    def _blank_source_run_id_to_none(cls, value: object) -> object:
        return empty_str_to_none(value)

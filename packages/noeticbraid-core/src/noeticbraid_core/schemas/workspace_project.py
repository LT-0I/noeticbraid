"""OMC ingestion workspace project schema for SDD-D2-02."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from ._common import COMMON_MODEL_CONFIG


class WorkspaceProject(BaseModel):
    """Minimum observable project surface for the OMC ingestion workbench."""

    model_config = COMMON_MODEL_CONFIG

    project_id: Literal["omc-ingest"] = Field(
        default="omc-ingest",
        description="Locked SDD-D2-02 project id for the OMC ingestion demo.",
    )
    title: Literal["吸收 OMC"] = Field(default="吸收 OMC")
    project_type: Literal["ingestion"] = Field(default="ingestion")
    owner: Literal["user"] = Field(default="user")
    status: Literal["active", "paused", "archived"] = Field(default="active")
    chat_entry: dict[str, Any] = Field(
        ...,
        description="Card-shaped project-chat entry; not a persisted thread protocol.",
    )
    external_reference_refs: list[str] = Field(default_factory=list, max_length=100)
    candidate_refs: list[str] = Field(default_factory=list, max_length=100)
    adopted_candidate_refs: list[str] = Field(default_factory=list, max_length=100)
    capability_refs: list[str] = Field(default_factory=list, max_length=32)
    run_refs: list[str] = Field(default_factory=list, max_length=100)

    @field_validator(
        "external_reference_refs",
        "candidate_refs",
        "adopted_candidate_refs",
        "capability_refs",
        "run_refs",
    )
    @classmethod
    def _dedupe_refs(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        for item in value:
            if not item.strip():
                raise ValueError("refs must not contain blank values")
            if item in seen:
                raise ValueError("refs must not contain duplicate values")
            seen.add(item)
        return value

    @field_validator("chat_entry")
    @classmethod
    def _chat_entry_is_card_only(cls, value: dict[str, Any]) -> dict[str, Any]:
        if value.get("mode") not in {"task_card", "card"}:
            raise ValueError("chat_entry must be card-shaped; thread chat is out of scope")
        return value

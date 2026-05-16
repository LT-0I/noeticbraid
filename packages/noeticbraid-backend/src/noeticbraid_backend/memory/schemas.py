# SPDX-License-Identifier: Apache-2.0
"""Memory item/source/context-pack schemas ported from claude-mem."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

MemoryItemKind = Literal["observation", "summary", "prompt", "manual"]
MemorySourceType = Literal["observation", "session_summary", "user_prompt", "manual", "import"]


class MemoryItem(BaseModel):
    """Pydantic port of claude-mem MemoryItemSchema."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str = Field(..., min_length=1)
    project_id: str = Field(..., min_length=1, alias="projectId")
    server_session_id: str | None = Field(default=None, min_length=1, alias="serverSessionId")
    legacy_observation_id: int | None = Field(default=None, gt=0, alias="legacyObservationId")
    kind: MemoryItemKind
    type: str = Field(..., min_length=1)
    title: str | None = Field(default=None, min_length=1)
    subtitle: str | None = Field(default=None, min_length=1)
    text: str | None = None
    narrative: str | None = None
    facts: list[str] = Field(default_factory=list)
    concepts: list[str] = Field(default_factory=list)
    files_read: list[str] = Field(default_factory=list, alias="filesRead")
    files_modified: list[str] = Field(default_factory=list, alias="filesModified")
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at_epoch: int = Field(..., ge=0, alias="createdAtEpoch")
    updated_at_epoch: int = Field(..., ge=0, alias="updatedAtEpoch")


class MemorySource(BaseModel):
    """Pydantic port of claude-mem MemorySourceSchema."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str = Field(..., min_length=1)
    memory_item_id: str = Field(..., min_length=1, alias="memoryItemId")
    source_type: MemorySourceType = Field(..., alias="sourceType")
    legacy_table: str | None = Field(default=None, min_length=1, alias="legacyTable")
    legacy_id: int | None = Field(default=None, gt=0, alias="legacyId")
    source_uri: str | None = Field(default=None, min_length=1, alias="sourceUri")
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at_epoch: int = Field(..., ge=0, alias="createdAtEpoch")


class ContextPack(BaseModel):
    """Pydantic port of claude-mem ContextPackSchema."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    project_id: str = Field(..., min_length=1, alias="projectId")
    server_session_id: str | None = Field(default=None, min_length=1, alias="serverSessionId")
    generated_at_epoch: int = Field(..., ge=0, alias="generatedAtEpoch")
    token_budget: int | None = Field(default=None, gt=0, alias="tokenBudget")
    items: list[MemoryItem] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "ContextPack",
    "MemoryItem",
    "MemoryItemKind",
    "MemorySource",
    "MemorySourceType",
]

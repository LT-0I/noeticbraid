# SPDX-License-Identifier: Apache-2.0
"""Static helpers for the frozen Phase 1.2 v1.2.0 API contract."""

from __future__ import annotations

import importlib
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

CONTRACT_VERSION = "1.2.0"
CONTRACT_V2_VERSION = "2.0.0"
CONTRACT_AUTHORITATIVE = True
OPENAPI_TITLE = "NoeticBraid Phase 1.2 API"
SIDE_NOTE_V2_TONE_CONSTRAINT = "不审判用户 / 不羞辱用户 / 不替用户解释自己；违反任一构成 fatal"
SIDE_NOTE_V2_REQUIRED_METADATA = (
    "evidence_source",
    "note_type",
    "confidence",
    "tone_constraint",
    "user_response_channel",
)
CONTRACT_V2_SCHEMA_NAMES: tuple[str, ...] = ("SideNote",)
CONTRACT_V2_SCHEMA_METADATA: dict[str, dict[str, Any]] = {
    "SideNote": {
        "contract_version": CONTRACT_V2_VERSION,
        "required_metadata": SIDE_NOTE_V2_REQUIRED_METADATA,
        "note_type_enum": ("fact", "hypothesis", "action_suggestion"),
        "confidence_enum": ("low", "medium", "high"),
        "tone_constraint": SIDE_NOTE_V2_TONE_CONSTRAINT,
        "user_response_channel_enum": (
            "accept",
            "rebut",
            "mark_inaccurate",
            "disable_this_type",
        ),
    }
}
CONTRACT_V2_ROUTE_SPECS: tuple[dict[str, str], ...] = ()

FROZEN_ROUTE_SPECS: tuple[dict[str, str], ...] = (
    {
        "method": "GET",
        "path": "/api/health",
        "summary": "Health check",
        "response_schema": "HealthResponse",
    },
    {
        "method": "POST",
        "path": "/api/auth/startup_token",
        "summary": "Validate startup token",
        "response_schema": "AuthResponse",
    },
    {
        "method": "GET",
        "path": "/api/dashboard/empty",
        "summary": "Empty dashboard state",
        "response_schema": "EmptyDashboard",
    },
    {
        "method": "GET",
        "path": "/api/workspace/threads",
        "summary": "List workspace threads",
        "response_schema": "WorkspaceThreads",
    },
    {
        "method": "GET",
        "path": "/api/approval/queue",
        "summary": "List approval queue",
        "response_schema": "ApprovalQueue",
    },
    {
        "method": "GET",
        "path": "/api/account/pool",
        "summary": "Account pool draft state",
        "response_schema": "AccountPoolDraft",
    },
    {
        "method": "GET",
        "path": "/api/ledger/runs",
        "summary": "List run records",
        "response_schema": "RunLedgerRuns",
    },
    {
        "method": "GET",
        "path": "/api/ledger/runs/aggregate",
        "summary": "Aggregate run record",
        "response_schema": "RunRecordAggregate",
    },
)


class _FrozenBaseModel(BaseModel):
    """Base model that rejects additive fields in frozen route wrappers."""

    model_config = ConfigDict(extra="forbid")


class HealthResponse(_FrozenBaseModel):
    """Health check response."""

    status: str
    contract_version: str
    authoritative: bool


class AuthResponse(_FrozenBaseModel):
    """Startup-token validation response."""

    accepted: bool
    mode: str


class EmptyDashboard(_FrozenBaseModel):
    """Empty dashboard fixture response."""

    tasks: list[dict[str, Any]] = Field(default_factory=list)
    approvals: list[dict[str, Any]] = Field(default_factory=list)
    accounts: list[dict[str, Any]] = Field(default_factory=list)


class WorkspaceThreads(_FrozenBaseModel):
    """Workspace thread fixture response."""

    threads: list[dict[str, Any]] = Field(default_factory=list)


class ApprovalQueue(_FrozenBaseModel):
    """Approval queue fixture response."""

    approvals: list[dict[str, Any]] = Field(default_factory=list)


class AccountPoolDraft(_FrozenBaseModel):
    """Account pool fixture response; Stage 1 does not expose profile_records."""

    profiles: list[dict[str, Any]] = Field(default_factory=list)


class RunLedgerRuns(_FrozenBaseModel):
    """Run ledger fixture response."""

    runs: list[dict[str, Any]] = Field(default_factory=list)


class _FallbackCoreModel(_FrozenBaseModel):
    """Fallback for local skeleton tests when noeticbraid-core is unavailable."""


try:  # Import where available; keep the backend skeleton runnable in isolation.
    _schemas = importlib.import_module("noeticbraid_core.schemas")
    Task = _schemas.Task
    RunRecord = _schemas.RunRecord
    SourceRecord = _schemas.SourceRecord
    ApprovalRequest = _schemas.ApprovalRequest
    DigestionItem = _schemas.DigestionItem
    Workflow = _schemas.Workflow
    ModelRoute = _schemas.ModelRoute
    VaultLayoutMinimum = _schemas.VaultLayoutMinimum
    RunRecordAggregate = _schemas.RunRecordAggregate
except Exception:  # pragma: no cover - exercised only without the workspace dependency

    class Task(_FallbackCoreModel):
        pass

    class RunRecord(_FallbackCoreModel):
        pass

    class SourceRecord(_FallbackCoreModel):
        pass

    class ApprovalRequest(_FallbackCoreModel):
        pass

    class DigestionItem(_FallbackCoreModel):
        pass

    class Workflow(_FallbackCoreModel):
        pass

    class ModelRoute(_FallbackCoreModel):
        pass

    class VaultLayoutMinimum(_FallbackCoreModel):
        pass

    class RunRecordAggregate(_FallbackCoreModel):
        pass


class SideNote(_FrozenBaseModel):
    """Frozen SideNote schema for backend contract 1.2.0.

    Core ``noeticbraid_core.schemas.SideNote`` now represents the breaking
    2.0.0 shape. The backend 1.2.0 OpenAPI component keeps this flat local
    v1 model so existing endpoint serialization remains unchanged.
    """

    note_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        pattern=r"^note_[A-Za-z0-9_]+$",
        description="Stable note identifier prefixed with 'note_'.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Note creation timestamp normalized to UTC.",
    )
    linked_source_refs: list[str] = Field(
        default_factory=list,
        max_length=100,
        description="Source references supporting or challenging the note.",
    )
    note_type: Literal["fact", "hypothesis", "challenge", "action"] = Field(
        ..., description="Type of side note."
    )
    claim: str = Field(..., min_length=1, max_length=4096, description="Claim or action text.")
    confidence: Literal["low", "medium", "high"] = Field(
        ..., description="Confidence in the claim."
    )
    user_response: Literal["unread", "accepted", "rejected", "modified"] = Field(
        default="unread", description="User handling state for the note."
    )
    follow_up_ref: Optional[str] = Field(
        default=None,
        max_length=128,
        description="Optional follow-up task, approval, note, or digestion reference.",
    )


CORE_SCHEMA_MODELS: tuple[type[BaseModel], ...] = (
    Task,
    RunRecord,
    SourceRecord,
    ApprovalRequest,
    SideNote,
    DigestionItem,
    Workflow,
    ModelRoute,
    VaultLayoutMinimum,
    RunRecordAggregate,
)


ALL_SCHEMA_NAMES: tuple[str, ...] = (
    "HealthResponse",
    "AuthResponse",
    "EmptyDashboard",
    "WorkspaceThreads",
    "ApprovalQueue",
    "AccountPoolDraft",
    "RunLedgerRuns",
    "Task",
    "RunRecord",
    "SourceRecord",
    "ApprovalRequest",
    "SideNote",
    "DigestionItem",
    "Workflow",
    "ModelRoute",
    "VaultLayoutMinimum",
    "RunRecordAggregate",
)

__all__ = [
    "CONTRACT_AUTHORITATIVE",
    "CONTRACT_VERSION",
    "CONTRACT_V2_VERSION",
    "OPENAPI_TITLE",
    "FROZEN_ROUTE_SPECS",
    "CONTRACT_V2_SCHEMA_NAMES",
    "CONTRACT_V2_SCHEMA_METADATA",
    "CONTRACT_V2_ROUTE_SPECS",
    "ALL_SCHEMA_NAMES",
    "CORE_SCHEMA_MODELS",
    "HealthResponse",
    "AuthResponse",
    "EmptyDashboard",
    "WorkspaceThreads",
    "ApprovalQueue",
    "AccountPoolDraft",
    "RunLedgerRuns",
    "Task",
    "RunRecord",
    "SourceRecord",
    "ApprovalRequest",
    "SideNote",
    "DigestionItem",
    "Workflow",
    "ModelRoute",
    "VaultLayoutMinimum",
    "RunRecordAggregate",
]

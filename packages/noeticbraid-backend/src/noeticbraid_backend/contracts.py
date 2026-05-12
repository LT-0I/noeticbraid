# SPDX-License-Identifier: Apache-2.0
"""Static helpers for Phase 1.2 plus additive SDD-D2-02/D2-03/D2-04 surfaces."""

from __future__ import annotations

import importlib
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

CONTRACT_VERSION = "1.4.0"
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


OMC_WORKSPACE_ROUTE_SPECS: tuple[dict[str, str], ...] = (
    {
        "method": "POST",
        "path": "/api/projects/omc-ingest/tasks",
        "summary": "Submit OMC ingestion task card",
        "response_schema": "OMCProjectTaskResponse",
    },
    {
        "method": "GET",
        "path": "/api/projects/omc-ingest/candidates",
        "summary": "List OMC ingestion candidates",
        "response_schema": "OMCProjectCandidates",
    },
    {
        "method": "GET",
        "path": "/api/projects/omc-ingest/adopted-history",
        "summary": "List OMC adopted candidates",
        "response_schema": "OMCProjectAdoptedHistory",
    },
    {
        "method": "POST",
        "path": "/api/candidates/{id}/adopt",
        "summary": "Adopt OMC candidate explicitly",
        "response_schema": "CandidateAdoptionResponse",
    },
    {
        "method": "GET",
        "path": "/api/capabilities",
        "summary": "List first-stage capabilities",
        "response_schema": "CapabilitiesResponse",
    },
    {
        "method": "POST",
        "path": "/api/capabilities/{id}/health-check",
        "summary": "Run capability health check",
        "response_schema": "CapabilityHealthCheckResponse",
    },
)

CONTRACT_1_3_ROUTE_SPECS: tuple[dict[str, str], ...] = (
    FROZEN_ROUTE_SPECS[:4] + OMC_WORKSPACE_ROUTE_SPECS + FROZEN_ROUTE_SPECS[4:]
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


class OMCProjectTaskRequest(_FrozenBaseModel):
    """Task-card request for the OMC ingestion workspace."""

    task_id: str = Field(default="task_omc_ingest", min_length=1, max_length=128)
    title: str = Field(default="吸收 OMC `omc help` slash 命令列表", min_length=1, max_length=512)
    prompt: str = Field(..., min_length=1, max_length=4096)
    source_refs: list[str] = Field(default_factory=list)


class OMCProjectTaskResponse(_FrozenBaseModel):
    """Response from running the OMC task card through the D2-01 adapter."""

    project_id: str
    task_id: str
    candidate_id: str
    convergence_markdown_ref: str
    run_record_ref: str
    artifact_refs: list[str] = Field(default_factory=list)
    candidate: dict[str, Any]
    run_records: list[dict[str, Any]] = Field(default_factory=list)


class OMCProjectCandidates(_FrozenBaseModel):
    """Project-scoped candidate lesson list."""

    project_id: str
    candidates: list[dict[str, Any]] = Field(default_factory=list)


class OMCProjectAdoptedHistory(_FrozenBaseModel):
    """Explicitly adopted candidate history for the OMC project."""

    project_id: str
    adopted_candidates: list[dict[str, Any]] = Field(default_factory=list)


class CandidateAdoptionResponse(_FrozenBaseModel):
    """Result of user-triggered candidate adoption."""

    project_id: str
    candidate_id: str
    status: str
    adopted_at: str
    adopted_by: str
    run_record_ref: str
    adoption_artifact_ref: str
    ledger_refs: list[str] = Field(default_factory=list)
    candidate: dict[str, Any]


class CapabilitiesResponse(_FrozenBaseModel):
    """First-stage capability registry list."""

    capabilities: list[dict[str, Any]] = Field(default_factory=list)


class CapabilityHealthCheckResponse(_FrozenBaseModel):
    """Capability health-check result wrapper."""

    capability: dict[str, Any]
    result: dict[str, Any]


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
    WorkspaceProject = _schemas.WorkspaceProject
    CapabilityRegistryEntry = _schemas.CapabilityRegistryEntry
    CapabilityHealthResult = _schemas.CapabilityHealthResult
    CandidateLesson = _schemas.CandidateLesson
    R6GateState = importlib.import_module("noeticbraid_core.r6_gate").R6GateState
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

    class WorkspaceProject(_FallbackCoreModel):
        pass

    class CapabilityRegistryEntry(_FallbackCoreModel):
        pass

    class CapabilityHealthResult(_FallbackCoreModel):
        pass

    class CandidateLesson(_FallbackCoreModel):
        pass

    class R6GateState(_FallbackCoreModel):
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
    WorkspaceProject,
    CapabilityRegistryEntry,
    CapabilityHealthResult,
    CandidateLesson,
    R6GateState,
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
    "WorkspaceProject",
    "CapabilityRegistryEntry",
    "CapabilityHealthResult",
    "CandidateLesson",
    "R6GateState",
    "OMCProjectTaskRequest",
    "OMCProjectTaskResponse",
    "OMCProjectCandidates",
    "OMCProjectAdoptedHistory",
    "CandidateAdoptionResponse",
    "CapabilitiesResponse",
    "CapabilityHealthCheckResponse",
)

__all__ = [
    "CONTRACT_AUTHORITATIVE",
    "CONTRACT_VERSION",
    "CONTRACT_V2_VERSION",
    "OPENAPI_TITLE",
    "FROZEN_ROUTE_SPECS",
    "OMC_WORKSPACE_ROUTE_SPECS",
    "CONTRACT_1_3_ROUTE_SPECS",
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
    "OMCProjectTaskRequest",
    "OMCProjectTaskResponse",
    "OMCProjectCandidates",
    "OMCProjectAdoptedHistory",
    "CandidateAdoptionResponse",
    "CapabilitiesResponse",
    "CapabilityHealthCheckResponse",
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
    "WorkspaceProject",
    "CapabilityRegistryEntry",
    "CapabilityHealthResult",
    "CandidateLesson",
    "R6GateState",
]

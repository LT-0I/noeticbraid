# SPDX-License-Identifier: Apache-2.0
"""Static helpers for the frozen Phase 1.2 v1.2.0 API contract."""

from __future__ import annotations

import importlib
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

CONTRACT_VERSION = "1.2.0"
CONTRACT_AUTHORITATIVE = True
OPENAPI_TITLE = "NoeticBraid Phase 1.2 API"

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
    SideNote = _schemas.SideNote
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

    class SideNote(_FallbackCoreModel):
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
    "OPENAPI_TITLE",
    "FROZEN_ROUTE_SPECS",
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

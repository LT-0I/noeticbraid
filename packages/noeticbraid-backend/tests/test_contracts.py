from __future__ import annotations

from typing import get_args

from noeticbraid_backend.contracts import (
    ALL_SCHEMA_NAMES,
    CONTRACT_V2_ROUTE_SPECS,
    CONTRACT_V2_SCHEMA_METADATA,
    CONTRACT_V2_SCHEMA_NAMES,
    CONTRACT_V2_VERSION,
    CONTRACT_VERSION,
    FROZEN_ROUTE_SPECS,
    SideNote,
)


def test_contract_v1_4_0_minor_bump_preserves_frozen_routes() -> None:
    assert CONTRACT_VERSION == "1.4.0"
    assert tuple(spec["path"] for spec in FROZEN_ROUTE_SPECS) == (
        "/api/health",
        "/api/auth/startup_token",
        "/api/dashboard/empty",
        "/api/workspace/threads",
        "/api/approval/queue",
        "/api/account/pool",
        "/api/ledger/runs",
        "/api/ledger/runs/aggregate",
    )
    assert ALL_SCHEMA_NAMES == (
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
    assert set(SideNote.model_fields) == {
        "note_id",
        "created_at",
        "linked_source_refs",
        "note_type",
        "claim",
        "confidence",
        "user_response",
        "follow_up_ref",
    }
    assert set(get_args(SideNote.model_fields["note_type"].annotation)) == {
        "fact",
        "hypothesis",
        "challenge",
        "action",
    }


def test_contract_v2_metadata_registered_flat() -> None:
    assert CONTRACT_V2_VERSION == "2.0.0"
    assert CONTRACT_V2_SCHEMA_NAMES == ("SideNote",)
    assert CONTRACT_V2_ROUTE_SPECS == ()
    side_note = CONTRACT_V2_SCHEMA_METADATA["SideNote"]
    assert side_note["required_metadata"] == (
        "evidence_source",
        "note_type",
        "confidence",
        "tone_constraint",
        "user_response_channel",
    )
    assert side_note["note_type_enum"] == ("fact", "hypothesis", "action_suggestion")
    assert side_note["confidence_enum"] == ("low", "medium", "high")
    assert side_note["tone_constraint"] == "不审判用户 / 不羞辱用户 / 不替用户解释自己；违反任一构成 fatal"
    assert side_note["user_response_channel_enum"] == (
        "accept",
        "rebut",
        "mark_inaccurate",
        "disable_this_type",
    )

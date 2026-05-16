# SPDX-License-Identifier: Apache-2.0
# ruff: noqa: E402
"""Parity tests for additive orchestration vendor-port adapters."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parent.parent
SRC_ROOT = PACKAGE_ROOT / "src"
CORE_SRC_ROOT = REPO_ROOT / "packages" / "noeticbraid-core" / "src"
for path in (CORE_SRC_ROOT, SRC_ROOT, REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import pytest

from noeticbraid_backend.orchestration.approvals import (
    ApprovalDefinition,
    DoorType,
    classify_approval,
)
from noeticbraid_backend.orchestration.artifacts import (
    has_complete_planning_pair,
    parse_planning_artifact_file_name,
    planning_artifact_timestamp,
    select_latest_planning_artifact_path,
    select_matching_test_specs_for_prd,
)
from noeticbraid_backend.orchestration.cost_estimate import estimate_cost
from noeticbraid_backend.orchestration.ledger_contracts import (
    can_transition_team_task_status,
    is_dispatch_status,
    is_safe_task_id,
    is_safe_team_name,
    is_safe_worker_name,
    is_terminal_team_task_status,
)
from noeticbraid_backend.orchestration.ledger_schema import (
    DecisionEvent,
    GovernanceEvent,
    SessionEvent,
    SkillRunEvent,
    StateStoreSnapshot,
    WorkItemEvent,
)
from noeticbraid_backend.orchestration.verification_tier import (
    ChangeMetadata,
    build_change_metadata,
    detect_architectural_changes,
    detect_security_implications,
    get_verification_agent,
    select_verification_tier,
)


def test_ledger_contracts_match_upstream_status_and_safe_id_rules() -> None:
    assert is_safe_team_name("team-1")
    assert not is_safe_team_name("Team-1")
    assert is_safe_worker_name("worker-123")
    assert not is_safe_worker_name("worker_123")
    assert is_safe_task_id("12345678901234567890")
    assert not is_safe_task_id("task-1")

    assert not is_terminal_team_task_status("pending")
    assert is_terminal_team_task_status("completed")
    assert can_transition_team_task_status("in_progress", "completed")
    assert can_transition_team_task_status("in_progress", "failed")
    assert not can_transition_team_task_status("pending", "completed")

    assert is_dispatch_status("notified")
    assert not is_dispatch_status("queued")


def test_artifact_names_matching_and_completeness() -> None:
    stamp = planning_artifact_timestamp(datetime(2026, 5, 16, 1, 2, 3, tzinfo=UTC))
    assert stamp == "20260516T010203Z"

    parsed = parse_planning_artifact_file_name(f"/tmp/prd-{stamp}-vendor-port.md")
    assert parsed is not None
    assert (parsed.kind, parsed.slug, parsed.timestamp) == ("prd", "vendor-port", stamp)

    tests = [
        "/plans/test-spec-old.md",
        f"/plans/test-spec-{stamp}-vendor-port.md",
        f"/plans/test-spec-{stamp}-other.md",
    ]
    assert select_matching_test_specs_for_prd(f"/plans/prd-{stamp}-vendor-port.md", tests) == [
        f"/plans/test-spec-{stamp}-vendor-port.md"
    ]
    assert select_matching_test_specs_for_prd("/plans/prd-legacy.md", tests) == []
    assert select_matching_test_specs_for_prd(
        "/plans/prd-legacy.md",
        ["/plans/test-spec-legacy.md", "/plans/testspec-legacy.md"],
    ) == ["/plans/test-spec-legacy.md", "/plans/testspec-legacy.md"]

    assert select_latest_planning_artifact_path(
        ["/plans/prd-alpha.md", f"/plans/prd-{stamp}-vendor-port.md"]
    ) == f"/plans/prd-{stamp}-vendor-port.md"

    prd = "## Acceptance criteria\nA\n\n## Requirement coverage map\nB\n"
    spec = "## Unit coverage\nC\n\n## Verification mapping\nD\n"
    assert has_complete_planning_pair(prd, spec)
    assert not has_complete_planning_pair(prd, "## Unit coverage\nC\n")


def test_verification_tier_selector_matches_upstream_thresholds() -> None:
    assert select_verification_tier(
        ChangeMetadata(
            files_changed=4,
            lines_changed=99,
            has_architectural_changes=False,
            has_security_implications=False,
            test_coverage="full",
        )
    ) == "LIGHT"
    assert select_verification_tier(
        ChangeMetadata(
            files_changed=21,
            lines_changed=1,
            has_architectural_changes=False,
            has_security_implications=False,
            test_coverage="full",
        )
    ) == "THOROUGH"
    assert select_verification_tier(
        ChangeMetadata(
            files_changed=4,
            lines_changed=100,
            has_architectural_changes=False,
            has_security_implications=False,
            test_coverage="full",
        )
    ) == "STANDARD"
    assert get_verification_agent("THOROUGH").evidence_required == (
        "full architect review",
        "all tests pass",
        "no regressions",
    )

    assert detect_architectural_changes(["src/team/types.ts"])
    assert detect_security_implications(["src/auth/login.ts"])
    metadata = build_change_metadata(["package.json"], 2, "partial")
    assert metadata.has_architectural_changes
    assert select_verification_tier(metadata) == "THOROUGH"


def test_approval_classification_registry_then_fallbacks() -> None:
    registry = {
        "safe-choice": ApprovalDefinition(
            id="safe-choice",
            skill="plan",
            category="routing",
            door_type=DoorType.TWO_WAY,
            description="Choose a reversible route.",
        ),
        "must-ask": ApprovalDefinition(
            id="must-ask",
            skill="ship",
            category="approval",
            door_type=DoorType.ONE_WAY,
            description="Stop for destructive action.",
        ),
    }

    assert classify_approval(question_id="safe-choice", registry=registry).reason == "registry"
    assert not classify_approval(question_id="safe-choice", registry=registry).one_way
    assert classify_approval(question_id="must-ask", registry=registry).one_way

    skill_gate = classify_approval(skill="cso", category="approval")
    assert (skill_gate.one_way, skill_gate.reason) == (True, "skill-category")

    keyword_gate = classify_approval(summary="Run terraform destroy for this stack")
    assert (keyword_gate.one_way, keyword_gate.reason) == (True, "keyword")

    default_gate = classify_approval(summary="Pick a label color")
    assert (default_gate.one_way, default_gate.reason) == (False, "default-two-way")


def test_cost_estimate_uses_upstream_rates_and_rounding() -> None:
    assert estimate_cost("claude-3-haiku", 1_000_000, 1_000_000) == 4.8
    assert estimate_cost("claude-3-sonnet", 500_000, 250_000) == 5.25
    assert estimate_cost("unknown", 1_000, 1_000) == 0.018
    assert estimate_cost("opus", 1, 1) == 0.00009


def test_ledger_schema_dataclasses_emit_state_store_shape() -> None:
    snapshot = StateStoreSnapshot(
        sessions=(
            SessionEvent(
                id="s1",
                adapter_id="adapter",
                harness="local",
                state="running",
                repo_root=None,
                started_at="2026-05-16T00:00:00Z",
                ended_at=None,
                snapshot={},
            ),
        ),
        skill_runs=(
            SkillRunEvent(
                id="run1",
                skill_id="plan",
                skill_version="v1",
                session_id="s1",
                task_description="Plan",
                outcome="ok",
                failure_reason=None,
                tokens_used=12,
                duration_ms=34,
                user_feedback=None,
                created_at="2026-05-16T00:00:01Z",
            ),
        ),
        decisions=(
            DecisionEvent(
                id="d1",
                session_id="s1",
                title="Use adapter",
                rationale="Pure Python",
                alternatives=[],
                supersedes=None,
                status="accepted",
                created_at="2026-05-16T00:00:02Z",
            ),
        ),
        governance_events=(
            GovernanceEvent(
                id="g1",
                session_id=None,
                event_type="approval_classified",
                payload={"oneWay": True},
                resolved_at=None,
                resolution=None,
                created_at="2026-05-16T00:00:03Z",
            ),
        ),
        work_items=(
            WorkItemEvent(
                id="w1",
                source="local",
                source_id=None,
                title="Implement",
                status="open",
                priority=None,
                url=None,
                owner=None,
                repo_root=None,
                session_id="s1",
                metadata={},
                created_at="2026-05-16T00:00:04Z",
                updated_at="2026-05-16T00:00:05Z",
            ),
        ),
    )

    dumped = snapshot.to_schema_dict()
    assert dumped["sessions"][0]["adapterId"] == "adapter"
    assert dumped["skillRuns"][0]["tokensUsed"] == 12
    assert dumped["governanceEvents"][0]["eventType"] == "approval_classified"

    with pytest.raises(ValueError):
        SkillRunEvent(
            id="bad",
            skill_id="plan",
            skill_version="v1",
            session_id="s1",
            task_description="Plan",
            outcome="ok",
            failure_reason=None,
            tokens_used=-1,
            duration_ms=None,
            user_feedback=None,
            created_at="2026-05-16T00:00:01Z",
        )

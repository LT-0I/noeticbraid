from __future__ import annotations

from typing import get_args

from noeticbraid_core.schemas import RunRecord


def test_omc_workspace_does_not_add_runrecord_event_type_by_default() -> None:
    assert set(get_args(RunRecord.model_fields["event_type"].annotation)) == {
        "task_created",
        "task_classified",
        "context_built",
        "approval_requested",
        "approval_decision_recorded",
        "web_ai_call_requested",
        "profile_health_checked",
        "source_record_linked",
        "artifact_created",
        "security_violation",
        "lesson_candidate_created",
        "routing_advice_recorded",
        "task_completed",
        "task_failed",
    }

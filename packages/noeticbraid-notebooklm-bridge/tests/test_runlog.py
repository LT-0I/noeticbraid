from __future__ import annotations

from noeticbraid.tools.notebooklm_bridge._runlog import build_event, redact
from noeticbraid.tools.notebooklm_bridge._types import OperationEvent


def test_redact_removes_tokens_and_cookies() -> None:
    payload = redact({"authorization": "Bearer abc.def", "message": "Cookie: SID=secret; ok"})
    assert payload["authorization"] == "[REDACTED]"
    assert "SID=secret" not in payload["message"]


def test_failed_event_maps_to_task_failed() -> None:
    event = build_event(OperationEvent("pull_briefing", "failed", "notebook_abc", message="bad"))
    assert event["event_type"] == "task_failed"
    assert event["status"] == "failed"
    assert event["run_id"].startswith("run_")
    assert event["task_id"].startswith("task_")


def test_started_event_does_not_claim_created_or_linked() -> None:
    for op in ("push_sources", "pull_briefing", "pull_faq"):
        event = build_event(OperationEvent(op, "started", "notebook_abc"))
        assert event["event_type"] == "task_created"
        assert event["event_type"] not in {"artifact_created", "source_record_linked"}


def test_redact_str_is_exported_for_caller_facing_errors() -> None:
    from noeticbraid.tools.notebooklm_bridge import redact_str

    assert "secret" not in redact_str("Authorization: Bearer secret")

"""RunRecord aggregate behavior for contract 1.2.0."""

from __future__ import annotations

from datetime import datetime, timezone

from noeticbraid_core.ledger.aggregate import RunRecordAggregator
from noeticbraid_core.schemas import RunRecord


def _event(
    event_type: str,
    *,
    run_id: str = "run_test01",
    task_id: str = "task_test01",
    created_at: datetime | None = None,
    model_refs: list[str] | None = None,
    artifact_refs: list[str] | None = None,
    routing_advice: str | None = None,
) -> RunRecord:
    return RunRecord(
        run_id=run_id,
        task_id=task_id,
        event_type=event_type,  # type: ignore[arg-type]
        created_at=created_at or datetime(2026, 5, 3, 12, 0, 0, tzinfo=timezone.utc),
        actor="system",
        model_refs=model_refs or [],
        source_refs=[],
        artifact_refs=artifact_refs or [],
        routing_advice=routing_advice,
        status="recorded",
    )


def test_empty_stream() -> None:
    aggregate = RunRecordAggregator.group_by_run_id([], run_id="run_empty01", task_id=None)

    assert aggregate.run_id == "run_empty01"
    assert aggregate.task_id is None
    assert aggregate.event_count == 0
    assert aggregate.first_event_at is None
    assert aggregate.last_event_at is None
    assert aggregate.models_used == []
    assert aggregate.artifacts == []
    assert aggregate.errors == []
    assert aggregate.lessons_summary == []


def test_single_event() -> None:
    event = _event("task_created")

    aggregate = RunRecordAggregator.group_by_run_id([event])

    assert aggregate.run_id == "run_test01"
    assert aggregate.task_id == "task_test01"
    assert aggregate.event_count == 1
    assert aggregate.first_event_at == event.created_at
    assert aggregate.last_event_at == event.created_at


def test_multi_event_same_run() -> None:
    first = _event(
        "task_created",
        created_at=datetime(2026, 5, 3, 12, 0, 0, tzinfo=timezone.utc),
        model_refs=["model_alpha"],
    )
    second = _event(
        "task_completed",
        created_at=datetime(2026, 5, 3, 12, 5, 0, tzinfo=timezone.utc),
        model_refs=["model_alpha", "model_beta"],
    )

    aggregate = RunRecordAggregator.group_by_run_id([second, first])

    assert aggregate.event_count == 2
    assert aggregate.first_event_at == first.created_at
    assert aggregate.last_event_at == second.created_at
    assert aggregate.models_used == ["model_alpha", "model_beta"]


def test_lesson_candidate() -> None:
    event = _event("lesson_candidate_created", artifact_refs=["artifact_lesson_summary"])

    aggregate = RunRecordAggregator.group_by_run_id([event])

    assert len(aggregate.lessons_summary) == 1
    lesson = aggregate.lessons_summary[0]
    assert lesson.event_id == "run_test01_0001"
    assert lesson.lesson_candidate_text == "artifact_lesson_summary"


def test_errors() -> None:
    failed = _event("task_failed", artifact_refs=["artifact_failure_summary"])
    violation = _event("security_violation", artifact_refs=["artifact_security_summary"])

    aggregate = RunRecordAggregator.group_by_run_id([failed, violation])

    assert [(error.event_id, error.error_kind, error.message) for error in aggregate.errors] == [
        ("run_test01_0001", "task_failed", "artifact_failure_summary"),
        ("run_test01_0002", "security_violation", "artifact_security_summary"),
    ]


def test_no_leak_regression() -> None:
    sensitive = "sk-1234567890abc cookie=session_xxx $env:TOKEN_X C:\\Users\\test\\AppData\\Roaming\\Profile"
    failed = _event(
        "task_failed",
        model_refs=["model_test"],
        artifact_refs=["artifact_safe_error_summary"],
        routing_advice=sensitive,
    )
    lesson = _event(
        "lesson_candidate_created",
        model_refs=["model_test"],
        artifact_refs=["artifact_safe_lesson_summary"],
        routing_advice=sensitive,
    )

    aggregate = RunRecordAggregator.group_by_run_id([failed, lesson])
    rendered = aggregate.model_dump_json()

    assert "model_test" in rendered
    assert "sk-" not in rendered
    assert "cookie=" not in rendered
    assert "$env:TOKEN_X" not in rendered
    assert "AppData" not in rendered
    assert "Profile" not in rendered

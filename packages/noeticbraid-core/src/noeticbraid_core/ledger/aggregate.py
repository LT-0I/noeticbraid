"""RunRecord aggregation utilities for contract 1.2.0."""

from __future__ import annotations

import re
from typing import Iterable, Optional

from noeticbraid_core.schemas import (
    AggregateArtifact,
    AggregateError,
    AggregateLesson,
    RunRecord,
    RunRecordAggregate,
)

_ARTIFACT_REF_RE = re.compile(r"^artifact_[A-Za-z0-9_]+$")
_SECRET_LIKE_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9]+", re.IGNORECASE),
    re.compile(r"cookie=[^\s;]+", re.IGNORECASE),
    re.compile(r"\$env:[A-Za-z_][A-Za-z0-9_]*", re.IGNORECASE),
    re.compile(r"C:\\Users\\[^\s]+", re.IGNORECASE),
)


class RunRecordAggregator:
    """Build a best-effort aggregate view from append-only RunRecord events."""

    @staticmethod
    def group_by_run_id(
        events: list[RunRecord],
        *,
        run_id: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> RunRecordAggregate:
        """Aggregate records that share one run_id.

        Empty streams need an explicit ``run_id`` because no event can supply
        the grouping key. ``task_id`` may be ``None`` for that empty-stream
        case, matching the nullable contract field.
        """

        if not events:
            if run_id is None:
                raise ValueError("run_id is required when aggregating an empty event stream")
            return RunRecordAggregate(
                run_id=run_id,
                task_id=task_id,
                event_count=0,
                first_event_at=None,
                last_event_at=None,
                models_used=[],
                artifacts=[],
                errors=[],
                lessons_summary=[],
            )

        aggregate_run_id = run_id or events[0].run_id
        for event in events:
            if event.run_id != aggregate_run_id:
                raise ValueError("all events must share one run_id")

        aggregate_task_id = task_id or _first_task_id(events)
        models_used = _dedupe_model_refs(events)
        created_at_values = [event.created_at for event in events]

        artifacts: list[AggregateArtifact] = []
        errors: list[AggregateError] = []
        lessons: list[AggregateLesson] = []

        for index, event in enumerate(events, start=1):
            event_id = _event_id(event.run_id, index)
            if event.event_type == "artifact_created":
                artifacts.extend(
                    AggregateArtifact(event_id=event_id, artifact_ref=artifact_ref)
                    for artifact_ref in _safe_artifact_refs(event.artifact_refs)
                )
            elif event.event_type in ("task_failed", "security_violation"):
                errors.append(
                    AggregateError(
                        event_id=event_id,
                        error_kind=event.event_type,
                        message=_artifact_summary(event.artifact_refs),
                    )
                )
            elif event.event_type == "lesson_candidate_created":
                lessons.append(
                    AggregateLesson(
                        event_id=event_id,
                        lesson_candidate_text=_artifact_summary(event.artifact_refs),
                    )
                )

        return RunRecordAggregate(
            run_id=aggregate_run_id,
            task_id=aggregate_task_id,
            event_count=len(events),
            first_event_at=min(created_at_values),
            last_event_at=max(created_at_values),
            models_used=models_used,
            artifacts=artifacts,
            errors=errors,
            lessons_summary=lessons,
        )


def _first_task_id(events: Iterable[RunRecord]) -> Optional[str]:
    for event in events:
        if event.task_id:
            return event.task_id
    return None


def _dedupe_model_refs(events: Iterable[RunRecord]) -> list[str]:
    models: list[str] = []
    seen: set[str] = set()
    for event in events:
        for model_ref in event.model_refs:
            if model_ref not in seen:
                seen.add(model_ref)
                models.append(model_ref)
    return models


def _event_id(run_id: str, index: int) -> str:
    return f"{run_id}_{index:04d}"


def _safe_artifact_refs(artifact_refs: Iterable[str]) -> list[str]:
    return [ref for ref in artifact_refs if _ARTIFACT_REF_RE.fullmatch(_sanitize_text(ref))]


def _artifact_summary(artifact_refs: Iterable[str]) -> Optional[str]:
    safe_refs = _safe_artifact_refs(artifact_refs)
    if not safe_refs:
        return None
    return "; ".join(safe_refs)


def _sanitize_text(value: str) -> str:
    clean = value
    for pattern in _SECRET_LIKE_PATTERNS:
        clean = pattern.sub("[redacted]", clean)
    return clean

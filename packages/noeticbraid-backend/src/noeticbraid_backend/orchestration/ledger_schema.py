# SPDX-License-Identifier: Apache-2.0
"""ECC state-store schema ported into Python dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

JsonValue = dict[str, Any] | list[Any] | str | int | float | bool | None
JsonArray = list[Any]


def _require_non_empty(value: str, field_name: str) -> str:
    if not isinstance(value, str) or value == "":
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _nullable_non_negative(value: int | None, field_name: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer or None")
    return value


@dataclass(frozen=True)
class SessionEvent:
    """State-store session record."""

    id: str
    adapter_id: str
    harness: str
    state: str
    repo_root: str | None
    started_at: str | None
    ended_at: str | None
    snapshot: dict[str, Any] | list[Any]

    def __post_init__(self) -> None:
        _require_non_empty(self.id, "id")
        _require_non_empty(self.adapter_id, "adapter_id")
        _require_non_empty(self.harness, "harness")
        _require_non_empty(self.state, "state")
        if not isinstance(self.snapshot, (dict, list)):
            raise ValueError("snapshot must be an object or array")

    def to_schema_dict(self) -> dict[str, JsonValue]:
        return {
            "id": self.id,
            "adapterId": self.adapter_id,
            "harness": self.harness,
            "state": self.state,
            "repoRoot": self.repo_root,
            "startedAt": self.started_at,
            "endedAt": self.ended_at,
            "snapshot": self.snapshot,
        }


@dataclass(frozen=True)
class SkillRunEvent:
    """State-store skillRun record."""

    id: str
    skill_id: str
    skill_version: str
    session_id: str
    task_description: str
    outcome: str
    failure_reason: str | None
    tokens_used: int | None
    duration_ms: int | None
    user_feedback: str | None
    created_at: str

    def __post_init__(self) -> None:
        for field_name in (
            "id",
            "skill_id",
            "skill_version",
            "session_id",
            "task_description",
            "outcome",
            "created_at",
        ):
            _require_non_empty(getattr(self, field_name), field_name)
        _nullable_non_negative(self.tokens_used, "tokens_used")
        _nullable_non_negative(self.duration_ms, "duration_ms")

    def to_schema_dict(self) -> dict[str, JsonValue]:
        return {
            "id": self.id,
            "skillId": self.skill_id,
            "skillVersion": self.skill_version,
            "sessionId": self.session_id,
            "taskDescription": self.task_description,
            "outcome": self.outcome,
            "failureReason": self.failure_reason,
            "tokensUsed": self.tokens_used,
            "durationMs": self.duration_ms,
            "userFeedback": self.user_feedback,
            "createdAt": self.created_at,
        }


@dataclass(frozen=True)
class DecisionEvent:
    """State-store decision record."""

    id: str
    session_id: str
    title: str
    rationale: str
    alternatives: JsonArray
    supersedes: str | None
    status: str
    created_at: str

    def __post_init__(self) -> None:
        for field_name in ("id", "session_id", "title", "rationale", "status", "created_at"):
            _require_non_empty(getattr(self, field_name), field_name)
        if not isinstance(self.alternatives, list):
            raise ValueError("alternatives must be an array")

    def to_schema_dict(self) -> dict[str, JsonValue]:
        return {
            "id": self.id,
            "sessionId": self.session_id,
            "title": self.title,
            "rationale": self.rationale,
            "alternatives": self.alternatives,
            "supersedes": self.supersedes,
            "status": self.status,
            "createdAt": self.created_at,
        }


@dataclass(frozen=True)
class GovernanceEvent:
    """State-store governanceEvent record."""

    id: str
    session_id: str | None
    event_type: str
    payload: JsonValue
    resolved_at: str | None
    resolution: str | None
    created_at: str

    def __post_init__(self) -> None:
        _require_non_empty(self.id, "id")
        _require_non_empty(self.event_type, "event_type")
        _require_non_empty(self.created_at, "created_at")

    def to_schema_dict(self) -> dict[str, JsonValue]:
        return {
            "id": self.id,
            "sessionId": self.session_id,
            "eventType": self.event_type,
            "payload": self.payload,
            "resolvedAt": self.resolved_at,
            "resolution": self.resolution,
            "createdAt": self.created_at,
        }


@dataclass(frozen=True)
class WorkItemEvent:
    """State-store workItem record."""

    id: str
    source: str
    source_id: str | None
    title: str
    status: str
    priority: str | None
    url: str | None
    owner: str | None
    repo_root: str | None
    session_id: str | None
    metadata: JsonValue
    created_at: str
    updated_at: str

    def __post_init__(self) -> None:
        for field_name in ("id", "source", "title", "status", "created_at", "updated_at"):
            _require_non_empty(getattr(self, field_name), field_name)

    def to_schema_dict(self) -> dict[str, JsonValue]:
        return {
            "id": self.id,
            "source": self.source,
            "sourceId": self.source_id,
            "title": self.title,
            "status": self.status,
            "priority": self.priority,
            "url": self.url,
            "owner": self.owner,
            "repoRoot": self.repo_root,
            "sessionId": self.session_id,
            "metadata": self.metadata,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }


@dataclass(frozen=True)
class StateStoreSnapshot:
    """Top-level state-store shape."""

    sessions: tuple[SessionEvent, ...] = field(default_factory=tuple)
    skill_runs: tuple[SkillRunEvent, ...] = field(default_factory=tuple)
    decisions: tuple[DecisionEvent, ...] = field(default_factory=tuple)
    governance_events: tuple[GovernanceEvent, ...] = field(default_factory=tuple)
    work_items: tuple[WorkItemEvent, ...] = field(default_factory=tuple)

    def to_schema_dict(self) -> dict[str, list[dict[str, JsonValue]]]:
        return {
            "sessions": [item.to_schema_dict() for item in self.sessions],
            "skillRuns": [item.to_schema_dict() for item in self.skill_runs],
            "decisions": [item.to_schema_dict() for item in self.decisions],
            "governanceEvents": [item.to_schema_dict() for item in self.governance_events],
            "workItems": [item.to_schema_dict() for item in self.work_items],
        }


__all__ = [
    "DecisionEvent",
    "GovernanceEvent",
    "JsonArray",
    "JsonValue",
    "SessionEvent",
    "SkillRunEvent",
    "StateStoreSnapshot",
    "WorkItemEvent",
]

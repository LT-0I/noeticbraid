# SPDX-License-Identifier: Apache-2.0
"""Task lifecycle model for the additive platform shell."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from noeticbraid_backend.omc_workspace.web_ai_hub_compat import TASK_ID_RE
from noeticbraid_backend.orchestration import ledger_contracts as cv_ledger_contracts

ACCOUNT_REF_PREFIX = "acct_"
ACCOUNT_REF_HEX_CHARS = 16
TASK_STATE_TRANSITION_SOURCE = cv_ledger_contracts.__name__


class TaskState(StrEnum):
    """Replayable C2 task lifecycle states."""

    CREATED = "created"
    PLANNING = "planning"
    DISPATCHING = "dispatching"
    PRODUCING = "producing"
    CROSS_VALIDATING = "cross_validating"
    DELIVERED = "delivered"
    BLOCKED = "blocked"
    ERROR = "error"


TASK_STATE_TRANSITIONS: dict[TaskState, tuple[TaskState, ...]] = {
    TaskState.CREATED: (TaskState.PLANNING, TaskState.BLOCKED, TaskState.ERROR),
    TaskState.PLANNING: (TaskState.DISPATCHING, TaskState.BLOCKED, TaskState.ERROR),
    TaskState.DISPATCHING: (TaskState.PRODUCING, TaskState.BLOCKED, TaskState.ERROR),
    TaskState.PRODUCING: (TaskState.CROSS_VALIDATING, TaskState.BLOCKED, TaskState.ERROR),
    TaskState.CROSS_VALIDATING: (
        TaskState.DELIVERED,
        TaskState.BLOCKED,
        TaskState.ERROR,
    ),
    TaskState.DELIVERED: (),
    TaskState.BLOCKED: (),
    TaskState.ERROR: (),
}
TERMINAL_TASK_STATES = frozenset({TaskState.DELIVERED, TaskState.BLOCKED, TaskState.ERROR})


@dataclass(frozen=True, slots=True)
class Task:
    """Private persisted task metadata."""

    task_id: str
    account_id_ref: str
    title: str
    state: TaskState
    created_ts: str
    updated_ts: str
    modality_targets: list[str]

    def __post_init__(self) -> None:
        validate_task_id(self.task_id)
        _validate_account_ref(self.account_id_ref)
        if not isinstance(self.title, str) or not self.title.strip():
            raise ValueError("title must be a non-empty string")
        if not isinstance(self.created_ts, str) or not self.created_ts:
            raise ValueError("created_ts must be a non-empty string")
        if not isinstance(self.updated_ts, str) or not self.updated_ts:
            raise ValueError("updated_ts must be a non-empty string")
        if not isinstance(self.modality_targets, list) or any(
            not isinstance(item, str) or not item for item in self.modality_targets
        ):
            raise ValueError("modality_targets must be a list of non-empty strings")
        if not isinstance(self.state, TaskState):
            object.__setattr__(self, "state", TaskState(str(self.state)))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a stable JSON object for task.json."""

        return {
            "task_id": self.task_id,
            "account_id_ref": self.account_id_ref,
            "title": self.title,
            "state": self.state.value,
            "created_ts": self.created_ts,
            "updated_ts": self.updated_ts,
            "modality_targets": list(self.modality_targets),
        }

    @classmethod
    def from_json_dict(cls, payload: dict[str, Any]) -> "Task":
        """Build a validated task from task.json."""

        return cls(
            task_id=str(payload["task_id"]),
            account_id_ref=str(payload["account_id_ref"]),
            title=str(payload["title"]),
            state=TaskState(str(payload["state"])),
            created_ts=str(payload["created_ts"]),
            updated_ts=str(payload["updated_ts"]),
            modality_targets=[str(item) for item in payload.get("modality_targets", [])],
        )


def validate_task_id(value: str) -> str:
    """Validate and return a hub-correlatable C2 task id."""

    if not isinstance(value, str) or TASK_ID_RE.fullmatch(value) is None:
        raise ValueError("task_id must match ^task_[a-z0-9_]{1,128}$")
    return value


def account_ref_for(account: str) -> str:
    """Return the opaque short account reference persisted by C2 records."""

    if not isinstance(account, str) or not account:
        raise ValueError("account must be a non-empty string")
    digest = hashlib.sha256(account.encode("utf-8")).hexdigest()[:ACCOUNT_REF_HEX_CHARS]
    return f"{ACCOUNT_REF_PREFIX}{digest}"


def can_transition_task_state(from_state: TaskState | str, to_state: TaskState | str) -> bool:
    """Return whether a lifecycle transition is legal."""

    source = TaskState(str(from_state))
    target = TaskState(str(to_state))
    return target in TASK_STATE_TRANSITIONS[source]


def validate_task_transition(from_state: TaskState | str, to_state: TaskState | str) -> None:
    """Raise ValueError when a lifecycle transition is illegal."""

    source = TaskState(str(from_state))
    target = TaskState(str(to_state))
    if not can_transition_task_state(source, target):
        raise ValueError(f"illegal task state transition: {source.value} -> {target.value}")


def is_terminal_task_state(value: TaskState | str) -> bool:
    """Return true for delivered, blocked, or error."""

    return TaskState(str(value)) in TERMINAL_TASK_STATES


def _validate_account_ref(value: str) -> None:
    if not isinstance(value, str) or not value.startswith(ACCOUNT_REF_PREFIX):
        raise ValueError("account_id_ref must be an opaque account reference")
    suffix = value[len(ACCOUNT_REF_PREFIX) :]
    if len(suffix) != ACCOUNT_REF_HEX_CHARS or any(char not in "0123456789abcdef" for char in suffix):
        raise ValueError("account_id_ref must use the expected short hash shape")


__all__ = [
    "ACCOUNT_REF_HEX_CHARS",
    "ACCOUNT_REF_PREFIX",
    "TASK_ID_RE",
    "TASK_STATE_TRANSITION_SOURCE",
    "TASK_STATE_TRANSITIONS",
    "TERMINAL_TASK_STATES",
    "Task",
    "TaskState",
    "account_ref_for",
    "can_transition_task_state",
    "is_terminal_task_state",
    "validate_task_id",
    "validate_task_transition",
]

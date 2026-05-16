# SPDX-License-Identifier: Apache-2.0
"""Private JSON task store rooted through resolve_user_path."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

from noeticbraid_backend.platform.ledger.events import dispatch_event, error_event
from noeticbraid_backend.platform.ledger.writer import append_event
from noeticbraid_backend.platform.tasks.models import (
    Task,
    TaskState,
    account_ref_for,
    validate_task_id,
    validate_task_transition,
)
from noeticbraid_backend.platform.workspace_paths import resolve_user_path

TASK_FILENAME = "task.json"


class TaskStoreError(Exception):
    """Base exception for task store failures."""


class TaskNotFound(TaskStoreError):
    """Raised when task.json is missing."""


class TaskAlreadyExists(TaskStoreError):
    """Raised when creating a task that already exists."""


class MalformedTask(TaskStoreError):
    """Raised when task.json cannot be trusted."""


class IllegalTaskTransition(TaskStoreError):
    """Raised when a task lifecycle transition is rejected."""


def create_task(
    account: str,
    *,
    task_id: str,
    title: str,
    modality_targets: Iterable[str] = (),
    created_ts: str | None = None,
) -> Task:
    """Create task.json and ledger the initial created state."""

    now = created_ts or _now_ts()
    task = Task(
        task_id=validate_task_id(task_id),
        account_id_ref=account_ref_for(account),
        title=title,
        state=TaskState.CREATED,
        created_ts=now,
        updated_ts=now,
        modality_targets=list(modality_targets),
    )
    path = task_path_for(account, task.task_id)
    if path.exists():
        raise TaskAlreadyExists(task.task_id)
    _write_task(path, task)
    append_event(account, dispatch_event(task.task_id, to_state=TaskState.CREATED))
    return task


def load_task(account: str, task_id: str) -> Task:
    """Load and validate one task.json."""

    path = task_path_for(account, task_id)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise TypeError("task must be an object")
        return Task.from_json_dict(payload)
    except FileNotFoundError as exc:
        raise TaskNotFound(task_id) from exc
    except TaskNotFound:
        raise
    except Exception as exc:
        raise MalformedTask(task_id) from exc


def list_tasks(account: str) -> tuple[Task, ...]:
    """List valid tasks for one account, sorted by task_id."""

    root = resolve_user_path(account, "tasks")
    if not root.exists():
        return ()
    tasks: list[Task] = []
    for path in sorted(root.glob(f"*/{TASK_FILENAME}")):
        try:
            tasks.append(Task.from_json_dict(json.loads(path.read_text(encoding="utf-8"))))
        except Exception as exc:
            raise MalformedTask(path.parent.name) from exc
    return tuple(tasks)


def update_task_state(
    account: str,
    task_id: str,
    to_state: TaskState | str,
    *,
    updated_ts: str | None = None,
) -> Task:
    """Validate, ledger, and persist a lifecycle transition."""

    current = load_task(account, task_id)
    target = TaskState(str(to_state))
    try:
        validate_task_transition(current.state, target)
    except ValueError as exc:
        append_event(
            account,
            error_event(
                current.task_id,
                reason=str(exc),
                code="illegal_transition",
                from_state=current.state,
            ),
        )
        raise IllegalTaskTransition(str(exc)) from exc

    updated = replace(current, state=target, updated_ts=updated_ts or _now_ts())
    _write_task(task_path_for(account, task_id), updated)
    append_event(
        account,
        dispatch_event(
            current.task_id,
            from_state=current.state,
            to_state=target,
        ),
    )
    return updated


def update_task(
    account: str,
    task_id: str,
    *,
    title: str | None = None,
    modality_targets: Iterable[str] | None = None,
    updated_ts: str | None = None,
) -> Task:
    """Update non-state task metadata without writing raw prompt material to the ledger."""

    current = load_task(account, task_id)
    updated = replace(
        current,
        title=current.title if title is None else title,
        modality_targets=current.modality_targets if modality_targets is None else list(modality_targets),
        updated_ts=updated_ts or _now_ts(),
    )
    _write_task(task_path_for(account, task_id), updated)
    return updated


def delete_task(account: str, task_id: str) -> None:
    """Delete task.json while leaving append-only ledger evidence intact."""

    path = task_path_for(account, task_id)
    try:
        path.unlink()
    except FileNotFoundError as exc:
        raise TaskNotFound(task_id) from exc


def task_path_for(account: str, task_id: str) -> Path:
    """Resolve task.json through the platform workspace chokepoint."""

    return resolve_user_path(account, f"tasks/{validate_task_id(task_id)}/{TASK_FILENAME}")


def _write_task(path: Path, task: Task) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_name = handle.name
            json.dump(task.to_json_dict(), handle, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temp_path = Path(temp_name)
        Task.from_json_dict(json.loads(temp_path.read_text(encoding="utf-8")))
        os.replace(temp_path, path)
        temp_name = None
        path.chmod(0o600)
    finally:
        if temp_name is not None:
            try:
                Path(temp_name).unlink()
            except OSError:
                pass


def _now_ts() -> str:
    return datetime.now(UTC).isoformat()


__all__ = [
    "TASK_FILENAME",
    "IllegalTaskTransition",
    "MalformedTask",
    "TaskAlreadyExists",
    "TaskNotFound",
    "TaskStoreError",
    "create_task",
    "delete_task",
    "list_tasks",
    "load_task",
    "task_path_for",
    "update_task",
    "update_task_state",
]

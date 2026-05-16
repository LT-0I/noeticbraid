# SPDX-License-Identifier: Apache-2.0
"""Append-only JSONL task ledger writer and replay engine."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Iterable

from noeticbraid_backend.platform.ledger.events import (
    LedgerEvent,
    LedgerEventDraft,
    event_to_json_line,
    make_enveloped_event,
)
from noeticbraid_backend.platform.settings import PlatformSettings
from noeticbraid_backend.platform.tasks.models import TaskState, validate_task_id, validate_task_transition
from noeticbraid_backend.platform.workspace_paths import resolve_user_path

LEDGER_FILENAME = "ledger.jsonl"
TASKS_INDEX_FILENAME = "tasks_index.jsonl"
INDEX_DIRNAME = "index"


class LedgerError(Exception):
    """Base exception for task ledger failures."""


class LedgerReplayError(LedgerError):
    """Raised when a ledger cannot be replayed safely."""


class MalformedLedger(LedgerReplayError):
    """Raised for malformed ledger JSONL."""


class IllegalLedgerTransition(LedgerReplayError):
    """Raised when replay encounters an illegal lifecycle transition."""


def append_event(account: str, draft: LedgerEventDraft) -> LedgerEvent:
    """Append one event using O_APPEND+fsync and atomically refresh the central index."""

    ledger_path = ledger_path_for(account, draft.task_id)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    seq = _next_seq(ledger_path)
    event = make_enveloped_event(account, draft, seq)
    line = event_to_json_line(event)

    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
    descriptor = os.open(ledger_path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "a", encoding="utf-8") as handle:
            handle.write(line)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        try:
            ledger_path.chmod(0o600)
        except OSError:
            pass

    _update_index(account, event)
    return event


def replay(task_id: str, *, account: str | None = None) -> TaskState:
    """Replay a task ledger and reconstruct the final lifecycle state."""

    validate_task_id(task_id)
    path = ledger_path_for(account, task_id) if account is not None else _discover_single_ledger_path(task_id)
    return replay_path(path, task_id=task_id)


def replay_path(path: Path, *, task_id: str | None = None) -> TaskState:
    """Replay a specific ledger path; useful for validation and tests."""

    expected_task = validate_task_id(task_id) if task_id is not None else None
    events = tuple(_read_events(path))
    if not events:
        raise MalformedLedger("ledger is empty")

    state: TaskState | None = None
    expected_seq = 1
    for event in events:
        if event.seq != expected_seq:
            raise MalformedLedger(f"ledger seq out of order: expected {expected_seq}, got {event.seq}")
        expected_seq += 1
        if expected_task is not None and event.task_id != expected_task:
            raise MalformedLedger("ledger contains a different task_id")
        raw_target = event.payload.get("to_state")
        if raw_target is None:
            continue
        try:
            target = TaskState(str(raw_target))
        except Exception as exc:
            raise MalformedLedger("ledger event has unknown to_state") from exc
        if state is None:
            if target is not TaskState.CREATED:
                raise IllegalLedgerTransition("ledger must start at created")
            state = target
            continue
        try:
            validate_task_transition(state, target)
        except ValueError as exc:
            raise IllegalLedgerTransition(str(exc)) from exc
        state = target

    if state is None:
        raise MalformedLedger("ledger has no lifecycle transition events")
    return state


def ledger_path_for(account: str, task_id: str) -> Path:
    """Resolve a per-task ledger path through the platform workspace chokepoint."""

    return resolve_user_path(account, _task_rel_path(task_id, LEDGER_FILENAME))


def index_path_for(account: str | None = None) -> Path:
    """Return the central task index path under the configured data root."""

    if account is not None:
        user_root = resolve_user_path(account, ".")
        data_root = user_root.parent.parent
    else:
        data_root = PlatformSettings.from_env().data_root
    return data_root / INDEX_DIRNAME / TASKS_INDEX_FILENAME


def _task_rel_path(task_id: str, filename: str) -> str:
    return f"tasks/{validate_task_id(task_id)}/{filename}"


def _next_seq(path: Path) -> int:
    if not path.exists():
        return 1
    seq = 0
    for event in _read_events(path):
        seq = event.seq
    return seq + 1


def _read_events(path: Path) -> Iterable[LedgerEvent]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc:
        raise MalformedLedger("ledger not found") from exc
    except OSError as exc:
        raise MalformedLedger("ledger cannot be read") from exc
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise TypeError("ledger row must be an object")
            yield LedgerEvent.from_json_dict(payload)
        except Exception as exc:
            raise MalformedLedger(f"malformed ledger row {line_number}") from exc


def _update_index(account: str, event: LedgerEvent) -> None:
    index_path = index_path_for(account)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    previous_state: object = None
    try:
        existing = []
        for payload in _read_index_payloads(index_path):
            if (
                payload.get("task_id") == event.task_id
                and payload.get("account_id_ref") == event.account_id_ref
            ):
                previous_state = payload.get("state")
                continue
            existing.append(payload)
    except MalformedLedger:
        existing = []

    state = event.payload.get("to_state")
    existing.append(
        {
            "task_id": event.task_id,
            "account_id_ref": event.account_id_ref,
            "seq": event.seq,
            "type": event.type.value,
            "state": state if isinstance(state, str) else previous_state,
            "updated_ts": event.ts,
        }
    )
    _atomic_write_jsonl(index_path, existing)


def _read_index_payloads(path: Path) -> tuple[dict[str, object], ...]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return ()
    except OSError as exc:
        raise MalformedLedger("index cannot be read") from exc
    rows: list[dict[str, object]] = []
    for line in lines:
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise MalformedLedger("index row must be an object")
        rows.append(payload)
    return tuple(rows)


def _atomic_write_jsonl(path: Path, rows: Iterable[dict[str, object]]) -> None:
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
            for row in rows:
                line = json.dumps(row, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
                json.loads(line)
                handle.write(line)
                handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temp_path = Path(temp_name)
        os.replace(temp_path, path)
        temp_name = None
        path.chmod(0o600)
    finally:
        if temp_name is not None:
            try:
                Path(temp_name).unlink()
            except OSError:
                pass


def _discover_single_ledger_path(task_id: str) -> Path:
    data_root = PlatformSettings.from_env().data_root
    users_root = data_root / "users"
    if not users_root.exists():
        raise MalformedLedger("ledger not found")
    matches = sorted(users_root.glob(f"*/tasks/{validate_task_id(task_id)}/{LEDGER_FILENAME}"))
    if not matches:
        raise MalformedLedger("ledger not found")
    if len(matches) > 1:
        raise MalformedLedger("task_id is not unique across accounts; pass account")
    return matches[0]


__all__ = [
    "INDEX_DIRNAME",
    "LEDGER_FILENAME",
    "TASKS_INDEX_FILENAME",
    "IllegalLedgerTransition",
    "LedgerError",
    "LedgerReplayError",
    "MalformedLedger",
    "append_event",
    "index_path_for",
    "ledger_path_for",
    "replay",
    "replay_path",
]

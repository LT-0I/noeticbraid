"""Append-only JSONL ledger for SP-E runtime events."""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
from typing import Any

from .errors import LedgerError
from .redaction import redact_value

REQUIRED_LEDGER_FIELDS = ("ts", "run_id", "workflow_id", "event_type", "status", "step_id", "runrecord_event_type")
OUTBOUND_LEVEL_TO_EVENT_TYPE = {
    "silent_record": "artifact_created",
    "low_priority": "routing_advice_recorded",
    "normal": "approval_requested",
    "requires_confirmation": "approval_requested",
    "urgent_interrupt": "approval_requested",
}
RUNRECORD_EVENT_TYPE_MAPPING = {
    "run_pending": "routing_advice_recorded",
    "run_started": "routing_advice_recorded",
    "step_started": "routing_advice_recorded",
    "step_completed": "artifact_created",
    "step_blocked": "approval_requested",
    "step_failed": "task_failed",
    "outbound_notify": "approval_requested",
    "run_finished": "task_completed",
    "run_failed": "task_failed",
    "security_violation": "security_violation",
}


class RunLedgerWriter:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def write(
        self,
        *,
        run_id: str,
        workflow_id: str,
        event_type: str,
        status: str,
        step_id: str | None = None,
        **extra: Any,
    ) -> int:
        event = build_event(
            run_id=run_id,
            workflow_id=workflow_id,
            event_type=event_type,
            status=status,
            step_id=step_id,
            extra=extra,
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self.path.open("a", encoding="utf-8") as handle:
                json.dump(event, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
        except OSError as exc:
            raise LedgerError("ledger event could not be written") from exc
        return 1

    def find_run(self, run_id: str) -> dict[str, Any] | None:
        """Return a cached run summary when run_id already has a run_started event."""

        if not self.path.exists():
            return None
        records = [record for record in read_jsonl(self.path) if record.get("run_id") == run_id]
        if not any(record.get("event_type") == "run_started" for record in records):
            return None
        workflow_id = next((str(record.get("workflow_id")) for record in records if record.get("workflow_id")), "")
        terminal = next(
            (
                record
                for record in reversed(records)
                if record.get("event_type") in {"run_failed", "run_finished"}
                or record.get("status") in {"failed", "blocked", "completed"}
            ),
            records[-1],
        )
        dry_run = any(bool(record.get("dry_run")) for record in records)
        return {
            "run_id": run_id,
            "workflow_id": workflow_id,
            "status": str(terminal.get("status", "running")),
            "dry_run": dry_run,
            "events_written": 0,
            "state_updated": False,
        }


def build_event(
    *,
    run_id: str,
    workflow_id: str,
    event_type: str,
    status: str,
    step_id: str | None,
    extra: dict[str, Any],
) -> dict[str, Any]:
    if event_type == "telegram_notify":
        raise LedgerError("telegram_notify is not a neutral SP-E event name")
    if event_type not in RUNRECORD_EVENT_TYPE_MAPPING:
        raise LedgerError(f"unsupported scheduler event_type: {event_type}")
    runrecord_event_type = RUNRECORD_EVENT_TYPE_MAPPING[event_type]
    if event_type == "outbound_notify":
        level = extra.get("level")
        if isinstance(level, str):
            runrecord_event_type = OUTBOUND_LEVEL_TO_EVENT_TYPE.get(level, runrecord_event_type)
    event = {
        "ts": dt.datetime.now(tz=dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "run_id": run_id,
        "workflow_id": workflow_id,
        "event_type": event_type,
        "status": status,
        "step_id": step_id,
        "runrecord_event_type": runrecord_event_type,
    }
    event.update(extra)
    return redact_value(event)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise LedgerError("ledger file could not be read") from exc
    return [json.loads(line) for line in text.splitlines() if line.strip()]

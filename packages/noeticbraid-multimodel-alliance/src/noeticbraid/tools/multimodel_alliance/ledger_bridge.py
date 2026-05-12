"""RunRecord-compatible ledger bridge for SDD-D2-01 debate loops.

This module does not import or mutate the frozen RunRecord enum. It writes
RunRecord-shaped JSONL using only event types already present in contract 1.2.0.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .candidate_store import SDD_ID, assert_safe_output_root

ALLOWED_DEBATE_LOOP_EVENT_TYPES = frozenset(
    {"artifact_created", "routing_advice_recorded", "lesson_candidate_created"}
)
LEDGER_RELATIVE_PATH = Path("state") / "ledger" / "run_ledger.jsonl"


class LedgerBridgeError(ValueError):
    """Raised when ledger evidence would leave D2-01's frozen event boundary."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ledger_jsonl_path(state_root: str | Path) -> Path:
    return assert_safe_output_root(state_root) / LEDGER_RELATIVE_PATH


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _validate_event_type(event_type: str) -> None:
    if event_type not in ALLOWED_DEBATE_LOOP_EVENT_TYPES:
        raise LedgerBridgeError(f"event_type not allowed for D2-01 bridge: {event_type}")


def build_run_record(
    *,
    run_id: str,
    task_id: str,
    event_type: str,
    model_refs: list[str] | None = None,
    source_refs: list[str] | None = None,
    artifact_refs: list[str] | None = None,
    routing_advice: str | None = None,
    actor: str = "system",
    status: str = "recorded",
    created_at: str | None = None,
) -> dict[str, Any]:
    """Build a compact RunRecord-shaped dict without adding event types."""

    _validate_event_type(event_type)
    if not run_id.startswith("run_"):
        raise LedgerBridgeError("run_id must use run_* prefix")
    if not task_id.startswith("task_"):
        raise LedgerBridgeError("task_id must use task_* prefix")
    if actor not in {"user", "system", "model", "local_review"}:
        raise LedgerBridgeError("actor is outside frozen RunRecord actor enum")
    if status not in {"draft", "recorded", "failed"}:
        raise LedgerBridgeError("status is outside frozen RunRecord status enum")
    record = {
        "run_id": run_id,
        "task_id": task_id,
        "event_type": event_type,
        "created_at": created_at or utc_now_iso(),
        "actor": actor,
        "model_refs": _dedupe(model_refs or []),
        "source_refs": _dedupe(source_refs or []),
        "artifact_refs": _dedupe(artifact_refs or []),
        "routing_advice": routing_advice,
        "status": status,
    }
    return record


def build_debate_loop_ledger_records(
    *,
    run_id: str,
    task_id: str,
    route_id: str,
    debate_id: str,
    convergence_id: str,
    candidate_ids: list[str],
    model_refs: list[str],
    source_refs: list[str],
    artifact_refs: list[str],
    provider_mode: str,
    decision_status: str,
    blocked_decision_count: int,
    created_at: str | None = None,
) -> list[dict[str, Any]]:
    """Return the three ledger events D2-01 is allowed to emit."""

    metadata = {
        "sdd_id": SDD_ID,
        "task_id": task_id,
        "route_id": route_id,
        "debate_id": debate_id,
        "convergence_id": convergence_id,
        "candidate_ids": candidate_ids,
        "provider_mode": provider_mode,
        "decision_status": decision_status,
        "blocked_decision_count": blocked_decision_count,
    }
    advice = json.dumps(metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    timestamp = created_at or utc_now_iso()
    return [
        build_run_record(
            run_id=run_id,
            task_id=task_id,
            event_type="artifact_created",
            model_refs=model_refs,
            source_refs=source_refs,
            artifact_refs=artifact_refs,
            routing_advice=f"{SDD_ID} debate-loop artifacts created",
            created_at=timestamp,
        ),
        build_run_record(
            run_id=run_id,
            task_id=task_id,
            event_type="routing_advice_recorded",
            model_refs=model_refs,
            source_refs=source_refs,
            artifact_refs=artifact_refs,
            routing_advice=advice,
            created_at=timestamp,
        ),
        build_run_record(
            run_id=run_id,
            task_id=task_id,
            event_type="lesson_candidate_created",
            model_refs=model_refs,
            source_refs=source_refs,
            artifact_refs=artifact_refs,
            routing_advice=advice,
            created_at=timestamp,
        ),
    ]


def append_ledger_records(state_root: str | Path, records: list[dict[str, Any]]) -> Path:
    """Append RunRecord-shaped records to state/ledger/run_ledger.jsonl."""

    path = ledger_jsonl_path(state_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for record in records:
            _validate_event_type(str(record.get("event_type")))
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            fh.write("\n")
    return path


def record_debate_loop_ledger(state_root: str | Path, **kwargs: Any) -> tuple[Path, list[dict[str, Any]]]:
    """Build and append D2-01 ledger evidence, returning path and records."""

    records = build_debate_loop_ledger_records(**kwargs)
    path = append_ledger_records(state_root, records)
    return path, records

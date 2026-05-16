# SPDX-License-Identifier: Apache-2.0
"""Typed C2 task ledger events built on the CV JSON schema substrate."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from noeticbraid_backend.omc_workspace.web_ai_hub_automation import redact_hub_response
from noeticbraid_backend.omc_workspace.web_ai_hub_client import sanitize_error_msg
from noeticbraid_backend.orchestration.approvals import classify_approval
from noeticbraid_backend.orchestration.ledger_schema import JsonValue
from noeticbraid_backend.platform.tasks.models import (
    ACCOUNT_REF_HEX_CHARS,
    ACCOUNT_REF_PREFIX,
    TaskState,
    account_ref_for,
    validate_task_id,
)

EventPayload = dict[str, JsonValue]
GovernanceDoorType = Literal["one-way", "two-way"]


class LedgerEventType(StrEnum):
    """C2 per-task ledger event types."""

    DISPATCH = "dispatch"
    AI_CALL = "ai_call"
    ARTIFACT_PRODUCED = "artifact_produced"
    CROSS_VALIDATION = "cross_validation"
    ERROR = "error"
    BLOCKED = "blocked"
    GOVERNANCE = "governance"


@dataclass(frozen=True, slots=True)
class LedgerEventDraft:
    """Event body before writer-owned envelope fields are assigned."""

    task_id: str
    type: LedgerEventType
    payload: EventPayload
    ts: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def __post_init__(self) -> None:
        validate_task_id(self.task_id)
        if not isinstance(self.type, LedgerEventType):
            object.__setattr__(self, "type", LedgerEventType(str(self.type)))
        _validate_json_payload(self.payload)
        if not isinstance(self.ts, str) or not self.ts:
            raise ValueError("ts must be a non-empty string")


@dataclass(frozen=True, slots=True)
class LedgerEvent:
    """Persisted replayable task ledger envelope."""

    ts: str
    task_id: str
    account_id_ref: str
    seq: int
    type: LedgerEventType
    payload: EventPayload

    def __post_init__(self) -> None:
        validate_task_id(self.task_id)
        if not isinstance(self.type, LedgerEventType):
            object.__setattr__(self, "type", LedgerEventType(str(self.type)))
        if not isinstance(self.seq, int) or self.seq < 1:
            raise ValueError("seq must be a positive integer")
        if not isinstance(self.ts, str) or not self.ts:
            raise ValueError("ts must be a non-empty string")
        _validate_account_ref(self.account_id_ref)
        _validate_json_payload(self.payload)

    def to_json_dict(self) -> dict[str, JsonValue]:
        """Return the compact JSONL envelope."""

        return {
            "ts": self.ts,
            "task_id": self.task_id,
            "account_id_ref": self.account_id_ref,
            "seq": self.seq,
            "type": self.type.value,
            "payload": self.payload,
        }

    @classmethod
    def from_json_dict(cls, payload: dict[str, Any]) -> "LedgerEvent":
        """Build a validated event from one JSONL object."""

        return cls(
            ts=str(payload["ts"]),
            task_id=str(payload["task_id"]),
            account_id_ref=str(payload["account_id_ref"]),
            seq=int(payload["seq"]),
            type=LedgerEventType(str(payload["type"])),
            payload=dict(payload["payload"]),
        )


# Backwards-friendly alias for callers that want to name the union explicitly.
TaskLedgerEvent = LedgerEvent


def make_enveloped_event(account: str, draft: LedgerEventDraft, seq: int) -> LedgerEvent:
    """Attach writer-owned envelope fields to a draft."""

    return LedgerEvent(
        ts=draft.ts,
        task_id=draft.task_id,
        account_id_ref=account_ref_for(account),
        seq=seq,
        type=draft.type,
        payload=draft.payload,
    )


def dispatch_event(
    task_id: str,
    *,
    to_state: TaskState | str,
    from_state: TaskState | str | None = None,
) -> LedgerEventDraft:
    """Create a lifecycle dispatch event without raw prompt material."""

    payload: EventPayload = {"to_state": TaskState(str(to_state)).value}
    if from_state is not None:
        payload["from_state"] = TaskState(str(from_state)).value
    return LedgerEventDraft(task_id=task_id, type=LedgerEventType.DISPATCH, payload=payload)


def ai_call_event(
    task_id: str,
    *,
    op: str,
    vendor: str,
    gate_status: str,
    redacted_payload: Any,
    prompt_text: str | None = None,
    to_state: TaskState | str | None = None,
) -> LedgerEventDraft:
    """Create an AI-call ledger event, forcing hub payload redaction at the boundary."""

    prompt = str(prompt_text) if prompt_text is not None else None
    safe_hub_payload = redact_hub_response(redacted_payload)
    if prompt:
        safe_hub_payload = _strip_prompt_text(safe_hub_payload, prompt)
    payload: EventPayload = {
        "op": _non_empty_string(op, "op"),
        "vendor": _non_empty_string(vendor, "vendor"),
        "gate_status": _non_empty_string(gate_status, "gate_status"),
        "redacted_payload": safe_hub_payload,
    }
    if prompt is not None:
        payload["prompt_sha256"] = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        payload["prompt_len"] = len(prompt)
    if to_state is not None:
        payload["to_state"] = TaskState(str(to_state)).value
    return LedgerEventDraft(task_id=task_id, type=LedgerEventType.AI_CALL, payload=payload)


def artifact_produced_event(
    task_id: str,
    *,
    modality: str,
    rel_path: str,
    sha256: str,
    bytes_count: int,
    to_state: TaskState | str | None = None,
) -> LedgerEventDraft:
    """Create an artifact-produced event with relative artifact evidence."""

    if len(sha256) != 64 or any(char not in "0123456789abcdef" for char in sha256.lower()):
        raise ValueError("sha256 must be a 64-character hex digest")
    if not isinstance(bytes_count, int) or bytes_count < 0:
        raise ValueError("bytes_count must be a non-negative integer")
    payload: EventPayload = {
        "modality": _non_empty_string(modality, "modality"),
        "rel_path": _safe_rel_path(rel_path),
        "sha256": sha256.lower(),
        "bytes": bytes_count,
    }
    if to_state is not None:
        payload["to_state"] = TaskState(str(to_state)).value
    return LedgerEventDraft(task_id=task_id, type=LedgerEventType.ARTIFACT_PRODUCED, payload=payload)


def cross_validation_event(
    task_id: str,
    *,
    checker: str,
    verdict: str,
    to_state: TaskState | str | None = None,
) -> LedgerEventDraft:
    """Create a cross-validation verdict event."""

    payload: EventPayload = {
        "checker": _non_empty_string(checker, "checker"),
        "verdict": _non_empty_string(verdict, "verdict"),
    }
    if to_state is not None:
        payload["to_state"] = TaskState(str(to_state)).value
    return LedgerEventDraft(task_id=task_id, type=LedgerEventType.CROSS_VALIDATION, payload=payload)


def error_event(
    task_id: str,
    *,
    reason: str,
    code: str | None = None,
    from_state: TaskState | str | None = None,
) -> LedgerEventDraft:
    """Create an error event with sanitized diagnostic text."""

    payload: EventPayload = {
        "reason": sanitize_error_msg(str(reason), max_chars=512) or "task error",
        "to_state": TaskState.ERROR.value,
    }
    if code:
        payload["code"] = sanitize_error_msg(str(code), max_chars=128) or "error"
    if from_state is not None:
        payload["from_state"] = TaskState(str(from_state)).value
    return LedgerEventDraft(task_id=task_id, type=LedgerEventType.ERROR, payload=payload)


def blocked_event(
    task_id: str,
    *,
    modality: str,
    reason: str,
) -> LedgerEventDraft:
    """Create a blocked terminal event."""

    return LedgerEventDraft(
        task_id=task_id,
        type=LedgerEventType.BLOCKED,
        payload={
            "modality": _non_empty_string(modality, "modality"),
            "reason": sanitize_error_msg(str(reason), max_chars=512) or "blocked",
            "to_state": TaskState.BLOCKED.value,
        },
    )


def governance_event(
    task_id: str,
    *,
    summary: str | None = None,
    question_id: str | None = None,
    skill: str | None = None,
    category: str | None = None,
) -> LedgerEventDraft:
    """Create a governance event classified through the CV approval classifier."""

    classification = classify_approval(
        question_id=question_id,
        skill=skill,
        category=category,
        summary=summary,
    )
    door_type: GovernanceDoorType = "one-way" if classification.one_way else "two-way"
    payload: EventPayload = {"door_type": door_type, "reason": classification.reason}
    if classification.matched:
        payload["matched"] = classification.matched
    if classification.definition_id:
        payload["definition_id"] = classification.definition_id
    return LedgerEventDraft(task_id=task_id, type=LedgerEventType.GOVERNANCE, payload=payload)


def event_to_json_line(event: LedgerEvent) -> str:
    """Serialize one ledger event as parse-valid compact JSONL."""

    line = json.dumps(event.to_json_dict(), ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    json.loads(line)
    return line


def _strip_prompt_text(value: JsonValue, prompt: str) -> JsonValue:
    if isinstance(value, str):
        return value.replace(prompt, "[prompt]")
    if isinstance(value, list):
        return [_strip_prompt_text(item, prompt) for item in value]
    if isinstance(value, dict):
        return {key: _strip_prompt_text(item, prompt) for key, item in value.items()}
    return value


def _validate_account_ref(value: str) -> None:
    if not isinstance(value, str) or not value.startswith(ACCOUNT_REF_PREFIX):
        raise ValueError("account_id_ref must be an opaque account reference")
    suffix = value[len(ACCOUNT_REF_PREFIX) :]
    if len(suffix) != ACCOUNT_REF_HEX_CHARS or any(char not in "0123456789abcdef" for char in suffix):
        raise ValueError("account_id_ref must use the expected short hash shape")


def _validate_json_payload(payload: EventPayload) -> None:
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")
    json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _non_empty_string(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _safe_rel_path(value: str) -> str:
    text = _non_empty_string(value, "rel_path")
    parts = text.replace("\\", "/").split("/")
    if text.startswith("/") or any(part in {"", ".", ".."} for part in parts):
        raise ValueError("rel_path must be a simple relative path without traversal")
    return text


__all__ = [
    "EventPayload",
    "GovernanceDoorType",
    "LedgerEvent",
    "LedgerEventDraft",
    "LedgerEventType",
    "TaskLedgerEvent",
    "ai_call_event",
    "artifact_produced_event",
    "blocked_event",
    "cross_validation_event",
    "dispatch_event",
    "error_event",
    "event_to_json_line",
    "governance_event",
    "make_enveloped_event",
]

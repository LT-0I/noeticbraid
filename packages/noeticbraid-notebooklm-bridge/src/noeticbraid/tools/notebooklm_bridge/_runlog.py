"""RunRecord 1.0.0-compatible observability helpers with redaction."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from ._serializer import utc_now_iso
from ._types import OperationEvent

_LOGGER = logging.getLogger("noeticbraid.notebooklm_bridge")
SENSITIVE_KEY_RE = re.compile(r"(cookie|credential|secret|token|password|authorization|auth(_|$)|browser_state)", re.I)
BEARER_RE = re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]+", re.I)
COOKIE_PAIR_RE = re.compile(r"(?i)(cookie\s*[:=]\s*)[^;\n]+")
GOOGLE_API_KEY_RE = re.compile(r"AIza[0-9A-Za-z_-]{20,}")


def redact_str(text: str) -> str:
    """Redact common token/cookie/key patterns from caller-facing text."""

    cleaned = BEARER_RE.sub("Bearer [REDACTED]", text)
    cleaned = COOKIE_PAIR_RE.sub(r"\1[REDACTED]", cleaned)
    return GOOGLE_API_KEY_RE.sub("[REDACTED_GOOGLE_API_KEY]", cleaned)


def redact(value: Any, *, key: str | None = None) -> Any:
    """Recursively redact common secret fields and token-like values."""

    if key and SENSITIVE_KEY_RE.search(key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): redact(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item) for item in value)
    if isinstance(value, str):
        return redact_str(value)
    return value


def build_event(event: OperationEvent) -> dict[str, Any]:
    """Build a strict RunRecord-compatible dict.

    No new event enum is introduced. Success events map to existing generic
    ledger categories; failures map to ``task_failed``. Artifact references are
    strings matching ``artifact_[A-Za-z0-9_]+``.
    """

    event_type = _event_type_for(event)
    payload: dict[str, Any] = {
        "run_id": _contract_id("run", event.run_id or f"notebooklm_{event.operation}"),
        "task_id": _contract_id("task", event.task_id or f"notebooklm_{event.operation}"),
        "event_type": event_type,
        "created_at": utc_now_iso(),
        "actor": "system",
        "model_refs": [],
        "source_refs": [_contract_id("source", ref) for ref in event.source_refs],
        "artifact_refs": [_contract_id("artifact", ref) for ref in (event.artifact_refs or [_notebook_artifact(event.notebook_id)])],
        "routing_advice": _routing_advice(event),
        "status": "failed" if event.status == "failed" else "recorded",
    }
    return payload


def emit_event(session: object, event: OperationEvent) -> dict[str, Any]:
    payload = build_event(event)
    safe_payload = redact(payload)
    for method_name in ("emit_event", "record_event", "log_event"):
        method = getattr(session, method_name, None)
        if callable(method):
            method(safe_payload)
            return safe_payload
    _LOGGER.info("notebooklm_bridge_event %s", json.dumps(safe_payload, sort_keys=True, ensure_ascii=False))
    return safe_payload


def _event_type_for(event: OperationEvent) -> str:
    if event.status == "failed":
        return "task_failed"
    if event.status == "started":
        return "task_created"
    if event.operation == "push_sources":
        return "source_record_linked"
    if event.operation in {"pull_briefing", "pull_faq"}:
        return "artifact_created"
    return "task_completed"


def _routing_advice(event: OperationEvent) -> str | None:
    if event.routing_advice:
        return str(redact(event.routing_advice))[:4096]
    if event.message:
        return str(redact(event.message))[:4096]
    return None


def _notebook_artifact(notebook_id: str) -> str:
    return f"notebooklm_{notebook_id}"


def _contract_id(prefix: str, value: str) -> str:
    if re.fullmatch(rf"{prefix}_[A-Za-z0-9_]+", value):
        return value[:128]
    slug = re.sub(r"[^A-Za-z0-9_]+", "_", value.strip())
    slug = re.sub(r"_+", "_", slug).strip("_") or "item"
    return f"{prefix}_{slug}"[:128]

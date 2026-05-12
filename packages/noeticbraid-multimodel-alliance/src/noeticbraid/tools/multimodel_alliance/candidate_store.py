"""Program-memory candidate JSONL store for SDD-D2-01 debate loops.

The store is intentionally candidate-only. It never writes confirmed memory,
raw user notes, frozen contracts, or provider transcripts.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .validator import ValidationError, require_prefix, scan_private_markers

SDD_ID = "SDD-D2-01"
CANDIDATE_TYPE = "program_memory_debate_lesson"
CANDIDATE_RELATIVE_PATH = Path("state") / "program_memory" / "candidates" / "multimodel_debate_candidates.jsonl"
UPGRADE_RULE = (
    "explicit user adoption OR reuse >=3 times with at least one independently "
    "checkable ledger run; not rejected is never sufficient"
)

_BLOCKED_PATH_PARTS = {
    "raw_note",
    "raw_notes",
    "raw-notes",
    "original_note",
    "original_notes",
    "original-notes",
    "confirmed",
    "confirmed_memory",
    "confirmed-memory",
    "frozen",
    "frozen_contracts",
    "frozen-contracts",
    "contract",
    "contracts",
    "vault",
    "obsidian",
}
_PRIVATE_ABSOLUTE_PATH = re.compile(r"(^/home/|^/users/|^/root/|^[a-z]:\\)", re.IGNORECASE)
_REQUIRED_KEYS = {
    "candidate_id",
    "candidate_type",
    "sdd_id",
    "task_id",
    "route_id",
    "debate_id",
    "convergence_id",
    "summary",
    "source_refs",
    "artifact_refs",
    "model_refs",
    "decision_status",
    "upgrade_rule",
    "status",
    "created_at",
}
_TRANSCRIPT_KEYS = {"raw_transcript", "provider_transcript", "full_transcript", "raw_provider_output", "raw_user_note"}


class CandidateStoreError(ValueError):
    """Raised when a candidate write would violate D2-01 boundaries."""


def utc_now_iso() -> str:
    """Return a compact UTC timestamp suitable for append-only JSONL records."""

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stable_candidate_id(task_id: str, route_id: str, debate_id: str, convergence_id: str) -> str:
    """Return a deterministic `memory_*` id for one debate-loop candidate."""

    base = task_id.removeprefix("task_")
    slug = re.sub(r"[^A-Za-z0-9_]+", "_", base).strip("_") or "debate_loop"
    candidate = f"memory_{slug}_debate_loop"
    if len(candidate) <= 128:
        return candidate
    digest = hashlib.sha256(f"{task_id}|{route_id}|{debate_id}|{convergence_id}".encode("utf-8")).hexdigest()[:12]
    return f"memory_{slug[:107].rstrip('_')}_{digest}"


def candidate_jsonl_path(state_root: str | Path) -> Path:
    """Return the module-local program-memory candidate JSONL path."""

    root = assert_safe_output_root(state_root)
    return root / CANDIDATE_RELATIVE_PATH


def assert_safe_output_root(root: str | Path) -> Path:
    """Reject roots that look like raw-note, confirmed, frozen, or vault zones."""

    resolved = Path(root).expanduser().resolve()
    lowered_parts = {part.lower() for part in resolved.parts}
    blocked = lowered_parts & _BLOCKED_PATH_PARTS
    if blocked:
        raise CandidateStoreError(f"blocked output path inside protected zone: {resolved}")
    return resolved


def scan_forbidden_material(value: Any, context: str = "candidate") -> None:
    """Reject private markers, host-private absolute paths, and transcript fields."""

    try:
        scan_private_markers(value, context)
    except ValidationError as exc:
        raise CandidateStoreError(str(exc)) from exc

    def walk(item: Any, item_context: str) -> None:
        if isinstance(item, str):
            if _PRIVATE_ABSOLUTE_PATH.search(item):
                raise CandidateStoreError(f"forbidden host-private absolute path in {item_context}")
        elif isinstance(item, list):
            for index, child in enumerate(item):
                walk(child, f"{item_context}[{index}]")
        elif isinstance(item, dict):
            for key, child in item.items():
                key_text = str(key)
                if key_text.lower() in _TRANSCRIPT_KEYS:
                    raise CandidateStoreError(f"raw transcript field is forbidden in {item_context}.{key_text}")
                walk(key_text, f"{item_context}.key")
                walk(child, f"{item_context}.{key_text}")

    walk(value, context)


def _require_ref_list(record: dict[str, Any], field: str, prefix_name: str) -> None:
    values = record.get(field)
    if not isinstance(values, list):
        raise CandidateStoreError(f"candidate.{field} must be a list")
    for value in values:
        try:
            require_prefix(value, prefix_name, f"candidate.{field}")
        except ValidationError as exc:
            raise CandidateStoreError(str(exc)) from exc


def validate_candidate_record(record: dict[str, Any]) -> None:
    """Validate the candidate-only JSONL payload required by D2-01."""

    missing = sorted(_REQUIRED_KEYS - set(record))
    if missing:
        raise CandidateStoreError(f"candidate missing required keys: {', '.join(missing)}")
    if record.get("candidate_type") != CANDIDATE_TYPE:
        raise CandidateStoreError("candidate_type must be program_memory_debate_lesson")
    if record.get("sdd_id") != SDD_ID:
        raise CandidateStoreError("candidate.sdd_id must be SDD-D2-01")
    if record.get("status") != "candidate":
        raise CandidateStoreError("D2-01 candidate store refuses non-candidate status")
    if record.get("decision_status") not in {"accepted", "needs_user_decision", "needs_more_evidence", "rejected"}:
        raise CandidateStoreError("candidate.decision_status is unknown")
    if record.get("upgrade_rule") != UPGRADE_RULE:
        raise CandidateStoreError("candidate.upgrade_rule must encode the R-6 gate")
    if not isinstance(record.get("summary"), str) or not record["summary"].strip():
        raise CandidateStoreError("candidate.summary is required")
    if len(record["summary"]) > 2048:
        raise CandidateStoreError("candidate.summary is too long for a concise evidence-backed lesson")

    candidate_id = record.get("candidate_id")
    if not isinstance(candidate_id, str) or not re.fullmatch(r"memory_[A-Za-z0-9_]+", candidate_id):
        raise CandidateStoreError("candidate.candidate_id must match memory_*")

    for field, prefix in (
        ("task_id", "task_id"),
        ("route_id", "route_id"),
        ("debate_id", "debate_id"),
        ("convergence_id", "convergence_id"),
    ):
        try:
            require_prefix(record.get(field), prefix, f"candidate.{field}")
        except ValidationError as exc:
            raise CandidateStoreError(str(exc)) from exc
    _require_ref_list(record, "source_refs", "source_ref")
    _require_ref_list(record, "artifact_refs", "artifact_ref")
    _require_ref_list(record, "model_refs", "model_ref")
    if not record["source_refs"] or not record["artifact_refs"] or not record["model_refs"]:
        raise CandidateStoreError("candidate must preserve source, artifact, and model refs")
    scan_forbidden_material(record, "candidate")


def build_debate_candidate(
    *,
    task_id: str,
    route_id: str,
    debate_id: str,
    convergence_id: str,
    summary: str,
    source_refs: list[str],
    artifact_refs: list[str],
    model_refs: list[str],
    decision_status: str,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Create a D2-01 program-memory candidate record without writing it."""

    record: dict[str, Any] = {
        "candidate_id": stable_candidate_id(task_id, route_id, debate_id, convergence_id),
        "candidate_type": CANDIDATE_TYPE,
        "sdd_id": SDD_ID,
        "task_id": task_id,
        "route_id": route_id,
        "debate_id": debate_id,
        "convergence_id": convergence_id,
        "summary": summary,
        "source_refs": list(dict.fromkeys(source_refs)),
        "artifact_refs": list(dict.fromkeys(artifact_refs)),
        "model_refs": list(dict.fromkeys(model_refs)),
        "decision_status": decision_status,
        "upgrade_rule": UPGRADE_RULE,
        "status": "candidate",
        "created_at": created_at or utc_now_iso(),
    }
    validate_candidate_record(record)
    return record


def append_candidate_record(state_root: str | Path, record: dict[str, Any]) -> Path:
    """Append a validated candidate record to the module-local JSONL store."""

    validate_candidate_record(record)
    path = candidate_jsonl_path(state_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        fh.write("\n")
    return path

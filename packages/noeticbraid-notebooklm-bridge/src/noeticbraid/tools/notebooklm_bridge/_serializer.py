"""Strict SourceRecord 1.0.0 serialization helpers."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

from ._errors import NotebookLMInputError, NotebookLMSerializationError

_VALID_SOURCE_TYPES = {"user_note", "web_page", "github_repo", "paper", "patent", "video", "ai_output", "paid_database"}
_VALID_QUALITY = {"low", "medium", "high", "unknown"}
_VALID_RELEVANCE = {"low", "medium", "high", "unknown"}
_VALID_EVIDENCE_ROLES = {"user_context", "reference_project", "source_grounding", "contradiction", "memory_update_evidence"}
_VALID_PURPOSES = {"project_positioning", "constraint_extraction", "source_grounding", "prior_art_check", "other"}


def to_source_records(notebook_id: str, briefing_text: str, run_id: str) -> list[dict]:
    """Serialize NotebookLM generated text into strict SourceRecord dictionaries.

    The returned dict uses only properties allowed by the frozen Phase 1.2
    SourceRecord schema (`additionalProperties: false`). The generated text body
    itself is represented by its content hash; callers that need full text should
    persist it as an artifact and link that artifact through RunRecord.
    """

    notebook_id = _require_non_empty("notebook_id", notebook_id)
    briefing_text = _require_non_empty("briefing_text", briefing_text)
    run_id = _normalize_contract_id("run", _require_non_empty("run_id", run_id))
    digest = hashlib.sha256(f"{notebook_id}\0{run_id}\0{briefing_text}".encode("utf-8")).hexdigest()
    content_hash = hashlib.sha256(briefing_text.encode("utf-8")).hexdigest()
    record = {
        "source_ref_id": f"source_notebooklm_briefing_{digest[:24]}",
        "source_type": _validate_enum("source_type", "ai_output", _VALID_SOURCE_TYPES),
        "title": "NotebookLM Briefing Doc",
        "local_path": f"notebooklm://notebook/{_slug(notebook_id)}/briefing/{digest[:12]}",
        "author": "google-notebooklm",
        "captured_at": utc_now_iso(),
        "retrieved_by_run_id": run_id,
        "content_hash": f"sha256:{content_hash}",
        "source_fingerprint": f"fingerprint_notebooklm_{digest[24:48]}",
        "quality_score": _validate_enum("quality_score", "unknown", _VALID_QUALITY),
        "relevance_score": _validate_enum("relevance_score", "unknown", _VALID_RELEVANCE),
        "evidence_role": _validate_enum("evidence_role", "source_grounding", _VALID_EVIDENCE_ROLES),
        "used_for_purpose": _validate_enum("used_for_purpose", "source_grounding", _VALID_PURPOSES),
    }
    return [record]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _require_non_empty(name: str, value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise NotebookLMInputError(f"{name} must be a non-empty string.")
    return value.strip()


def _validate_enum(name: str, value: str, allowed: set[str]) -> str:
    if value not in allowed:
        raise NotebookLMSerializationError(
            f"SourceRecord field '{name}' got invalid enum value '{value}'. Allowed: {sorted(allowed)}"
        )
    return value


def _normalize_contract_id(prefix: str, value: str) -> str:
    if re.fullmatch(rf"{re.escape(prefix)}_[A-Za-z0-9_]+", value):
        return value[:128]
    return f"{prefix}_{_slug(value)}"[:128]


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_]+", "_", value.strip())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "item"

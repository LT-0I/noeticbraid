"""Schema objects for the user-growth LLMwiki mirror module.

The models in this module are intentionally local to
``noeticbraid_core.user_growth_llmwiki``. They are not OpenAPI additions and do
not modify the frozen Phase 1.2 schemas.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import PurePosixPath
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from noeticbraid_core.schemas._common import (
    COMMON_MODEL_CONFIG,
    ensure_optional_utc_datetime,
    ensure_utc_datetime,
    utc_now,
)

ContentLayer = Literal["raw", "source", "compiled", "wiki", "output", "log"]
Confidence = Literal["low", "medium", "high"]
CandidateStatus = Literal[
    "candidate",
    "open",
    "recorded",
    "accepted",
    "rejected",
    "modified",
    "superseded",
]
Severity = Literal["info", "light", "strong"]
NoteType = Literal["fact", "hypothesis", "challenge", "action"]
ReportPeriod = Literal["daily", "weekly", "monthly"]

CONTENT_HASH_RE = re.compile(r"^sha256:[A-Fa-f0-9]{64}$")
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_]+$")


def normalize_relative_path(value: str, *, allow_dot: bool = True, directory: bool = False) -> str:
    """Normalize a repository/vault-relative path without exposing host paths."""

    if not isinstance(value, str):
        raise TypeError("path must be a string")
    raw = value.strip().replace("\\", "/")
    if not raw:
        if allow_dot:
            return "."
        raise ValueError("path must not be empty")
    if raw.startswith("/") or re.match(r"^[A-Za-z]:/", raw):
        raise ValueError("path must be relative, not absolute")
    if "\x00" in raw:
        raise ValueError("path must not contain NUL bytes")
    posix = PurePosixPath(raw)
    if any(part in ("..", "") for part in posix.parts):
        raise ValueError("path must not contain empty or parent-directory segments")
    normalized = str(posix)
    if normalized == "." and not allow_dot:
        raise ValueError("path must not be '.'")
    if directory and normalized != "." and not normalized.endswith("/"):
        normalized += "/"
    return normalized


def normalize_content_hash(value: str) -> str:
    """Validate and normalize a sha256-prefixed content hash."""

    if not isinstance(value, str) or not CONTENT_HASH_RE.fullmatch(value):
        raise ValueError("content_hash must match sha256:<64 hex chars>")
    return value.lower()


def stable_hash(parts: list[str] | tuple[str, ...]) -> str:
    """Return a deterministic SHA-256 digest over string parts."""

    h = hashlib.sha256()
    for part in parts:
        h.update(part.encode("utf-8"))
        h.update(b"\0")
    return h.hexdigest()


def stable_id(prefix: str, *parts: object, length: int = 16) -> str:
    """Build a deterministic prefixed identifier from stable parts."""

    if not prefix.endswith("_"):
        raise ValueError("prefix must end with '_'")
    digest = stable_hash(tuple(str(part) for part in parts))[:length]
    return f"{prefix}{digest}"


def profile_source_ref(vault_root_hash: str) -> str:
    """Return a deterministic source ref for a VaultProfile snapshot."""

    normalized = normalize_content_hash(vault_root_hash)
    return f"source_vaultprofile_{normalized.removeprefix('sha256:')[:16]}"


def deterministic_json(data: Any) -> str:
    """Serialize JSON deterministically for review packets and tests."""

    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class RiskFlag(BaseModel):
    """Structured scanner or lint risk; warnings are data, not prose only."""

    model_config = COMMON_MODEL_CONFIG

    code: str = Field(..., min_length=1, max_length=128, pattern=r"^[a-z0-9_]+$")
    path: str = Field(..., min_length=1, max_length=1024)
    severity: Severity = Field(...)
    rationale: str = Field(..., min_length=1, max_length=1024)
    evidence_paths: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("path")
    @classmethod
    def _normalize_path(cls, value: str) -> str:
        return normalize_relative_path(value)

    @field_validator("evidence_paths")
    @classmethod
    def _normalize_evidence_paths(cls, values: list[str]) -> list[str]:
        return [normalize_relative_path(value) for value in values]


class FolderSummary(BaseModel):
    """Small read-only summary for one vault folder."""

    model_config = COMMON_MODEL_CONFIG

    path: str = Field(..., min_length=1, max_length=1024)
    depth: int = Field(..., ge=0)
    markdown_count: int = Field(..., ge=0)
    has_index: bool = Field(...)
    is_empty: bool = Field(...)

    @field_validator("path")
    @classmethod
    def _normalize_folder_path(cls, value: str) -> str:
        return normalize_relative_path(value, directory=value != ".")


class LinkHint(BaseModel):
    """A link edge detected without interpreting the linked note as fact."""

    model_config = COMMON_MODEL_CONFIG

    source_path: str = Field(..., min_length=1, max_length=1024)
    target: str = Field(..., min_length=1, max_length=1024)
    link_kind: Literal["wikilink", "markdown"] = Field(...)

    @field_validator("source_path")
    @classmethod
    def _normalize_source_path(cls, value: str) -> str:
        return normalize_relative_path(value, allow_dot=False)

    @field_validator("target")
    @classmethod
    def _normalize_target(cls, value: str) -> str:
        cleaned = value.strip().replace("\\", "/")
        if not cleaned:
            raise ValueError("target must not be empty")
        if cleaned.startswith(("http://", "https://", "mailto:")):
            return cleaned
        return normalize_relative_path(cleaned, allow_dot=False)


class NoteSummary(BaseModel):
    """Metadata-only summary of one Markdown note."""

    model_config = COMMON_MODEL_CONFIG

    path: str = Field(..., min_length=1, max_length=1024)
    has_frontmatter: bool = Field(...)
    frontmatter_keys: list[str] = Field(default_factory=list, max_length=100)
    note_type: Literal[
        "daily",
        "project",
        "source",
        "meeting",
        "idea",
        "artifact",
        "ai_observation",
        "report",
        "digestion",
        "unknown",
    ] = Field(...)
    owner_hint: Literal["user", "noeticbraid", "unknown"] = Field(default="unknown")
    zone_hint: Literal["raw_user", "ai_allowed", "unknown"] = Field(default="unknown")
    outgoing_link_count: int = Field(default=0, ge=0)
    incoming_link_count: int = Field(default=0, ge=0)

    @field_validator("path")
    @classmethod
    def _normalize_note_path(cls, value: str) -> str:
        return normalize_relative_path(value, allow_dot=False)

    @field_validator("frontmatter_keys")
    @classmethod
    def _validate_frontmatter_keys(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            key = str(value).strip()
            if not key or len(key) > 128:
                raise ValueError("frontmatter key must be 1-128 characters")
            if key not in seen:
                normalized.append(key)
                seen.add(key)
        return normalized


class DuplicateTopicName(BaseModel):
    """Folders that normalize to the same topic-ish name."""

    model_config = COMMON_MODEL_CONFIG

    normalized_name: str = Field(..., min_length=1, max_length=128)
    paths: list[str] = Field(..., min_length=2, max_length=50)

    @field_validator("paths")
    @classmethod
    def _normalize_paths(cls, values: list[str]) -> list[str]:
        return [normalize_relative_path(value, directory=True) for value in values]


class OrphanCluster(BaseModel):
    """A likely cluster of weakly linked notes under one folder."""

    model_config = COMMON_MODEL_CONFIG

    topic: str = Field(..., min_length=1, max_length=128)
    path: str = Field(..., min_length=1, max_length=1024)
    note_count: int = Field(..., ge=2)
    evidence_paths: list[str] = Field(..., min_length=2, max_length=100)

    @field_validator("path")
    @classmethod
    def _normalize_path(cls, value: str) -> str:
        return normalize_relative_path(value, directory=True)

    @field_validator("evidence_paths")
    @classmethod
    def _normalize_evidence_paths(cls, values: list[str]) -> list[str]:
        return [normalize_relative_path(value, allow_dot=False) for value in values]


class VaultProfile(BaseModel):
    """Read-only structural image of an Obsidian-style vault."""

    model_config = COMMON_MODEL_CONFIG

    vault_root_hash: str = Field(..., description="sha256 of the relative vault shape, not host path")
    scanned_at: datetime = Field(default_factory=utc_now)
    folder_summary: list[FolderSummary] = Field(default_factory=list)
    note_summaries: list[NoteSummary] = Field(default_factory=list)
    note_type_summary: dict[str, int] = Field(default_factory=dict)
    raw_user_zones: list[str] = Field(default_factory=list)
    ai_allowed_zones: list[str] = Field(default_factory=list)
    missing_indexes: list[str] = Field(default_factory=list)
    duplicate_topic_names: list[DuplicateTopicName] = Field(default_factory=list)
    orphan_clusters: list[OrphanCluster] = Field(default_factory=list)
    link_hints: list[LinkHint] = Field(default_factory=list)
    risk_flags: list[RiskFlag] = Field(default_factory=list)

    @field_validator("vault_root_hash")
    @classmethod
    def _normalize_vault_root_hash(cls, value: str) -> str:
        return normalize_content_hash(value)

    @field_validator("scanned_at")
    @classmethod
    def _ensure_scanned_at_utc(cls, value: datetime) -> datetime:
        return ensure_utc_datetime(value)

    @field_validator("raw_user_zones", "ai_allowed_zones")
    @classmethod
    def _normalize_zone_paths(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            path = normalize_relative_path(value, directory=True)
            if path not in seen:
                normalized.append(path)
                seen.add(path)
        return normalized

    @field_validator("missing_indexes")
    @classmethod
    def _normalize_missing_indexes(cls, values: list[str]) -> list[str]:
        return [normalize_relative_path(value, allow_dot=False) for value in values]

    def to_deterministic_json(self) -> str:
        return deterministic_json(self.model_dump(mode="json"))

    def profile_source_ref(self) -> str:
        return profile_source_ref(self.vault_root_hash)


class LLMWikiSourceRecord(BaseModel):
    """Immutable source identity for the raw/source layer.

    The required shape is: record_id, origin, content_hash, layer, ingested_at.
    Additional fields are provenance-only and must not store raw note content.
    """

    model_config = COMMON_MODEL_CONFIG

    record_id: str = Field(..., min_length=1, max_length=128, pattern=r"^source_[A-Za-z0-9_]+$")
    origin: str = Field(..., min_length=1, max_length=2048)
    content_hash: str = Field(..., min_length=71, max_length=71)
    layer: ContentLayer = Field(...)
    ingested_at: datetime = Field(default_factory=utc_now)
    relative_path: Optional[str] = Field(default=None, max_length=1024)
    title: Optional[str] = Field(default=None, max_length=512)
    provenance: dict[str, str] = Field(default_factory=dict, max_length=50)
    owner: Literal["noeticbraid"] = Field(default="noeticbraid")

    @field_validator("content_hash")
    @classmethod
    def _normalize_content_hash(cls, value: str) -> str:
        return normalize_content_hash(value)

    @field_validator("layer")
    @classmethod
    def _source_layer_only(cls, value: ContentLayer) -> ContentLayer:
        if value not in ("raw", "source"):
            raise ValueError("LLMWikiSourceRecord layer must be raw/source")
        return value

    @field_validator("ingested_at")
    @classmethod
    def _ensure_ingested_at_utc(cls, value: datetime) -> datetime:
        return ensure_utc_datetime(value)

    @field_validator("relative_path", mode="before")
    @classmethod
    def _normalize_optional_relative_path(cls, value: object) -> object:
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return None
        return normalize_relative_path(str(value), allow_dot=False)

    @field_validator("origin")
    @classmethod
    def _protect_origin_from_host_paths(cls, value: str) -> str:
        origin = value.strip()
        if not origin:
            raise ValueError("origin must not be empty")
        if origin.startswith("/") or re.match(r"^[A-Za-z]:[\\/]", origin):
            raise ValueError("origin must not be an absolute machine-local path")
        if origin.startswith("file:"):
            file_part = origin.removeprefix("file:")
            normalize_relative_path(file_part, allow_dot=False)
        return origin

    @field_validator("provenance")
    @classmethod
    def _validate_provenance(cls, value: dict[str, str]) -> dict[str, str]:
        clean: dict[str, str] = {}
        for key, raw in value.items():
            if not SAFE_ID_RE.fullmatch(str(key)):
                raise ValueError("provenance keys must be conservative identifiers")
            text = str(raw)
            if len(text) > 512:
                raise ValueError("provenance values must be <=512 characters")
            clean[str(key)] = text
        return clean

    def layer_group(self) -> Literal["raw/source", "compiled/wiki", "output", "log"]:
        if self.layer in ("raw", "source"):
            return "raw/source"
        if self.layer in ("compiled", "wiki"):
            return "compiled/wiki"
        if self.layer == "output":
            return "output"
        return "log"


class LayerCandidate(BaseModel):
    """A candidate artifact for compiled/wiki or output layers."""

    model_config = COMMON_MODEL_CONFIG

    candidate_id: str = Field(..., min_length=1, max_length=128, pattern=r"^candidate_[A-Za-z0-9_]+$")
    layer: ContentLayer = Field(...)
    target_path: str = Field(..., min_length=1, max_length=1024)
    title: str = Field(..., min_length=1, max_length=512)
    source_refs: list[str] = Field(..., min_length=1, max_length=100)
    evidence_refs: list[str] = Field(..., min_length=1, max_length=100)
    rationale: str = Field(..., min_length=1, max_length=2048)
    status: CandidateStatus = Field(default="candidate")
    owner: Literal["noeticbraid"] = Field(default="noeticbraid")
    created_at: datetime = Field(default_factory=utc_now)
    confidence: Confidence = Field(default="medium")

    @field_validator("layer")
    @classmethod
    def _candidate_layer(cls, value: ContentLayer) -> ContentLayer:
        if value not in ("compiled", "wiki", "output"):
            raise ValueError("LayerCandidate must be in compiled/wiki or output layer")
        return value

    @field_validator("target_path")
    @classmethod
    def _normalize_target_path(cls, value: str) -> str:
        return normalize_relative_path(value, allow_dot=False)

    @field_validator("source_refs")
    @classmethod
    def _validate_source_refs(cls, values: list[str]) -> list[str]:
        seen: set[str] = set()
        for value in values:
            if not re.fullmatch(r"^source_[A-Za-z0-9_]+$", value):
                raise ValueError("source_refs must use source_ identifiers")
            if value in seen:
                raise ValueError("source_refs must not contain duplicates")
            seen.add(value)
        return values

    @field_validator("evidence_refs")
    @classmethod
    def _validate_evidence_refs(cls, values: list[str]) -> list[str]:
        if not values:
            raise ValueError("evidence_refs must be non-empty")
        return [str(value).strip() for value in values]

    @field_validator("created_at")
    @classmethod
    def _ensure_created_at_utc(cls, value: datetime) -> datetime:
        return ensure_utc_datetime(value)


class ActivityLogRecord(BaseModel):
    """Append-only log record describing ingestion, compilation, output, or audit activity."""

    model_config = COMMON_MODEL_CONFIG

    event_id: str = Field(..., min_length=1, max_length=128, pattern=r"^log_[A-Za-z0-9_]+$")
    event_type: Literal["ingestion", "compilation", "output", "user_response", "audit"] = Field(...)
    layer: Literal["log"] = Field(default="log")
    source_refs: list[str] = Field(default_factory=list, max_length=100)
    related_candidate_refs: list[str] = Field(default_factory=list, max_length=100)
    created_at: datetime = Field(default_factory=utc_now)
    summary: str = Field(..., min_length=1, max_length=2048)
    details: dict[str, str] = Field(default_factory=dict, max_length=50)
    owner: Literal["noeticbraid"] = Field(default="noeticbraid")

    @field_validator("source_refs")
    @classmethod
    def _validate_source_refs(cls, values: list[str]) -> list[str]:
        for value in values:
            if not re.fullmatch(r"^source_[A-Za-z0-9_]+$", value):
                raise ValueError("source_refs must use source_ identifiers")
        return values

    @field_validator("related_candidate_refs")
    @classmethod
    def _validate_related_candidates(cls, values: list[str]) -> list[str]:
        for value in values:
            if not re.fullmatch(r"^(candidate|suggestion|note|digestion|report_input)_[A-Za-z0-9_]+$", value):
                raise ValueError("related candidate refs must use a known module prefix")
        return values

    @field_validator("created_at")
    @classmethod
    def _ensure_created_at_utc(cls, value: datetime) -> datetime:
        return ensure_utc_datetime(value)


class ContentReusePlan(BaseModel):
    """Four-layer LLMwiki-style plan; it never writes final vault notes."""

    model_config = COMMON_MODEL_CONFIG

    created_at: datetime = Field(default_factory=utc_now)
    layer_model: list[Literal["raw/source", "compiled/wiki", "output", "log"]] = Field(
        default_factory=lambda: ["raw/source", "compiled/wiki", "output", "log"]
    )
    source_records: list[LLMWikiSourceRecord] = Field(default_factory=list)
    compiled_candidates: list[LayerCandidate] = Field(default_factory=list)
    output_candidates: list[LayerCandidate] = Field(default_factory=list)
    log_records: list[ActivityLogRecord] = Field(default_factory=list)
    audit_flags: list[RiskFlag] = Field(default_factory=list)

    @field_validator("created_at")
    @classmethod
    def _ensure_created_at_utc(cls, value: datetime) -> datetime:
        return ensure_utc_datetime(value)

    @model_validator(mode="after")
    def _validate_layer_separation(self) -> "ContentReusePlan":
        if self.layer_model != ["raw/source", "compiled/wiki", "output", "log"]:
            raise ValueError("layer_model must preserve raw/source, compiled/wiki, output, log order")
        for candidate in self.compiled_candidates:
            if candidate.layer not in ("compiled", "wiki"):
                raise ValueError("compiled_candidates must use compiled/wiki layers")
        for candidate in self.output_candidates:
            if candidate.layer != "output":
                raise ValueError("output_candidates must use output layer")
        return self

    def to_deterministic_json(self) -> str:
        return deterministic_json(self.model_dump(mode="json"))


class StructureSuggestion(BaseModel):
    """A proposed structure action; final writes remain outside this module."""

    model_config = COMMON_MODEL_CONFIG

    suggestion_id: str = Field(..., min_length=1, max_length=128, pattern=r"^suggestion_[A-Za-z0-9_]+$")
    severity: Severity = Field(...)
    target_path: str = Field(..., min_length=1, max_length=1024)
    action_type: Literal[
        "create_index",
        "add_frontmatter_template",
        "split_ai_zone",
        "mark_raw_zone",
    ] = Field(...)
    rationale: str = Field(..., min_length=1, max_length=2048)
    source_refs: list[str] = Field(..., min_length=1, max_length=100)
    evidence_paths: list[str] = Field(..., min_length=1, max_length=100)
    confidence: Confidence = Field(default="medium")
    owner: Literal["noeticbraid"] = Field(default="noeticbraid")
    status: CandidateStatus = Field(default="candidate")
    created_at: datetime = Field(default_factory=utc_now)
    proposed_markdown: Optional[str] = Field(default=None, max_length=8192)

    @field_validator("target_path")
    @classmethod
    def _normalize_target_path(cls, value: str) -> str:
        return normalize_relative_path(value, allow_dot=False)

    @field_validator("source_refs")
    @classmethod
    def _validate_source_refs(cls, values: list[str]) -> list[str]:
        for value in values:
            if not re.fullmatch(r"^source_[A-Za-z0-9_]+$", value):
                raise ValueError("source_refs must use source_ identifiers")
        return values

    @field_validator("evidence_paths")
    @classmethod
    def _normalize_evidence_paths(cls, values: list[str]) -> list[str]:
        return [normalize_relative_path(value) for value in values]

    @field_validator("created_at")
    @classmethod
    def _ensure_created_at_utc(cls, value: datetime) -> datetime:
        return ensure_utc_datetime(value)

    def to_writer_handoff_request(self) -> dict[str, Any]:
        """Return a guardable handoff packet without writing any files."""

        return {
            "handoff_type": "candidate_only",
            "writer_boundary": "obsidian_center",
            "action_type": self.action_type,
            "target_path": self.target_path,
            "candidate_ref": self.suggestion_id,
            "requires_review": True,
            "no_user_original_mutation": True,
        }


class SideNoteCandidate(BaseModel):
    """Evidence-bound side-note candidate compatible with SideNote concepts."""

    model_config = COMMON_MODEL_CONFIG

    candidate_id: str = Field(..., min_length=1, max_length=128, pattern=r"^note_[A-Za-z0-9_]+$")
    note_type: NoteType = Field(...)
    claim: str = Field(..., min_length=1, max_length=4096)
    evidence_refs: list[str] = Field(..., min_length=1, max_length=100)
    source_refs: list[str] = Field(..., min_length=1, max_length=100)
    confidence: Confidence = Field(...)
    strength: Literal["gentle", "normal", "direct"] = Field(default="normal")
    owner: Literal["noeticbraid"] = Field(default="noeticbraid")
    status: Literal["unread", "accepted", "rejected", "modified"] = Field(default="unread")
    created_at: datetime = Field(default_factory=utc_now)
    follow_up_ref: Optional[str] = Field(default=None, max_length=128)

    @field_validator("source_refs")
    @classmethod
    def _validate_source_refs(cls, values: list[str]) -> list[str]:
        for value in values:
            if not re.fullmatch(r"^source_[A-Za-z0-9_]+$", value):
                raise ValueError("source_refs must use source_ identifiers")
        return values

    @field_validator("evidence_refs")
    @classmethod
    def _validate_evidence_refs(cls, values: list[str]) -> list[str]:
        return [str(value).strip() for value in values]

    @field_validator("created_at")
    @classmethod
    def _ensure_created_at_utc(cls, value: datetime) -> datetime:
        return ensure_utc_datetime(value)

    @model_validator(mode="after")
    def _hypotheses_and_challenges_are_labelled(self) -> "SideNoteCandidate":
        claim_lower = self.claim.lower()
        if self.note_type == "hypothesis" and not claim_lower.startswith("hypothesis:"):
            raise ValueError("hypothesis claims must begin with 'Hypothesis:'")
        if self.note_type == "challenge" and not claim_lower.startswith("challenge:"):
            raise ValueError("challenge claims must begin with 'Challenge:'")
        return self

    def to_candidate_markdown(self) -> str:
        evidence = "\n".join(f"- {ref}" for ref in self.evidence_refs)
        source_refs = "\n".join(f"  - {ref}" for ref in self.source_refs)
        return (
            "---\n"
            "hm_type: side_note\n"
            "hm_owner: noeticbraid\n"
            f"note_id: {self.candidate_id}\n"
            f"note_type: {self.note_type}\n"
            "linked_source_refs:\n"
            f"{source_refs}\n"
            f"confidence: {self.confidence}\n"
            f"user_response: {self.status}\n"
            f"hm_created_at: {self.created_at.isoformat()}\n"
            "hm_status: candidate\n"
            "---\n\n"
            "## Evidence\n"
            f"{evidence}\n\n"
            "## Candidate side note\n"
            f"{self.claim}\n\n"
            "## User response\n"
        )


class DigestionCandidate(BaseModel):
    """Open digestion candidate linked to a side-note candidate."""

    model_config = COMMON_MODEL_CONFIG

    digestion_id: str = Field(..., min_length=1, max_length=128, pattern=r"^digestion_[A-Za-z0-9_]+$")
    side_note_candidate_id: str = Field(..., min_length=1, max_length=128, pattern=r"^note_[A-Za-z0-9_]+$")
    source_refs: list[str] = Field(..., min_length=1, max_length=100)
    evidence_refs: list[str] = Field(..., min_length=1, max_length=100)
    c_status: Literal["c0", "c1", "c2", "c3", "c4", "cX"] = Field(default="c0")
    status: Literal["open", "closed", "rejected", "snoozed"] = Field(default="open")
    confidence: Confidence = Field(default="medium")
    owner: Literal["noeticbraid"] = Field(default="noeticbraid")
    created_at: datetime = Field(default_factory=utc_now)
    next_review_at: Optional[datetime] = Field(default=None)

    @field_validator("source_refs")
    @classmethod
    def _validate_source_refs(cls, values: list[str]) -> list[str]:
        for value in values:
            if not re.fullmatch(r"^source_[A-Za-z0-9_]+$", value):
                raise ValueError("source_refs must use source_ identifiers")
        return values

    @field_validator("created_at")
    @classmethod
    def _ensure_created_at_utc(cls, value: datetime) -> datetime:
        return ensure_utc_datetime(value)

    @field_validator("next_review_at")
    @classmethod
    def _ensure_next_review_at_utc(cls, value: Optional[datetime]) -> Optional[datetime]:
        return ensure_optional_utc_datetime(value)

    def to_candidate_markdown(self) -> str:
        evidence = "\n".join(f"- {ref}" for ref in self.evidence_refs)
        source_refs = "\n".join(f"  - {ref}" for ref in self.source_refs)
        return (
            "---\n"
            "hm_type: digestion_item\n"
            "hm_owner: noeticbraid\n"
            f"digestion_id: {self.digestion_id}\n"
            f"side_note_id: {self.side_note_candidate_id}\n"
            "hm_source_refs:\n"
            f"{source_refs}\n"
            f"c_status: {self.c_status}\n"
            f"status: {self.status}\n"
            f"hm_created_at: {self.created_at.isoformat()}\n"
            "hm_status: candidate\n"
            "---\n\n"
            "## Trigger evidence\n"
            f"{evidence}\n\n"
            "## AI hypothesis\n"
            "Candidate only; final write requires the Obsidian writer boundary.\n\n"
            "## User response\n\n"
            "## Follow-up observation\n"
        )


class GrowthReportInput(BaseModel):
    """Candidate input packet for daily, weekly, or monthly report assembly."""

    model_config = COMMON_MODEL_CONFIG

    report_input_id: str = Field(..., min_length=1, max_length=128, pattern=r"^report_input_[A-Za-z0-9_]+$")
    period: ReportPeriod = Field(...)
    facts: list[SideNoteCandidate] = Field(default_factory=list)
    hypotheses: list[SideNoteCandidate] = Field(default_factory=list)
    challenges: list[SideNoteCandidate] = Field(default_factory=list)
    actions: list[SideNoteCandidate] = Field(default_factory=list)
    digestion_refs: list[str] = Field(default_factory=list, max_length=100)
    source_refs: list[str] = Field(..., min_length=1, max_length=100)
    owner: Literal["noeticbraid"] = Field(default="noeticbraid")
    status: CandidateStatus = Field(default="candidate")
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("digestion_refs")
    @classmethod
    def _validate_digestion_refs(cls, values: list[str]) -> list[str]:
        for value in values:
            if not re.fullmatch(r"^digestion_[A-Za-z0-9_]+$", value):
                raise ValueError("digestion_refs must use digestion_ identifiers")
        return values

    @field_validator("source_refs")
    @classmethod
    def _validate_source_refs(cls, values: list[str]) -> list[str]:
        for value in values:
            if not re.fullmatch(r"^source_[A-Za-z0-9_]+$", value):
                raise ValueError("source_refs must use source_ identifiers")
        return values

    @field_validator("created_at")
    @classmethod
    def _ensure_created_at_utc(cls, value: datetime) -> datetime:
        return ensure_utc_datetime(value)

    @model_validator(mode="after")
    def _validate_group_types(self) -> "GrowthReportInput":
        groups = [
            ("facts", self.facts, "fact"),
            ("hypotheses", self.hypotheses, "hypothesis"),
            ("challenges", self.challenges, "challenge"),
            ("actions", self.actions, "action"),
        ]
        for name, items, expected in groups:
            for item in items:
                if item.note_type != expected:
                    raise ValueError(f"{name} may only contain {expected} candidates")
        return self

    def to_deterministic_json(self) -> str:
        return deterministic_json(self.model_dump(mode="json"))


class ModuleManifest(BaseModel):
    """Deterministic review packet for this module's in-memory outputs."""

    model_config = COMMON_MODEL_CONFIG

    module: Literal["user_growth_llmwiki"] = Field(default="user_growth_llmwiki")
    generated_at: datetime = Field(default_factory=utc_now)
    vault_profile: Optional[VaultProfile] = Field(default=None)
    reuse_plan: Optional[ContentReusePlan] = Field(default=None)
    structure_suggestions: list[StructureSuggestion] = Field(default_factory=list)
    side_note_candidates: list[SideNoteCandidate] = Field(default_factory=list)
    digestion_candidates: list[DigestionCandidate] = Field(default_factory=list)
    report_inputs: list[GrowthReportInput] = Field(default_factory=list)

    @field_validator("generated_at")
    @classmethod
    def _ensure_generated_at_utc(cls, value: datetime) -> datetime:
        return ensure_utc_datetime(value)

    def to_deterministic_json(self) -> str:
        return deterministic_json(self.model_dump(mode="json"))

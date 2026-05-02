"""LLMwiki-style content-reuse primitives for the growth mirror.

This module implements structural reuse only. It records source identity,
proposes compiled/wiki and output candidates, and emits append-only log records;
it never installs or embeds an external wiki/RAG project and never writes final
Obsidian notes.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from noeticbraid_core.schemas._common import ensure_utc_datetime, utc_now

from .models import (
    ActivityLogRecord,
    ContentLayer,
    ContentReusePlan,
    LLMWikiSourceRecord,
    LayerCandidate,
    RiskFlag,
    normalize_content_hash,
    normalize_relative_path,
    stable_id,
)

_ALLOWED_SOURCE_LAYERS = {"raw", "source"}


def sha256_content(content: str | bytes) -> str:
    """Return a sha256-prefixed digest for source identity."""

    if isinstance(content, str):
        payload = content.encode("utf-8")
    else:
        payload = content
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def source_record_from_text(
    *,
    origin: str,
    text: str,
    layer: ContentLayer = "source",
    ingested_at: Optional[datetime] = None,
    relative_path: Optional[str] = None,
    title: Optional[str] = None,
    provenance: Optional[dict[str, str]] = None,
) -> LLMWikiSourceRecord:
    """Create an immutable source record without storing the raw text."""

    if layer not in _ALLOWED_SOURCE_LAYERS:
        raise ValueError("source records must use raw/source layer for ingestion")
    content_hash = sha256_content(text)
    record_id = stable_id("source_llmwiki_", origin, content_hash, layer)
    return LLMWikiSourceRecord(
        record_id=record_id,
        origin=origin,
        content_hash=content_hash,
        layer=layer,
        ingested_at=ensure_utc_datetime(ingested_at or utc_now()),
        relative_path=relative_path,
        title=title,
        provenance=provenance or {},
    )


def source_record_from_file(
    path: Path | str,
    *,
    root: Path | str,
    layer: ContentLayer = "source",
    ingested_at: Optional[datetime] = None,
    title: Optional[str] = None,
    provenance: Optional[dict[str, str]] = None,
) -> LLMWikiSourceRecord:
    """Read a local fixture/source file and record only hash and provenance.

    ``root`` is required so the recorded origin is repository/vault-relative,
    never an absolute machine-local path.
    """

    if layer not in _ALLOWED_SOURCE_LAYERS:
        raise ValueError("source records must use raw/source layer for ingestion")
    path_obj = Path(path)
    root_obj = Path(root)
    rel = path_obj.resolve().relative_to(root_obj.resolve()).as_posix()
    rel_path = normalize_relative_path(rel, allow_dot=False)
    text = path_obj.read_text(encoding="utf-8")
    inferred_title = title or Path(rel_path).stem.replace("_", " ").replace("-", " ").strip() or rel_path
    return source_record_from_text(
        origin=f"file:{rel_path}",
        text=text,
        layer=layer,
        ingested_at=ingested_at,
        relative_path=rel_path,
        title=inferred_title,
        provenance=provenance,
    )


def build_content_reuse_plan(
    source_records: Iterable[LLMWikiSourceRecord],
    *,
    created_at: Optional[datetime] = None,
    include_index_candidate: bool = True,
) -> ContentReusePlan:
    """Build a deterministic four-layer reuse plan.

    The plan is candidate-only: source records are raw/source identity,
    compiled/wiki entries are review candidates, output entries are report/review
    packet candidates, and log entries are append-only activity records.
    """

    timestamp = ensure_utc_datetime(created_at or utc_now())
    sources = sorted(source_records, key=lambda item: (item.record_id, item.origin))
    compiled: list[LayerCandidate] = []
    output: list[LayerCandidate] = []
    logs: list[ActivityLogRecord] = []

    for source in sources:
        source_ref = source.record_id
        evidence = _source_evidence(source)
        title = source.title or _title_from_origin(source.origin)
        target_path = f"compiled/wiki/{_slug(title or source.record_id)}.md"
        compiled_candidate = LayerCandidate(
            candidate_id=stable_id("candidate_wiki_", source_ref, source.content_hash, target_path),
            layer="wiki",
            target_path=target_path,
            title=f"Wiki synthesis candidate: {title}",
            source_refs=[source_ref],
            evidence_refs=evidence,
            rationale="Synthesizes source material into a NoeticBraid-owned wiki candidate; does not copy source text or write the vault.",
            status="candidate",
            owner="noeticbraid",
            created_at=timestamp,
            confidence="medium",
        )
        compiled.append(compiled_candidate)
        logs.append(
            ActivityLogRecord(
                event_id=stable_id("log_ingest_", source_ref, source.content_hash),
                event_type="ingestion",
                layer="log",
                source_refs=[source_ref],
                related_candidate_refs=[],
                created_at=timestamp,
                summary="Recorded raw/source identity for content reuse.",
                details={"layer_group": "raw/source", "origin": source.origin},
                owner="noeticbraid",
            )
        )
        logs.append(
            ActivityLogRecord(
                event_id=stable_id("log_compile_", source_ref, compiled_candidate.candidate_id),
                event_type="compilation",
                layer="log",
                source_refs=[source_ref],
                related_candidate_refs=[compiled_candidate.candidate_id],
                created_at=timestamp,
                summary="Prepared compiled/wiki candidate for review.",
                details={"target_path": compiled_candidate.target_path, "candidate_only": "true"},
                owner="noeticbraid",
            )
        )

    if include_index_candidate and compiled:
        source_refs = sorted({ref for candidate in compiled for ref in candidate.source_refs})
        output_candidate = LayerCandidate(
            candidate_id=stable_id("candidate_output_", *(candidate.candidate_id for candidate in compiled)),
            layer="output",
            target_path="output/review_packets/user_growth_llmwiki_index.md",
            title="User growth LLMwiki review packet",
            source_refs=source_refs,
            evidence_refs=[candidate.candidate_id for candidate in compiled],
            rationale="Collects compiled/wiki candidates into a reviewable output packet for downstream report assembly.",
            status="candidate",
            owner="noeticbraid",
            created_at=timestamp,
            confidence="medium",
        )
        output.append(output_candidate)
        logs.append(
            ActivityLogRecord(
                event_id=stable_id("log_output_", output_candidate.candidate_id, timestamp.isoformat()),
                event_type="output",
                layer="log",
                source_refs=source_refs,
                related_candidate_refs=[output_candidate.candidate_id],
                created_at=timestamp,
                summary="Prepared output-layer review packet candidate.",
                details={"target_path": output_candidate.target_path, "candidate_only": "true"},
                owner="noeticbraid",
            )
        )

    provisional = ContentReusePlan(
        created_at=timestamp,
        source_records=sources,
        compiled_candidates=compiled,
        output_candidates=output,
        log_records=logs,
        audit_flags=[],
    )
    audit_flags = lint_content_reuse_plan(provisional)
    return ContentReusePlan(
        created_at=timestamp,
        source_records=sources,
        compiled_candidates=compiled,
        output_candidates=output,
        log_records=logs,
        audit_flags=audit_flags,
    )


def lint_content_reuse_plan(plan: ContentReusePlan) -> list[RiskFlag]:
    """Return audit flags for layer separation and provenance gaps."""

    flags: list[RiskFlag] = []
    source_refs = {record.record_id for record in plan.source_records}
    if not plan.source_records:
        flags.append(
            RiskFlag(
                code="empty_source_layer",
                path=".",
                severity="info",
                rationale="No raw/source records were supplied to the content-reuse plan.",
                evidence_paths=["."],
            )
        )
    for record in plan.source_records:
        if record.layer not in _ALLOWED_SOURCE_LAYERS:
            flags.append(
                RiskFlag(
                    code="source_record_wrong_layer",
                    path=record.relative_path or ".",
                    severity="strong",
                    rationale="Source records must remain in the raw/source layer.",
                    evidence_paths=[record.relative_path or record.record_id],
                )
            )
        try:
            normalize_content_hash(record.content_hash)
        except ValueError:
            flags.append(
                RiskFlag(
                    code="invalid_source_hash",
                    path=record.relative_path or ".",
                    severity="strong",
                    rationale="Source record has an invalid sha256 content hash.",
                    evidence_paths=[record.relative_path or record.record_id],
                )
            )
    for candidate in [*plan.compiled_candidates, *plan.output_candidates]:
        missing = [ref for ref in candidate.source_refs if ref not in source_refs]
        if missing:
            flags.append(
                RiskFlag(
                    code="candidate_missing_source_record",
                    path=candidate.target_path,
                    severity="strong",
                    rationale="Candidate references a source ref that is absent from the raw/source layer.",
                    evidence_paths=missing,
                )
            )
        if candidate.status != "candidate":
            flags.append(
                RiskFlag(
                    code="candidate_not_reviewable",
                    path=candidate.target_path,
                    severity="light",
                    rationale="Content-reuse outputs should start as review candidates.",
                    evidence_paths=[candidate.candidate_id],
                )
            )
    if plan.compiled_candidates and not plan.log_records:
        flags.append(
            RiskFlag(
                code="missing_activity_log",
                path="log/",
                severity="strong",
                rationale="Compiled/wiki candidates require append-only log records.",
                evidence_paths=[candidate.candidate_id for candidate in plan.compiled_candidates],
            )
        )
    return sorted(flags, key=lambda flag: (flag.code, flag.path))


def _source_evidence(source: LLMWikiSourceRecord) -> list[str]:
    evidence = [source.content_hash]
    if source.relative_path:
        evidence.append(source.relative_path)
    else:
        evidence.append(source.origin)
    return evidence


def _title_from_origin(origin: str) -> str:
    stripped = origin.removeprefix("file:").removeprefix("url:")
    stem = Path(stripped).stem or stripped
    return stem.replace("_", " ").replace("-", " ").strip() or "source"


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "source"

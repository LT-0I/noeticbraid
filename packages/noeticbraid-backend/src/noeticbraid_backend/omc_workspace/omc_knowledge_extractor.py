# SPDX-License-Identifier: Apache-2.0
"""Deterministic OMC metadata extraction for SDD-D3-01."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

SECTION_START_RE = re.compile(r"^(#{1,3} \S|<[a-z_]+>\s*$)")
LIVE_ENV = "NOETICBRAID_OMC_EXTRACT_LIVE"
LIVE_INSTRUCTION = "用 NoeticBraid v3.2 §10.1 lesson 形态总结：返回 L1–L5 结构化建议，每条含 source path:line 引用"


class OMCKnowledgeExtractionError(RuntimeError):
    """Raised when required OMC source files cannot be read."""

    def __init__(self, *, missing: Iterable[str]) -> None:
        self.missing = [str(ref) for ref in missing]
        joined = ", ".join(self.missing)
        super().__init__(f"OMC source missing: {joined}")


class OMCLiveEnrichmentError(RuntimeError):
    """Raised when opt-in live OMC enrichment fails."""

    def __init__(self, *, reason: str) -> None:
        self.reason = reason
        super().__init__(f"OMC live enrichment failed: {reason}")


@dataclass(frozen=True)
class Section:
    title: str
    source_ref: str
    line_start: int
    line_end: int
    excerpt: str


@dataclass(frozen=True)
class ExtractionResult:
    summary: str
    outline: list[Section]
    narrative_artifact_ref: str
    live_artifact_ref: str | None
    source_hashes: dict[str, str]


@dataclass(frozen=True)
class _SourceDocument:
    path: Path
    source_ref: str
    text: str
    lines: list[str]
    sha16: str


def extract_omc_knowledge(
    sources: list[tuple[Path, str]],
    *,
    live: bool,
    artifact_root: Path,
    extracted_at: datetime | None = None,
) -> ExtractionResult:
    """Extract deterministic OMC source knowledge and write local artifacts.

    Phase A is pure stdlib markdown/XML-tag slicing. Phase B is opt-in and must
    fail fast before the Phase A narrative artifact is persisted.
    """

    resolved_sources = [(Path(path).expanduser(), source_ref) for path, source_ref in sources]
    missing = [source_ref for path, source_ref in resolved_sources if not path.exists()]
    if missing:
        raise OMCKnowledgeExtractionError(missing=missing)

    moment = _ensure_utc_seconds(extracted_at or datetime.now(timezone.utc))
    documents = [_read_source(path, source_ref) for path, source_ref in resolved_sources]
    outline = _build_outline(documents)
    source_hashes = {document.source_ref: document.sha16 for document in documents}
    summary = _summary(documents, outline, live=live)

    artifact_root = Path(artifact_root)
    narrative_path = artifact_root / f"omc-knowledge-extraction-{_timestamp_slug(moment)}.md"
    live_path = artifact_root / f"omx-exec-omc-knowledge-{_timestamp_slug(moment)}.md"

    live_artifact_ref: str | None = None
    if live:
        artifact_root.mkdir(parents=True, exist_ok=True)
        _run_live_enrichment(outline=outline, documents=documents, source_hashes=source_hashes, live_artifact_path=live_path)
        live_artifact_ref = str(live_path)

    artifact_root.mkdir(parents=True, exist_ok=True)
    narrative_path.write_text(
        _render_narrative_artifact(moment=moment, documents=documents, outline=outline),
        encoding="utf-8",
    )

    return ExtractionResult(
        summary=summary,
        outline=outline,
        narrative_artifact_ref=f"{narrative_path}:1",
        live_artifact_ref=live_artifact_ref,
        source_hashes=source_hashes,
    )


def _read_source(path: Path, source_ref: str) -> _SourceDocument:
    data = path.read_bytes()
    text = data.decode("utf-8")
    return _SourceDocument(
        path=path,
        source_ref=source_ref,
        text=text,
        lines=text.splitlines(),
        sha16=hashlib.sha256(data).hexdigest()[:16],
    )


def _build_outline(documents: list[_SourceDocument]) -> list[Section]:
    outline: list[Section] = []
    for document in documents:
        starts = [index for index, line in enumerate(document.lines) if SECTION_START_RE.match(line)]
        for position, start_index in enumerate(starts):
            end_exclusive = starts[position + 1] if position + 1 < len(starts) else len(document.lines)
            section_lines = document.lines[start_index:end_exclusive]
            line_start = start_index + 1
            line_end = end_exclusive
            outline.append(
                Section(
                    title=_section_title(section_lines[0]),
                    source_ref=document.source_ref,
                    line_start=line_start,
                    line_end=line_end,
                    excerpt="\n".join(section_lines[:8]),
                )
            )
    return outline


def _section_title(line: str) -> str:
    stripped = line.strip()
    if stripped.startswith("#"):
        title = stripped.lstrip("#").strip()
    elif stripped.startswith("<") and stripped.endswith(">"):
        title = stripped[1:-1].strip()
    else:  # pragma: no cover - guarded by SECTION_START_RE
        title = stripped
    if len(title) > 80:
        return title[:77] + "..."
    return title


def _summary(documents: list[_SourceDocument], outline: list[Section], *, live: bool) -> str:
    hashes_joined = ", ".join(f"{document.path.name}={document.sha16}" for document in documents)
    titles = [section.title for section in outline[:3]]
    titles_joined = ", ".join(titles)
    if len(outline) > 3:
        titles_joined = f"{titles_joined}, ..." if titles_joined else "..."
    summary = (
        f"Extracted {len(outline)} sections from {len(documents)} OMC source files "
        f"(sha256: {hashes_joined}); covers: {titles_joined}"
    )
    if live:
        summary += " (enriched=live)"
    return summary


def _render_narrative_artifact(*, moment: datetime, documents: list[_SourceDocument], outline: list[Section]) -> str:
    lines: list[str] = [
        "# OMC knowledge extraction",
        "",
        f"- extracted_at: {_isoformat_utc(moment)}",
        f"- source_count: {len(documents)}",
        f"- section_count: {len(outline)}",
        "",
        "## Sources",
        "",
    ]
    lines.extend(f"- {document.source_ref}:{document.sha16}" for document in documents)
    lines.extend(["", "## Sections", ""])
    for section in outline:
        lines.extend(
            [
                f"### {section.title}",
                "",
                f"- source: {section.source_ref}:{section.line_start}-{section.line_end}",
                "",
                "```",
                section.excerpt,
                "```",
                "",
            ]
        )
    return "\n".join(lines).rstrip("\n") + "\n"


def _run_live_enrichment(
    *,
    outline: list[Section],
    documents: list[_SourceDocument],
    source_hashes: dict[str, str],
    live_artifact_path: Path,
) -> None:
    prompt_text = _live_prompt(outline=outline, documents=documents, source_hashes=source_hashes)
    try:
        subprocess.run(
            [
                "omx",
                "exec",
                "-m",
                "gpt-5.5",
                "-c",
                'model_reasoning_effort="high"',
                "--skip-git-repo-check",
                "-o",
                str(live_artifact_path),
            ],
            input=prompt_text,
            text=True,
            timeout=300,
            check=True,
        )
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise OMCLiveEnrichmentError(reason=str(exc)) from exc
    try:
        if not live_artifact_path.read_text(encoding="utf-8").strip():
            raise OMCLiveEnrichmentError(reason=f"empty live artifact: {live_artifact_path}")
    except OSError as exc:
        raise OMCLiveEnrichmentError(reason=str(exc)) from exc


def _live_prompt(*, outline: list[Section], documents: list[_SourceDocument], source_hashes: dict[str, str]) -> str:
    payload = {
        "instruction": LIVE_INSTRUCTION,
        "source_hashes": source_hashes,
        "outline": [asdict(section) for section in outline],
        "sources": [
            {
                "path": document.source_ref,
                "sha256": document.sha16,
                "text": document.text,
            }
            for document in documents
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def _ensure_utc_seconds(value: datetime) -> datetime:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).replace(microsecond=0)


def _isoformat_utc(value: datetime) -> str:
    return _ensure_utc_seconds(value).isoformat().replace("+00:00", "Z")


def _timestamp_slug(value: datetime) -> str:
    return _ensure_utc_seconds(value).strftime("%Y%m%dT%H%M%SZ")


__all__ = [
    "ExtractionResult",
    "OMCKnowledgeExtractionError",
    "OMCLiveEnrichmentError",
    "Section",
    "extract_omc_knowledge",
]

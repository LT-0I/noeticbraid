"""Wikilink and alias mention scanner for b-1 detection."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable

from .tracked_project import ProjectCandidate, normalize_project_ref

WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
DATE_IN_PATH_RE = re.compile(r"(?<!\d)(20\d{2})[-_/](\d{2})[-_/](\d{2})(?!\d)")
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", "node_modules", "dist", "build"}


@dataclass(frozen=True)
class ProjectMention:
    """A raw project mention with only ref/date/path-line metadata."""

    project_ref: str
    mention_date: date
    path: str
    line: int
    mention_mode: str

    @property
    def source_ref(self) -> str:
        return f"{self.path}:{self.line}"


def scan_mentions(
    vault_path: str | Path,
    projects: Iterable[ProjectCandidate],
    *,
    window_start: datetime | None = None,
) -> dict[str, list[ProjectMention]]:
    """Scan markdown files for wikilink or alias mentions of tracked projects.

    The scanner returns raw mentions. Same-day de-duplication is intentionally
    performed by the detector main flow, per SDD-D1-02.
    """

    root = Path(vault_path)
    project_list = list(projects)
    by_ref = {project.project_ref: project for project in project_list}
    lookup = _build_lookup(project_list)
    alias_patterns = _build_alias_patterns(project_list)
    result: dict[str, list[ProjectMention]] = {project.project_ref: [] for project in project_list}
    start = _ensure_utc(window_start) if window_start is not None else None

    for md_path in _iter_markdown(root):
        rel = md_path.relative_to(root).as_posix()
        mention_dt = _mention_datetime(md_path, rel)
        if start is not None and mention_dt.date() < start.date():
            continue
        lines = md_path.read_text(encoding="utf-8", errors="replace").splitlines()
        for line_no, line in enumerate(lines, start=1):
            matched_on_line: set[str] = set()
            for raw_target in WIKILINK_RE.findall(line):
                target = normalize_project_ref(raw_target)
                candidates = _wikilink_candidate_keys(target)
                for key in candidates:
                    project_ref = lookup.get(_key(key))
                    if project_ref and project_ref not in matched_on_line:
                        result.setdefault(project_ref, []).append(
                            ProjectMention(project_ref, mention_dt.date(), rel, line_no, "wikilink")
                        )
                        matched_on_line.add(project_ref)
                        break
            for project_ref, patterns in alias_patterns.items():
                if project_ref in matched_on_line or project_ref not in by_ref:
                    continue
                if any(pattern.search(line) for pattern in patterns):
                    result.setdefault(project_ref, []).append(
                        ProjectMention(project_ref, mention_dt.date(), rel, line_no, "alias")
                    )
                    matched_on_line.add(project_ref)

    return {project_ref: mentions for project_ref, mentions in result.items() if mentions}


def _build_lookup(projects: list[ProjectCandidate]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for project in projects:
        keys = [project.project_ref, project.project_name, project.project_ref.split("/")[-1], *project.aliases]
        for key in keys:
            text = normalize_project_ref(key)
            if text:
                lookup[_key(text)] = project.project_ref
    return lookup


def _build_alias_patterns(projects: list[ProjectCandidate]) -> dict[str, list[re.Pattern[str]]]:
    result: dict[str, list[re.Pattern[str]]] = {}
    for project in projects:
        aliases = [project.project_name, *project.aliases]
        patterns: list[re.Pattern[str]] = []
        seen: set[str] = set()
        for alias in aliases:
            text = alias.strip()
            if not text or text.casefold() in seen:
                continue
            seen.add(text.casefold())
            escaped = re.escape(text)
            patterns.append(re.compile(rf"(?<![\w/]){escaped}(?![\w/])", re.IGNORECASE))
        result[project.project_ref] = patterns
    return result


def _wikilink_candidate_keys(target: str) -> list[str]:
    parts = [part for part in target.split("/") if part]
    keys = [target]
    if parts:
        keys.append(parts[-1])
        if parts[-1].casefold() in {"project", "_index", "index"} and len(parts) >= 2:
            keys.append(parts[-2])
    return keys


def _mention_datetime(path: Path, rel: str) -> datetime:
    match = DATE_IN_PATH_RE.search(rel)
    if match:
        year, month, day = (int(part) for part in match.groups())
        return datetime(year, month, day, tzinfo=timezone.utc)
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


def _iter_markdown(root: Path) -> list[Path]:
    if not root.exists() or not root.is_dir():
        raise ValueError("vault root must be an existing directory")
    return sorted(
        path
        for path in root.rglob("*.md")
        if path.is_file() and not any(part in SKIP_DIRS for part in path.relative_to(root).parts)
    )


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _key(value: str) -> str:
    return normalize_project_ref(value).casefold().replace("_", "-")

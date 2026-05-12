"""Progress checks for b-1 project stagnation detection."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .mention_scanner import DATE_IN_PATH_RE
from .tracked_project import normalize_project_ref

CANDIDATE_QUEUE_ENV_VAR = "NOETICBRAID_B1_CANDIDATE_QUEUE"
DONE_CHECKBOX_RE = re.compile(r"-\s*\[[xX]\]")
DONE_HEADING_RE = re.compile(r"^#{1,6}\s+Done\b", re.IGNORECASE)
MILESTONE_RE = re.compile(r"\b(milestone|里程碑)\b", re.IGNORECASE)
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", "node_modules", "dist", "build"}


@dataclass(frozen=True)
class ProgressCheckResult:
    mtime_unchanged: bool
    no_new_done: bool
    no_new_response: bool

    @property
    def is_stagnant(self) -> bool:
        return self.mtime_unchanged and self.no_new_done and self.no_new_response

    def to_record(self) -> dict[str, bool]:
        return {
            "mtime_unchanged": self.mtime_unchanged,
            "no_new_done": self.no_new_done,
            "no_new_response": self.no_new_response,
        }


def mtime_unchanged(project_ref: str, window_start: datetime, vault_path: str | Path = ".") -> bool:
    """Return true when project-related files have no mtime in the window."""

    root = Path(vault_path)
    start = _ensure_utc(window_start).timestamp()
    for path in _project_related_paths(root, project_ref):
        if path.exists() and path.stat().st_mtime >= start:
            return False
    return True


def no_new_done(project_ref: str, window_start: datetime, vault_path: str | Path) -> bool:
    """Return true when no new done/milestone marker references the project."""

    root = Path(vault_path)
    start = _ensure_utc(window_start)
    keys = _project_reference_keys(project_ref)
    for path in _iter_markdown(root):
        rel = path.relative_to(root).as_posix()
        if _note_datetime(path, rel).date() < start.date():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not _is_done_signal(line):
                continue
            if _line_mentions_project(line, keys):
                return False
    return True


def no_new_response(project_ref: str, window_start: datetime) -> bool:
    """Return true when no b-1 SideNote user response changed in the window."""

    queue = candidate_queue_path(None)
    if not queue.exists():
        return True
    start = _ensure_utc(window_start)
    ref = normalize_project_ref(project_ref)
    try:
        rows = json.loads(queue.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return True
    if not isinstance(rows, list):
        return True
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("candidate_type") != "b1_sidenote":
            continue
        if normalize_project_ref(str(row.get("project_ref", ""))) != ref:
            continue
        response = str(row.get("user_response", "unread"))
        if response in {"", "unread"}:
            continue
        changed_at = _parse_datetime(row.get("user_response_at") or row.get("updated_at") or row.get("created_at"))
        if changed_at is not None and changed_at >= start:
            return False
    return True


def progress_checks(project_ref: str, window_start: datetime, vault_path: str | Path) -> ProgressCheckResult:
    """Return the three b-1 progress predicates without collapsing them."""

    return ProgressCheckResult(
        mtime_unchanged=mtime_unchanged(project_ref, window_start, vault_path),
        no_new_done=no_new_done(project_ref, window_start, vault_path),
        no_new_response=no_new_response(project_ref, window_start),
    )


def is_stagnant(project_ref: str, window_start: datetime, vault_path: str | Path) -> bool:
    """A project is stagnant only when all three no-progress checks are true."""

    return progress_checks(project_ref, window_start, vault_path).is_stagnant


def candidate_queue_path(vault_path: str | Path | None = None) -> Path:
    """Return the b-1 candidate queue path without writing inside the vault."""

    env_path = os.environ.get(CANDIDATE_QUEUE_ENV_VAR)
    if env_path:
        return Path(env_path).expanduser()
    cwd_queue = Path.cwd() / ".omx" / "candidates" / "b1-detector.json"
    if vault_path is not None and _path_is_within(cwd_queue.resolve(), Path(vault_path).resolve()):
        return Path("~/.noeticbraid/candidates/b1-detector.json").expanduser()
    return cwd_queue


def _project_related_paths(root: Path, project_ref: str) -> list[Path]:
    ref = normalize_project_ref(project_ref)
    candidates = [root / ref]
    if not ref.endswith(".md"):
        candidates.append(root / f"{ref}.md")
    parts = [part for part in ref.split("/") if part]
    if parts:
        candidates.append(root / "Projects" / f"{parts[-1]}.md")
        candidates.append(root / "Projects" / parts[-1])
    if (root / ref).is_dir():
        candidates.extend(sorted((root / ref).rglob("*.md")))
    existing_dirs = [path for path in candidates if path.exists() and path.is_dir()]
    for directory in existing_dirs:
        candidates.extend(sorted(directory.rglob("*.md")))
    result: list[Path] = []
    seen: set[Path] = set()
    for path in candidates:
        if path not in seen:
            result.append(path)
            seen.add(path)
    return result


def _project_reference_keys(project_ref: str) -> set[str]:
    ref = normalize_project_ref(project_ref)
    parts = [part for part in ref.split("/") if part]
    keys = {ref.casefold()}
    if parts:
        keys.add(parts[-1].casefold())
        if parts[-1].casefold() in {"project", "_index", "index"} and len(parts) >= 2:
            keys.add(parts[-2].casefold())
    return keys


def _line_mentions_project(line: str, keys: set[str]) -> bool:
    text = line.casefold().replace("\\", "/")
    compact = normalize_project_ref(text).casefold()
    for key in keys:
        if f"[[{key}" in text or key in compact:
            return True
    return False


def _is_done_signal(line: str) -> bool:
    return bool(DONE_CHECKBOX_RE.search(line) or DONE_HEADING_RE.search(line) or MILESTONE_RE.search(line))


def _iter_markdown(root: Path) -> list[Path]:
    if not root.exists() or not root.is_dir():
        raise ValueError("vault root must be an existing directory")
    return sorted(
        path
        for path in root.rglob("*.md")
        if path.is_file() and not any(part in SKIP_DIRS for part in path.relative_to(root).parts)
    )


def _note_datetime(path: Path, rel: str) -> datetime:
    match = DATE_IN_PATH_RE.search(rel)
    if match:
        year, month, day = (int(part) for part in match.groups())
        return datetime(year, month, day, tzinfo=timezone.utc)
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


def _parse_datetime(value: object) -> datetime | None:
    if not value:
        return None
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return _ensure_utc(datetime.fromisoformat(text))
    except ValueError:
        return None


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _path_is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False

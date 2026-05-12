"""Tracked project registry for b-1 SideNote detection.

The registry is deliberately outside the Obsidian vault by default. AI may
create ``candidate`` project records from repeated wikilinks, but only the user
CLI path may promote them to ``confirmed``.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

TrackedProjectStatus = Literal["candidate", "confirmed"]

REGISTRY_ENV_VAR = "NOETICBRAID_TRACKED_PROJECTS_PATH"
DEFAULT_REGISTRY_PATH = Path("~/.noeticbraid/tracked_projects.json")
WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", "node_modules", "dist", "build"}


@dataclass(frozen=True)
class ProjectCandidate:
    """A user-reviewable tracked-project registry item."""

    project_ref: str
    project_name: str
    aliases: list[str] = field(default_factory=list)
    status: TrackedProjectStatus = "candidate"
    candidate_type: str = "tracked_project"
    mention_count: int = 0
    evidence_source: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: _now_iso())
    updated_at: str = field(default_factory=lambda: _now_iso())

    def to_record(self) -> dict[str, Any]:
        return {
            "candidate_type": self.candidate_type,
            "project_ref": self.project_ref,
            "project_name": self.project_name,
            "aliases": list(dict.fromkeys(self.aliases)),
            "status": self.status,
            "mention_count": self.mention_count,
            "evidence_source": list(dict.fromkeys(self.evidence_source)),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_record(cls, data: dict[str, Any]) -> "ProjectCandidate":
        status = str(data.get("status", "candidate"))
        if status not in {"candidate", "confirmed"}:
            raise ValueError(f"invalid tracked_project status: {status!r}")
        project_ref = normalize_project_ref(str(data["project_ref"]))
        return cls(
            candidate_type="tracked_project",
            project_ref=project_ref,
            project_name=str(data.get("project_name") or default_project_name(project_ref)),
            aliases=[str(item) for item in data.get("aliases", []) if str(item).strip()],
            status=status,  # type: ignore[arg-type]
            mention_count=int(data.get("mention_count", 0)),
            evidence_source=[str(item) for item in data.get("evidence_source", []) if str(item).strip()],
            created_at=str(data.get("created_at") or _now_iso()),
            updated_at=str(data.get("updated_at") or _now_iso()),
        )


def registry_path(path: str | Path | None = None) -> Path:
    """Return the tracked-project registry path, honoring test/runtime overrides."""

    if path is not None:
        return Path(path).expanduser()
    env_path = os.environ.get(REGISTRY_ENV_VAR)
    if env_path:
        return Path(env_path).expanduser()
    return DEFAULT_REGISTRY_PATH.expanduser()


def load_registry(path: str | Path | None = None) -> list[ProjectCandidate]:
    """Load tracked projects from JSON; missing registry means no projects."""

    target = registry_path(path)
    if not target.exists():
        return []
    data = json.loads(target.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        rows = data.get("projects", [])
    elif isinstance(data, list):
        rows = data
    else:
        raise ValueError("tracked_project registry must be a JSON list or object with projects")
    return [ProjectCandidate.from_record(dict(row)) for row in rows]


def save_registry(projects: list[ProjectCandidate], path: str | Path | None = None) -> None:
    """Persist tracked projects to the registry JSON file."""

    target = registry_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(projects, key=lambda item: item.project_ref.casefold())
    payload = {"projects": [item.to_record() for item in ordered]}
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def auto_discover(vault_path: str | Path) -> list[ProjectCandidate]:
    """Discover wikilinked project candidates mentioned at least three times.

    This is a candidate-only write to the registry. It never promotes a project
    to ``confirmed``; approval is reserved for the explicit CLI/user path.
    """

    root = Path(vault_path)
    mentions: dict[str, list[str]] = {}
    for md_path in _iter_markdown(root):
        rel = md_path.relative_to(root).as_posix()
        for line_no, line in enumerate(md_path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            for raw_target in WIKILINK_RE.findall(line):
                project_ref = normalize_project_ref(raw_target)
                if not project_ref:
                    continue
                mentions.setdefault(project_ref, []).append(f"{rel}:{line_no}")

    existing = {item.project_ref: item for item in load_registry()}
    changed = False
    now = _now_iso()
    for project_ref, refs in sorted(mentions.items()):
        unique_refs = list(dict.fromkeys(refs))
        if len(unique_refs) < 3:
            continue
        previous = existing.get(project_ref)
        if previous is not None:
            merged_refs = list(dict.fromkeys([*previous.evidence_source, *unique_refs]))
            aliases = _default_aliases(project_ref, previous.project_name, previous.aliases)
            existing[project_ref] = ProjectCandidate(
                project_ref=project_ref,
                project_name=previous.project_name,
                aliases=aliases,
                status=previous.status,
                mention_count=max(previous.mention_count, len(unique_refs)),
                evidence_source=merged_refs,
                created_at=previous.created_at,
                updated_at=now,
            )
            changed = True
            continue
        name = default_project_name(project_ref)
        existing[project_ref] = ProjectCandidate(
            project_ref=project_ref,
            project_name=name,
            aliases=_default_aliases(project_ref, name, []),
            status="candidate",
            mention_count=len(unique_refs),
            evidence_source=unique_refs,
            created_at=now,
            updated_at=now,
        )
        changed = True

    if changed:
        save_registry(list(existing.values()))
    return sorted([item for item in existing.values() if item.status == "candidate"], key=lambda item: item.project_ref.casefold())


def approve(project_ref: str) -> None:
    """Promote a candidate tracked project to confirmed via the user CLI path."""

    _set_status(project_ref, "confirmed")


def unconfirm(project_ref: str) -> None:
    """Demote a confirmed tracked project back to candidate without deleting history."""

    _set_status(project_ref, "candidate")


def confirmed_projects(path: str | Path | None = None) -> list[ProjectCandidate]:
    """Return confirmed projects only."""

    return [item for item in load_registry(path) if item.status == "confirmed"]


def normalize_project_ref(value: str) -> str:
    """Normalize a wikilink target or CLI project ref for registry identity."""

    text = str(value).strip()
    if "|" in text:
        text = text.split("|", 1)[0]
    if "#" in text:
        text = text.split("#", 1)[0]
    text = text.replace("\\", "/").strip().strip("/")
    if text.endswith(".md"):
        text = text[:-3]
    text = re.sub(r"/{2,}", "/", text)
    return text


def default_project_name(project_ref: str) -> str:
    """Derive a readable project name from a project ref."""

    parts = [part for part in project_ref.split("/") if part]
    if not parts:
        return project_ref
    if parts[-1].casefold() in {"project", "_index", "index"} and len(parts) >= 2:
        return parts[-2]
    return parts[-1]


def _set_status(project_ref: str, status: TrackedProjectStatus) -> None:
    ref = normalize_project_ref(project_ref)
    projects = load_registry()
    for index, item in enumerate(projects):
        if item.project_ref == ref:
            projects[index] = ProjectCandidate(
                project_ref=item.project_ref,
                project_name=item.project_name,
                aliases=item.aliases,
                status=status,
                mention_count=item.mention_count,
                evidence_source=item.evidence_source,
                created_at=item.created_at,
                updated_at=_now_iso(),
            )
            save_registry(projects)
            return
    raise KeyError(f"tracked_project not found: {ref}")


def _iter_markdown(root: Path) -> list[Path]:
    if not root.exists() or not root.is_dir():
        raise ValueError("vault root must be an existing directory")
    return sorted(
        path
        for path in root.rglob("*.md")
        if path.is_file() and not any(part in SKIP_DIRS for part in path.relative_to(root).parts)
    )


def _default_aliases(project_ref: str, project_name: str, aliases: list[str]) -> list[str]:
    values = [project_name, project_ref.split("/")[-1], *aliases]
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = value.strip()
        if text and text.casefold() not in seen:
            result.append(text)
            seen.add(text.casefold())
    return result


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

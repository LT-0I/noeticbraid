# SPDX-License-Identifier: Apache-2.0
"""Policy-checked vault writer with dry-run default and atomic live writes."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .dashboard import preserve_manual_notes
from .errors import WritePolicyViolation
from .frontmatter import extract_frontmatter
from .path_policy import ModeEnforcer, resolve_path
from .renderer import RenderedNote
from .settings import WritePolicySettings, default_settings

ALLOWED_APPEND_HEADINGS = {"Status Notes", "Decision Notes"}


@dataclass(frozen=True)
class WriteResult:
    """Result of a dry-run or live vault write."""

    relative_path: str
    absolute_path: Path
    written: bool
    dry_run: bool
    preview_text: str


class VaultWriter:
    """Write generated dashboards and stable records into a local vault namespace."""

    def __init__(self, vault_root: Path | str, settings: WritePolicySettings | None = None) -> None:
        self.vault_root = Path(vault_root)
        self.settings = settings or default_settings()
        self.enforcer = ModeEnforcer(self.settings)

    @property
    def dry_run(self) -> bool:
        return self.settings.default_write_mode != "live"

    def write_dashboard(self, dashboard_id: str, note: RenderedNote) -> WriteResult:
        """Write a generated dashboard. Generated surfaces may be overwritten."""

        if note.frontmatter.get("generated") is not True:
            raise WritePolicyViolation("dashboard writes require generated: true frontmatter")
        relative = resolve_path("dashboard", dashboard_id, date=str(note.frontmatter["date"]), namespace=self.settings.namespace)
        absolute = self.enforcer.resolve_under_vault(self.vault_root, relative)
        text = note.to_markdown()
        if absolute.exists() and self.settings.generated_overwrite_allowed:
            existing = absolute.read_text(encoding="utf-8")
            _existing_frontmatter, existing_body = extract_frontmatter(existing)
            merged_body = preserve_manual_notes(note.body, existing_body)
            text = RenderedNote(dict(note.frontmatter), merged_body).to_markdown()
        return self._write(relative, text, allow_overwrite=self.settings.generated_overwrite_allowed)

    def write_stable_record(
        self,
        nb_type: str,
        record_id: str,
        note: RenderedNote,
        *,
        date: str,
        project: str = "default",
    ) -> WriteResult:
        """Create a stable record. Existing records fail closed."""

        relative = resolve_path(nb_type, record_id, date=date, namespace=self.settings.namespace, project=project)
        allow_overwrite = self.settings.non_generated_overwrite_allowed
        return self._write(relative, note.to_markdown(), allow_overwrite=allow_overwrite)

    def append_to_heading(self, relative_path: str, heading: str, content: str) -> WriteResult:
        """Append content under an allowed heading and atomically rewrite the note."""

        if heading not in ALLOWED_APPEND_HEADINGS:
            raise WritePolicyViolation(f"append heading not allowed: {heading}")
        absolute = self.enforcer.resolve_under_vault(self.vault_root, relative_path)
        if not absolute.exists():
            raise WritePolicyViolation(f"target note does not exist: {relative_path}")
        text = absolute.read_text(encoding="utf-8")
        needle = f"## {heading}"
        if needle not in text:
            raise WritePolicyViolation(f"target heading not found: {heading}")
        updated = _append_under_heading(text, heading, content)
        if self.dry_run:
            normalized = self.enforcer.require_allowed_write_path(relative_path)
            return WriteResult(normalized, absolute, written=False, dry_run=True, preview_text=updated)
        _atomic_write_text(absolute, updated)
        normalized = self.enforcer.require_allowed_write_path(relative_path)
        return WriteResult(normalized, absolute, written=True, dry_run=False, preview_text=updated)

    def record_sync_log(self, entry: dict[str, Any]) -> None:
        """Append a non-secret sync-log entry.

        The sync log is append-only and intentionally bypasses full-file atomic
        replacement. Crash safety is line-oriented: each appended line is
        flushed and fsynced before the next append; partial-line detection is a
        reader responsibility.
        """

        relative = self.settings.sync_log_relative_path
        absolute = self.enforcer.resolve_under_vault(self.vault_root, relative)
        if self.dry_run:
            return
        absolute.parent.mkdir(parents=True, exist_ok=True)
        line = "- " + " ".join(f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in entry.items())
        with absolute.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def _write(self, relative_path: str, text: str, *, allow_overwrite: bool) -> WriteResult:
        normalized = self.enforcer.require_allowed_write_path(relative_path)
        absolute = self.enforcer.resolve_under_vault(self.vault_root, normalized)
        if absolute.exists() and not allow_overwrite:
            raise WritePolicyViolation(f"stable record already exists: {normalized}")
        if self.settings.generated_surface_requires_frontmatter and not text.startswith("---\n"):
            raise WritePolicyViolation("writes require frontmatter")
        if self.dry_run:
            return WriteResult(normalized, absolute, written=False, dry_run=True, preview_text=text)
        _atomic_write_text(absolute, text)
        return WriteResult(normalized, absolute, written=True, dry_run=False, preview_text=text)


def _append_under_heading(text: str, heading: str, content: str) -> str:
    heading_line = f"## {heading}"
    lines = text.splitlines()
    start = next(index for index, line in enumerate(lines) if line.strip() == heading_line)
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if lines[index].startswith("## "):
            end = index
            break
    insert = content.rstrip()
    while end > start + 1 and lines[end - 1] == "":
        end -= 1
    lines.insert(end, insert)
    return "\n".join(lines) + "\n"


def _atomic_write_text(path: Path, text: str) -> None:
    """Atomic same-directory text write."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".tmp_{path.name}.{os.getpid()}.tmp")
    try:
        temp_path.write_text(text, encoding="utf-8")
        os.replace(temp_path, path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def is_generated_markdown(text: str) -> bool:
    frontmatter, _body = extract_frontmatter(text)
    return frontmatter.get("generated") is True

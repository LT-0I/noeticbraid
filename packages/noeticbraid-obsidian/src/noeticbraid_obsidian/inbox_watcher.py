# SPDX-License-Identifier: Apache-2.0
"""Polling inbox watcher for user_dropzone Markdown files."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .frontmatter import extract_frontmatter
from .path_policy import ModeEnforcer, normalize_relative_path
from .settings import WritePolicySettings, default_settings


class InboxWatcher:
    """Scan the configured user dropzone and convert notes into task dicts.

    This class deliberately uses polling and direct Markdown parsing only. It does
    not launch Obsidian, install plugins, or depend on watchdog.
    """

    def __init__(self, vault_root: Path | str, settings: WritePolicySettings | None = None) -> None:
        self.vault_root = Path(vault_root)
        self.settings = settings or default_settings()
        self.enforcer = ModeEnforcer(self.settings)
        self._seen: set[Path] = set()

    def scan_once(
        self,
        *,
        on_task: Callable[[dict[str, Any]], None],
        on_run_record: Callable[[dict[str, Any]], None] | None = None,
    ) -> int:
        """Process each unseen Markdown file once and return the count."""

        dropzone = self._dropzone_path()
        if not dropzone.exists():
            return 0
        processed = 0
        for path in sorted(dropzone.glob("*.md")):
            if path in self._seen:
                continue
            task = self._task_from_file(path)
            on_task(task)
            if on_run_record is not None:
                on_run_record(_run_record_for_task(task))
            self._seen.add(path)
            processed += 1
        return processed

    def _task_from_file(self, path: Path) -> dict[str, Any]:
        text = path.read_text(encoding="utf-8")
        frontmatter, body = extract_frontmatter(text)
        created_at = _utc_now()
        title = str(frontmatter.get("title") or path.stem)
        task_id = "task_obsidian_" + hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:12]
        relative = path.relative_to(self.vault_root).as_posix()
        return {
            "task_id": task_id,
            "task_type": frontmatter.get("task_type", "research"),
            "risk_level": frontmatter.get("risk_level", "low"),
            "approval_level": frontmatter.get("approval_level", "light"),
            "status": "ready",
            "source_channel": "obsidian",
            "created_at": created_at,
            "title": title,
            "project_ref": frontmatter.get("project_ref"),
            "tags": frontmatter.get("tags", ["noeticbraid/inbox"]),
            "body": body,
            "source_path": relative,
        }

    def _dropzone_path(self) -> Path:
        normalized = normalize_relative_path(self.settings.user_dropzone_read_relative_root.rstrip("/") + "/inbox.md")
        if normalized is None:
            raise ValueError("invalid user_dropzone_read_relative_root")
        read_root = self.settings.user_dropzone_read_relative_root.rstrip("/") + "/"
        if not normalized.startswith(read_root):
            raise ValueError("dropzone path must stay under user_dropzone_read_relative_root")
        return self.vault_root.joinpath(*normalized.split("/")[:-1]).resolve()


def _run_record_for_task(task: dict[str, Any]) -> dict[str, Any]:
    source_id = "source_obsidian_" + hashlib.sha256(str(task["source_path"]).encode("utf-8")).hexdigest()[:16]
    return {
        "run_id": "run_obsidian_" + hashlib.sha256(str(task["task_id"]).encode("utf-8")).hexdigest()[:12],
        "task_id": task["task_id"],
        "event_type": "task_created",
        "actor": "system",
        "status": "recorded",
        "created_at": task["created_at"],
        "source_refs": [source_id],
        "vault_source_path": task["source_path"],
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

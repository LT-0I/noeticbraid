# SPDX-License-Identifier: Apache-2.0
"""One-shot SideNote note_type migration for contract 2.0.0.

Default behavior is dry-run only. Live writes require either the explicit
``apply=True`` API/``--apply`` CLI flag or an interactive typed ``yes`` through
``--confirm``. Before any live write, affected files are backed up under the
vault at ``.noeticbraid-backup-<UTC>/``.
"""

from __future__ import annotations

import argparse
import difflib
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

NOTE_TYPE_MAP = {
    "challenge": "hypothesis",
    "action": "action_suggestion",
}
NOTE_TYPE_LINE_RE = re.compile(
    r"^(?P<prefix>\s*note_type\s*[:=]\s*)(?P<quote>[\"']?)(?P<value>challenge|action)(?P=quote)(?P<suffix>\s*)$"
)


@dataclass(frozen=True)
class FileChange:
    """Planned or applied note_type update for one vault file."""

    path: Path
    relative_path: Path
    original_text: str
    migrated_text: str
    diff: str


@dataclass(frozen=True)
class MigrationResult:
    """Result of a dry-run or live migration."""

    vault_path: Path
    dry_run: bool
    changed_files: tuple[Path, ...]
    diff_previews: dict[Path, str] = field(default_factory=dict)
    backup_path: Path | None = None
    written: bool = False


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _iter_markdown_files(vault_path: Path) -> Iterable[Path]:
    for path in sorted(vault_path.rglob("*.md")):
        if any(part.startswith(".noeticbraid-backup-") for part in path.relative_to(vault_path).parts):
            continue
        yield path


def _migrate_text(text: str) -> str:
    lines = text.splitlines(keepends=True)
    migrated: list[str] = []
    for line in lines:
        line_ending = "\n" if line.endswith("\n") else ""
        body = line[:-1] if line_ending else line
        match = NOTE_TYPE_LINE_RE.match(body)
        if match is None:
            migrated.append(line)
            continue
        new_value = NOTE_TYPE_MAP[match.group("value")]
        migrated.append(
            f"{match.group('prefix')}{match.group('quote')}{new_value}{match.group('quote')}{match.group('suffix')}{line_ending}"
        )
    return "".join(migrated)


def plan_migration(vault_path: str | Path) -> tuple[FileChange, ...]:
    """Return affected files and unified diffs without writing anything."""

    vault = Path(vault_path).expanduser().resolve()
    if not vault.is_dir():
        raise ValueError(f"vault path must be an existing directory: {vault}")

    changes: list[FileChange] = []
    for path in _iter_markdown_files(vault):
        original = path.read_text(encoding="utf-8")
        migrated = _migrate_text(original)
        if migrated == original:
            continue
        relative = path.relative_to(vault)
        diff = "".join(
            difflib.unified_diff(
                original.splitlines(keepends=True),
                migrated.splitlines(keepends=True),
                fromfile=str(relative),
                tofile=f"{relative} (v2)",
            )
        )
        changes.append(FileChange(path, relative, original, migrated, diff))
    return tuple(changes)


def _backup_changes(vault: Path, changes: tuple[FileChange, ...], stamp: str | None = None) -> Path:
    backup_root = vault / f".noeticbraid-backup-{stamp or _utc_stamp()}"
    for change in changes:
        backup_target = backup_root / change.relative_path
        backup_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(change.path, backup_target)
    return backup_root


def migrate_vault(
    vault_path: str | Path,
    *,
    apply: bool = False,
    confirm: bool = False,
    input_func: Callable[[str], str] = input,
    timestamp: str | None = None,
) -> MigrationResult:
    """Migrate legacy SideNote note_type values.

    Dry-run is the default and returns affected files plus diff previews.
    Live writes require ``apply=True`` or ``confirm=True`` with typed ``yes``.
    """

    vault = Path(vault_path).expanduser().resolve()
    changes = plan_migration(vault)
    previews = {change.relative_path: change.diff for change in changes}
    changed_files = tuple(change.relative_path for change in changes)

    if not changes:
        return MigrationResult(vault, dry_run=not apply, changed_files=changed_files, diff_previews=previews)

    should_write = apply
    if confirm and not apply:
        answer = input_func("Type yes to apply SideNote note_type v2 migration: ")
        should_write = answer == "yes"

    if not should_write:
        return MigrationResult(vault, dry_run=True, changed_files=changed_files, diff_previews=previews)

    backup_path = _backup_changes(vault, changes, stamp=timestamp)
    for change in changes:
        change.path.write_text(change.migrated_text, encoding="utf-8")

    return MigrationResult(
        vault,
        dry_run=False,
        changed_files=changed_files,
        diff_previews=previews,
        backup_path=backup_path,
        written=True,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Migrate SideNote note_type values to contract 2.0.0.")
    parser.add_argument("vault", type=Path, help="Obsidian vault path")
    parser.add_argument("--apply", action="store_true", help="write changes after backing up affected files")
    parser.add_argument("--confirm", action="store_true", help="prompt for typed yes before writing")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    result = migrate_vault(args.vault, apply=args.apply, confirm=args.confirm)
    mode = "APPLIED" if result.written else "DRY-RUN"
    print(f"{mode}: {len(result.changed_files)} file(s) affected")
    for rel_path in result.changed_files:
        print(f"- {rel_path}")
        diff = result.diff_previews.get(rel_path)
        if diff:
            print(diff, end="" if diff.endswith("\n") else "\n")
    if result.backup_path is not None:
        print(f"backup: {result.backup_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

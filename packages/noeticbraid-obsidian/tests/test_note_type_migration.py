from __future__ import annotations

from pathlib import Path

from noeticbraid_obsidian.migration.note_type_v2 import migrate_vault, plan_migration


def _write_note(path: Path, note_type: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\nnote_type: {note_type}\n---\n\nBody\n", encoding="utf-8")


def test_challenge_to_hypothesis_dry_run_lists_diff_without_writing(tmp_path: Path) -> None:
    note = tmp_path / "side.md"
    _write_note(note, "challenge")

    result = migrate_vault(tmp_path)

    assert result.dry_run is True
    assert result.written is False
    assert result.changed_files == (Path("side.md"),)
    assert "-note_type: challenge" in result.diff_previews[Path("side.md")]
    assert "+note_type: hypothesis" in result.diff_previews[Path("side.md")]
    assert "note_type: challenge" in note.read_text(encoding="utf-8")


def test_challenge_to_hypothesis_apply_writes_after_backup(tmp_path: Path) -> None:
    note = tmp_path / "nested" / "side.md"
    _write_note(note, "challenge")

    result = migrate_vault(tmp_path, apply=True, timestamp="20260511T120000Z")

    assert result.dry_run is False
    assert result.written is True
    assert result.backup_path == tmp_path / ".noeticbraid-backup-20260511T120000Z"
    assert "note_type: hypothesis" in note.read_text(encoding="utf-8")
    backup_note = result.backup_path / "nested" / "side.md"
    assert "note_type: challenge" in backup_note.read_text(encoding="utf-8")


def test_action_to_action_suggestion_apply_writes_and_backup(tmp_path: Path) -> None:
    note = tmp_path / "side.md"
    _write_note(note, "action")

    result = migrate_vault(tmp_path, apply=True, timestamp="20260511T121500Z")

    assert result.written is True
    assert "note_type: action_suggestion" in note.read_text(encoding="utf-8")
    assert (result.backup_path / "side.md").is_file()


def test_confirm_requires_typed_yes_before_writing(tmp_path: Path) -> None:
    note = tmp_path / "side.md"
    _write_note(note, "challenge")

    result = migrate_vault(tmp_path, confirm=True, input_func=lambda _prompt: "no")

    assert result.dry_run is True
    assert result.written is False
    assert "note_type: challenge" in note.read_text(encoding="utf-8")
    assert len(plan_migration(tmp_path)) == 1

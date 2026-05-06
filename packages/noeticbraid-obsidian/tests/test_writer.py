from __future__ import annotations

from pathlib import Path

import pytest

from noeticbraid_obsidian.renderer import MarkdownRenderer
from noeticbraid_obsidian.settings import default_settings
from noeticbraid_obsidian import writer as writer_module
from noeticbraid_obsidian.writer import VaultWriter, WritePolicyViolation


def test_writer_defaults_to_dry_run_without_touching_vault(tmp_path: Path) -> None:
    writer = VaultWriter(tmp_path, default_settings())
    renderer = MarkdownRenderer()
    note = renderer.render_dashboard(
        dashboard_id="today",
        title="Today",
        date="2026-05-06",
        generated_at="2026-05-06T12:00:00Z",
        body="## Today\n- dry run",
    )

    result = writer.write_dashboard("today", note)

    assert result.written is False
    assert result.dry_run is True
    assert result.relative_path == "NoeticBraid/00_dashboard/today.md"
    assert not (tmp_path / result.relative_path).exists()
    assert "dry run" in result.preview_text


def test_writer_live_mode_atomic_writes_generated_and_create_only_records(tmp_path: Path) -> None:
    settings = default_settings(write_mode="live")
    writer = VaultWriter(tmp_path, settings)
    renderer = MarkdownRenderer()
    dashboard = renderer.render_dashboard(
        dashboard_id="today",
        title="Today",
        date="2026-05-06",
        generated_at="2026-05-06T12:00:00Z",
        body="## Today\n- first",
    )
    updated_dashboard = renderer.render_dashboard(
        dashboard_id="today",
        title="Today",
        date="2026-05-06",
        generated_at="2026-05-06T13:00:00Z",
        body="## Today\n- second",
    )
    task = renderer.render_task(
        {
            "task_id": "task_obsidian_001",
            "task_type": "research",
            "risk_level": "low",
            "approval_level": "none",
            "status": "ready",
            "source_channel": "obsidian",
            "created_at": "2026-05-06T12:00:00Z",
        },
        body="Stable task.",
    )

    first = writer.write_dashboard("today", dashboard)
    second = writer.write_dashboard("today", updated_dashboard)
    stable = writer.write_stable_record("task", "task_obsidian_001", task, date="2026-05-06")

    assert first.written is True
    assert second.written is True
    assert "second" in (tmp_path / second.relative_path).read_text(encoding="utf-8")
    assert stable.relative_path == "NoeticBraid/20_episodic_memory/40_projects/default/plans/task_obsidian_001.md"
    with pytest.raises(WritePolicyViolation):
        writer.write_stable_record("task", "task_obsidian_001", task, date="2026-05-06")


def test_append_to_heading_is_policy_limited_and_sync_log_is_append_only(tmp_path: Path) -> None:
    writer = VaultWriter(tmp_path, default_settings(write_mode="live"))
    target = tmp_path / "NoeticBraid" / "20_episodic_memory" / "40_projects" / "default" / "plans" / "task_obsidian_001.md"
    target.parent.mkdir(parents=True)
    target.write_text("# Task\n\n## Status Notes\nOld\n\n## Other\nKeep\n", encoding="utf-8")

    result = writer.append_to_heading(
        "NoeticBraid/20_episodic_memory/40_projects/default/plans/task_obsidian_001.md",
        "Status Notes",
        "New line",
    )
    writer.record_sync_log({"event": "write", "path": result.relative_path, "created_at": "2026-05-06T12:00:00Z"})
    writer.record_sync_log({"event": "append", "path": result.relative_path, "created_at": "2026-05-06T12:01:00Z"})

    text = target.read_text(encoding="utf-8")
    assert "Old\nNew line\n\n## Other" in text
    log_text = (tmp_path / "NoeticBraid" / "90_system" / "sync_log.md").read_text(encoding="utf-8")
    assert log_text.count("- event:") == 2
    with pytest.raises(WritePolicyViolation):
        writer.append_to_heading(result.relative_path, "Other", "forbidden")


def test_write_dashboard_preserves_manual_notes(tmp_path: Path) -> None:
    writer = VaultWriter(tmp_path, default_settings(write_mode="live"))
    renderer = MarkdownRenderer()
    first = renderer.render_dashboard(
        dashboard_id="today",
        title="Today",
        date="2026-05-06",
        generated_at="2026-05-06T12:00:00Z",
        body="## Active tasks\n- old generated\n\n## Manual notes\nuser-owned note\n",
    )
    second = renderer.render_dashboard(
        dashboard_id="today",
        title="Today",
        date="2026-05-06",
        generated_at="2026-05-06T13:00:00Z",
        body="## Active tasks\n- new generated\n\n## Manual notes\n",
    )

    writer.write_dashboard("today", first)
    result = writer.write_dashboard("today", second)
    text = (tmp_path / result.relative_path).read_text(encoding="utf-8")

    assert "new generated" in text
    assert "old generated" not in text
    assert "## Manual notes\nuser-owned note" in text


def test_atomic_write_cleans_tmp_on_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "note.md"

    def fail_replace(_temp_path: Path, _target_path: Path) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(writer_module.os, "replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        writer_module._atomic_write_text(target, "body")

    assert not list(tmp_path.glob(".tmp_*"))

from __future__ import annotations

import re
from pathlib import Path

from noeticbraid_obsidian.dashboard import DashboardContext, DashboardGenerator, preserve_manual_notes
from noeticbraid_obsidian.frontmatter import render_markdown
from noeticbraid_obsidian.inbox_watcher import InboxWatcher
from noeticbraid_obsidian.settings import default_settings


def test_dashboard_generator_preserves_manual_notes_boundary() -> None:
    generator = DashboardGenerator()
    existing = "## Today\nold generated\n\n## Manual notes\nkeep this\n"
    generated = generator.generate_today(
        DashboardContext(
            date="2026-05-06",
            active_tasks=[{"task_id": "task_1", "title": "Review", "status": "ready"}],
            digestion_items=[{"digestion_id": "digestion_1", "status": "open"}],
            recent_runs=[{"run_id": "run_1", "status": "recorded"}],
        )
    )

    merged = preserve_manual_notes(generated, existing)

    assert "task_1" in merged
    assert "digestion_1" in merged
    assert "## Manual notes\nkeep this" in merged


def test_dashboard_generator_supports_weekly_dashboard() -> None:
    generator = DashboardGenerator()

    body = generator.generate_this_week(
        [
            {"task_id": "task_1", "status": "ready", "title": "Review"},
            {"run_id": "run_1", "status": "recorded"},
        ],
        week_start="2026-05-04",
    )

    assert "# NoeticBraid Week - 2026-05-04" in body
    assert "task_1" in body
    assert "run_1" in body
    assert "## Manual notes" in body


def test_inbox_watcher_parses_dropzone_markdown_and_invokes_callbacks(tmp_path: Path) -> None:
    dropzone = tmp_path / "NoeticBraid" / "80_inbox" / "user_dropzone"
    dropzone.mkdir(parents=True)
    note_text = render_markdown(
        {
            "title": "Research CLI bridge",
            "task_type": "research",
            "risk_level": "low",
            "approval_level": "light",
            "project_ref": "project_alpha",
            "tags": ["noeticbraid/inbox"],
        },
        "Please compare local-only vault bridge designs.",
    )
    (dropzone / "Research CLI bridge.md").write_text(note_text, encoding="utf-8")
    tasks: list[dict[str, object]] = []
    runs: list[dict[str, object]] = []

    watcher = InboxWatcher(tmp_path, default_settings())
    processed = watcher.scan_once(on_task=tasks.append, on_run_record=runs.append)

    assert processed == 1
    assert tasks[0]["source_channel"] == "obsidian"
    assert tasks[0]["status"] == "ready"
    assert tasks[0]["task_type"] == "research"
    assert tasks[0]["body"] == "Please compare local-only vault bridge designs."
    assert tasks[0]["source_path"] == "NoeticBraid/80_inbox/user_dropzone/Research CLI bridge.md"
    assert runs[0]["event_type"] == "task_created"
    assert runs[0]["task_id"] == tasks[0]["task_id"]
    assert re.fullmatch(r"source_[A-Za-z0-9_]+", runs[0]["source_refs"][0])
    assert "/" not in runs[0]["source_refs"][0]
    assert runs[0]["vault_source_path"] == tasks[0]["source_path"]

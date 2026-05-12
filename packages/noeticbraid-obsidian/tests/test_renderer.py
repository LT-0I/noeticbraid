from __future__ import annotations

import json

from noeticbraid_obsidian.frontmatter import extract_frontmatter, render_markdown
import pytest

from noeticbraid_obsidian.errors import RenderError
from noeticbraid_obsidian.renderer import MarkdownRenderer


def test_renderer_emits_task_frontmatter_and_body_without_user_raw_text() -> None:
    renderer = MarkdownRenderer()

    note = renderer.render_task(
        {
            "task_id": "task_obsidian_001",
            "task_type": "research",
            "risk_level": "low",
            "approval_level": "light",
            "status": "ready",
            "source_channel": "obsidian",
            "created_at": "2026-05-06T12:00:00Z",
            "account_hint": None,
            "project_ref": "project_alpha",
            "title": "Review source bundle",
        },
        body="Summarize accepted source references.",
    )

    assert note.frontmatter["nb_type"] == "task"
    assert note.frontmatter["contract_version"] == "1.3.0"
    assert note.frontmatter["source_channel"] == "obsidian"
    assert "Summarize accepted source references." in note.body
    assert "user_request" not in json.dumps(note.frontmatter)


def test_render_markdown_round_trips_frontmatter_lists_and_bools() -> None:
    renderer = MarkdownRenderer()
    note = renderer.render_dashboard(
        dashboard_id="today",
        title="Today",
        date="2026-05-06",
        generated_at="2026-05-06T12:00:00Z",
        body="## Today\n- Ready",
    )

    text = render_markdown(note.frontmatter, note.body)
    frontmatter, body = extract_frontmatter(text)

    assert frontmatter["generated"] is True
    assert frontmatter["tags"] == ["noeticbraid/dashboard"]
    assert body == note.body


def test_renderer_supports_core_note_types() -> None:
    renderer = MarkdownRenderer()

    notes = [
        renderer.render_run_record(
            {
                "run_id": "run_obsidian_001",
                "task_id": "task_obsidian_001",
                "event_type": "task_created",
                "actor": "system",
                "status": "recorded",
                "created_at": "2026-05-06T12:00:00Z",
            },
            body="Created task from dropzone.",
        ),
        renderer.render_side_note(
            {
                "note_id": "note_obsidian_001",
                "created_at": "2026-05-06T12:00:00Z",
                "linked_source_refs": ["source_obsidian_001"],
                "evidence_source": ["source_obsidian_001"],
                "note_type": "fact",
                "confidence": "medium",
                "tone_constraint": "不审判用户 / 不羞辱用户 / 不替用户解释自己；违反任一构成 fatal",
                "user_response_channel": ["accept", "rebut", "mark_inaccurate", "disable_this_type"],
                "user_response": "unread",
            },
            body="Potential follow-up.",
        ),
        renderer.render_digestion_item(
            {
                "digestion_id": "digestion_obsidian_001",
                "side_note_id": "note_obsidian_001",
                "created_at": "2026-05-06T12:00:00Z",
                "c_status": "c2",
                "status": "open",
            },
            body="Needs review.",
        ),
    ]

    assert [note.frontmatter["nb_type"] for note in notes] == ["run_record", "side_note", "digestion_item"]
    assert notes[0].frontmatter["contract_version"] == "1.3.0"
    assert notes[1].frontmatter["contract_version"] == "2.0.0"
    assert notes[2].frontmatter["contract_version"] == "1.3.0"


def test_render_side_note_invalid_enum_raises() -> None:
    renderer = MarkdownRenderer()

    with pytest.raises(RenderError, match="note_type"):
        renderer.render_side_note(
            {
                "note_id": "note_obsidian_001",
                "created_at": "2026-05-06T12:00:00Z",
                "linked_source_refs": ["source_obsidian_001"],
                "evidence_source": ["source_obsidian_001"],
                "note_type": "observation",
                "confidence": "medium",
                "tone_constraint": "不审判用户 / 不羞辱用户 / 不替用户解释自己；违反任一构成 fatal",
                "user_response_channel": ["accept", "rebut", "mark_inaccurate", "disable_this_type"],
                "user_response": "unread",
            },
            body="Invalid enum should not render.",
        )

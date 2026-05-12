from __future__ import annotations

import pytest

from noeticbraid_obsidian.errors import RenderError
from noeticbraid_obsidian.frontmatter import extract_frontmatter
from noeticbraid_obsidian.renderer import MarkdownRenderer, SIDE_NOTE_TONE_CONSTRAINT


def _side_note() -> dict[str, object]:
    return {
        "note_id": "note_metadata_001",
        "created_at": "2026-05-11T12:00:00Z",
        "linked_source_refs": ["source_metadata_001"],
        "evidence_source": ["source_metadata_001"],
        "note_type": "hypothesis",
        "confidence": "high",
        "tone_constraint": SIDE_NOTE_TONE_CONSTRAINT,
        "user_response_channel": ["accept", "rebut", "mark_inaccurate", "disable_this_type"],
        "user_response": "unread",
    }


def test_side_note_renderer_outputs_all_five_metadata_fields() -> None:
    rendered = MarkdownRenderer().render_side_note(_side_note(), body="Claim body.")
    frontmatter, body = extract_frontmatter(rendered.to_markdown())

    assert frontmatter["contract_version"] == "2.0.0"
    assert frontmatter["evidence_source"] == ["source_metadata_001"]
    assert frontmatter["note_type"] == "hypothesis"
    assert frontmatter["confidence"] == "high"
    assert frontmatter["tone_constraint"] == SIDE_NOTE_TONE_CONSTRAINT
    assert frontmatter["user_response_channel"] == [
        "accept",
        "rebut",
        "mark_inaccurate",
        "disable_this_type",
    ]
    assert "可关闭此类旁注 / disable_this_type" in body


@pytest.mark.parametrize(
    "missing_field",
    ["evidence_source", "note_type", "confidence", "tone_constraint", "user_response_channel"],
)
def test_side_note_renderer_rejects_missing_metadata(missing_field: str) -> None:
    data = _side_note()
    data.pop(missing_field)

    with pytest.raises(RenderError):
        MarkdownRenderer().render_side_note(data, body="Claim body.")

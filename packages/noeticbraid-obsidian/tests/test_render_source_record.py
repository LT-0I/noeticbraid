from __future__ import annotations

from typing import Any

import pytest

from noeticbraid_obsidian.errors import RenderError
from noeticbraid_obsidian.renderer import MarkdownRenderer


def minimal_record(**overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "nb_type": "source_record",
        "schema_version": "obsidian-hub-0.1",
        "contract_version": "1.3.0",
        "source_ref_id": "source_render_001",
        "source_type": "web_page",
        "title": "Render Source",
        "captured_at": "2026-05-14T12:00:00+00:00",
        "quality_score": "unknown",
        "relevance_score": "unknown",
        "tags": ["noeticbraid/source/test"],
    }
    record.update(overrides)
    return record


def test_render_source_record_required_fields() -> None:
    note = MarkdownRenderer().render_source_record(minimal_record(), body="")

    assert note.frontmatter["nb_type"] == "source_record"
    assert note.frontmatter["schema_version"] == "obsidian-hub-0.1"
    assert note.frontmatter["contract_version"] == "1.3.0"
    assert note.frontmatter["source_ref_id"] == "source_render_001"
    assert note.frontmatter["source_type"] == "web_page"
    assert note.frontmatter["title"] == "Render Source"
    assert note.frontmatter["captured_at"] == "2026-05-14T12:00:00+00:00"
    assert note.frontmatter["quality_score"] == "unknown"
    assert note.frontmatter["relevance_score"] == "unknown"
    assert note.frontmatter["tags"] == ["noeticbraid/source", "noeticbraid/source/test"]


def test_render_source_record_optional_omitted_and_present() -> None:
    renderer = MarkdownRenderer()
    omitted = renderer.render_source_record(minimal_record(), body="")
    present_record = minimal_record(
        title="Rich Source",
        canonical_url="https://example.com/canonical",
        local_path="/tmp/source.md",
        content_hash="sha256:" + "a" * 64,
        source_fingerprint="fingerprint-1",
    )

    present = renderer.render_source_record(present_record, body="Body text")

    assert omitted.frontmatter["canonical_url"] is None
    assert omitted.frontmatter["local_path"] is None
    assert omitted.frontmatter["content_hash"] is None
    assert omitted.frontmatter["source_fingerprint"] is None
    assert present.frontmatter["canonical_url"] == "https://example.com/canonical"
    assert present.frontmatter["local_path"] == "/tmp/source.md"
    assert present.frontmatter["content_hash"] == "sha256:" + "a" * 64
    assert present.frontmatter["source_fingerprint"] == "fingerprint-1"
    assert present.body.startswith("# Rich Source\n\n")


def test_render_source_record_invalid_enum_raises() -> None:
    renderer = MarkdownRenderer()
    cases = [
        ("quality_score", "bogus"),
        ("relevance_score", "bogus"),
        ("evidence_role", "bogus"),
        ("used_for_purpose", "bogus"),
    ]

    for field_name, value in cases:
        with pytest.raises(RenderError, match=field_name):
            renderer.render_source_record(minimal_record(**{field_name: value}), body="")

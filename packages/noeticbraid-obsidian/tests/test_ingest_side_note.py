from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any

import pytest

from noeticbraid_obsidian import default_settings, ingest_side_note
from noeticbraid_obsidian.errors import RenderError
from noeticbraid_obsidian.path_policy import PathPolicyError
from noeticbraid_obsidian.renderer import SIDE_NOTE_TONE_CONSTRAINT
from noeticbraid_obsidian.writer import WritePolicyViolation


def valid_side_note(**overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "note_id": "note_ingest_001",
        "created_at": "2026-05-15T12:00:00Z",
        "linked_source_refs": ["source_sidenote_001"],
        "evidence_source": ["source_sidenote_001"],
        "note_type": "hypothesis",
        "confidence": "medium",
        "tone_constraint": SIDE_NOTE_TONE_CONSTRAINT,
        "user_response_channel": ["accept", "rebut", "mark_inaccurate", "disable_this_type"],
        "user_response": "unread",
    }
    record.update(overrides)
    return record


def test_dry_run_default_returns_preview_no_write(tmp_path: Path) -> None:
    result = ingest_side_note(valid_side_note(), vault_root=tmp_path)

    assert result.dry_run is True
    assert result.written is False
    assert result.preview_text.startswith("---\n")
    assert not (tmp_path / result.relative_path).exists()
    assert list(tmp_path.iterdir()) == []


def test_live_mode_writes_to_ai_observations_path(tmp_path: Path) -> None:
    result = ingest_side_note(
        valid_side_note(),
        vault_root=tmp_path,
        settings=default_settings(write_mode="live"),
    )

    expected_prefix = "NoeticBraid/20_episodic_memory/20_ai_observations/side_notes/2026/05/"
    assert result.written is True
    assert result.dry_run is False
    assert result.relative_path.startswith(expected_prefix)
    assert result.absolute_path == tmp_path / result.relative_path
    assert result.absolute_path.exists()
    assert result.absolute_path.read_text(encoding="utf-8") == result.preview_text


def test_path_is_ai_observations_never_user_raw(tmp_path: Path) -> None:
    result = ingest_side_note(valid_side_note(), vault_root=tmp_path)

    assert "20_episodic_memory/20_ai_observations/side_notes/" in result.relative_path
    assert not result.relative_path.startswith("NoeticBraid/20_episodic_memory/10_user_raw/")
    assert "20_episodic_memory/10_user_raw/" not in result.relative_path


def test_record_id_is_note_id_from_frontmatter(tmp_path: Path) -> None:
    record = valid_side_note(note_id="note_frontmatter_042")

    result = ingest_side_note(record, vault_root=tmp_path)

    assert PurePosixPath(result.relative_path).name == f"{record['note_id']}.md"


def test_date_derived_from_created_at(tmp_path: Path) -> None:
    record = valid_side_note(created_at="2026-05-15T23:59:00+00:00")

    result = ingest_side_note(record, vault_root=tmp_path)

    assert "/2026/05/" in f"/{result.relative_path}"


def test_missing_note_id_raises_render_error(tmp_path: Path) -> None:
    record = valid_side_note()
    del record["note_id"]

    with pytest.raises(RenderError):
        ingest_side_note(record, vault_root=tmp_path)


def test_invalid_note_type_raises_render_error(tmp_path: Path) -> None:
    with pytest.raises(RenderError):
        ingest_side_note(valid_side_note(note_type="bogus"), vault_root=tmp_path)


def test_tone_constraint_literal_enforced(tmp_path: Path) -> None:
    with pytest.raises(RenderError):
        ingest_side_note(
            valid_side_note(tone_constraint=SIDE_NOTE_TONE_CONSTRAINT.replace("不审判", "不评判")),
            vault_root=tmp_path,
        )


def test_evidence_source_must_match_linked_source_refs(tmp_path: Path) -> None:
    with pytest.raises(RenderError):
        ingest_side_note(valid_side_note(evidence_source=["source_sidenote_other"]), vault_root=tmp_path)


def test_user_response_channel_must_have_all_four(tmp_path: Path) -> None:
    with pytest.raises(RenderError):
        ingest_side_note(
            valid_side_note(user_response_channel=["accept", "rebut", "mark_inaccurate"]),
            vault_root=tmp_path,
        )


def test_path_fragment_in_note_id_rejected(tmp_path: Path) -> None:
    with pytest.raises(PathPolicyError):
        ingest_side_note(valid_side_note(note_id="../escape"), vault_root=tmp_path)


def test_all_note_types_ingestible_and_path_invariant(tmp_path: Path) -> None:
    for index, note_type in enumerate(("fact", "hypothesis", "action_suggestion")):
        result = ingest_side_note(
            valid_side_note(note_id=f"note_type_{index}", note_type=note_type),
            vault_root=tmp_path,
        )

        assert result.dry_run is True
        assert "20_episodic_memory/20_ai_observations/side_notes/" in result.relative_path
        assert "20_episodic_memory/10_user_raw/" not in result.relative_path


def test_create_only_second_ingest_raises(tmp_path: Path) -> None:
    settings = default_settings(write_mode="live")
    record = valid_side_note(note_id="note_create_only")
    first = ingest_side_note(record, vault_root=tmp_path, settings=settings, body="first body")
    before = first.absolute_path.read_text(encoding="utf-8")

    with pytest.raises(WritePolicyViolation):
        ingest_side_note(record, vault_root=tmp_path, settings=settings, body="second body")

    assert first.absolute_path.read_text(encoding="utf-8") == before

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone, tzinfo
from pathlib import Path

import jsonschema
import pytest
from notebooklm import Note

from noeticbraid.tools.notebooklm_rpc import (
    NOTEBOOK_TAG,
    NOTE_TAG,
    NotebookLMNoteError,
    note_to_source_record,
)


AWARE_UTC = datetime(2026, 5, 14, 12, 0, 0, tzinfo=timezone.utc)


class PlusSeven(tzinfo):
    def utcoffset(self, dt):
        return timedelta(hours=7)

    def dst(self, dt):
        return timedelta(0)


def make_note(**overrides) -> Note:
    params = {
        "id": "n_1",
        "notebook_id": "nb_1",
        "title": "X",
        "content": "...",
        "created_at": AWARE_UTC,
    }
    params.update(overrides)
    return Note(**params)


def minimal_record(**overrides):
    params = {"note": make_note(), "captured_at": AWARE_UTC}
    params.update(overrides)
    return note_to_source_record(**params)


def assert_error_class(excinfo, error_class: str) -> None:
    assert excinfo.value.error_class == error_class


def load_source_record_schema() -> dict:
    repo_root = Path(__file__).resolve().parents[3]
    schema_path = (
        repo_root
        / "packages"
        / "noeticbraid-obsidian"
        / "src"
        / "noeticbraid_obsidian"
        / "schemas"
        / "source_record_note.schema.json"
    )
    if not schema_path.exists():
        pytest.fail("source_record_note.schema.json not reachable; obsidian package required for nser-3a")
    return json.loads(schema_path.read_text())


def test_minimal_required_only():
    record = minimal_record()
    assert record == {
        "nb_type": "source_record",
        "schema_version": "obsidian-hub-0.1",
        "contract_version": "1.3.0",
        "source_ref_id": "source_notebooklm_note_n_1",
        "source_type": "user_note",
        "title": "X",
        "captured_at": "2026-05-14T12:00:00+00:00",
        "quality_score": "unknown",
        "relevance_score": "unknown",
        "tags": ["noeticbraid/notebooklm/note", "noeticbraid/notebooklm/notebook/nb_1"],
        "source_fingerprint": "notebooklm_note:n_1",
    }
    assert len(record) == 11


def test_source_ref_id_format():
    assert minimal_record()["source_ref_id"] == "source_notebooklm_note_n_1"


def test_source_fingerprint_format():
    assert minimal_record()["source_fingerprint"] == "notebooklm_note:n_1"


def test_source_type_always_user_note():
    assert minimal_record()["source_type"] == "user_note"


def test_tags_include_note_and_notebook_tags():
    note = make_note(notebook_id="nb_123")
    record = minimal_record(note=note)
    assert NOTE_TAG in record["tags"]
    assert f"{NOTEBOOK_TAG}/{note.notebook_id}" in record["tags"]


def test_title_override_wins():
    assert minimal_record(title_override="Custom")["title"] == "Custom"


def test_title_fallback_to_note_title():
    note = make_note(title="Note Title")
    assert minimal_record(note=note, title_override=None)["title"] == note.title


def test_title_truncation_to_512():
    record = minimal_record(note=make_note(title="x" * 600))
    assert len(record["title"]) == 512
    assert record["title"] == "x" * 512


def test_captured_at_utc_isoformat():
    captured_at = datetime(2026, 5, 14, 19, 0, 0, tzinfo=PlusSeven())
    assert minimal_record(captured_at=captured_at)["captured_at"] == "2026-05-14T12:00:00+00:00"


def test_quality_relevance_unknown():
    record = minimal_record()
    assert record["quality_score"] == "unknown"
    assert record["relevance_score"] == "unknown"


def test_optional_local_path_passthrough(tmp_path: Path):
    tmp_file = tmp_path / "note.md"
    tmp_file.touch()
    assert minimal_record(local_path=tmp_file)["local_path"] == str(tmp_file)


def test_optional_content_hash_passthrough():
    content_hash = "sha256:" + "c" * 64
    assert minimal_record(content_hash=content_hash)["content_hash"] == content_hash


def test_optional_retrieved_by_run_id_passthrough():
    assert minimal_record(retrieved_by_run_id="run_x")["retrieved_by_run_id"] == "run_x"


def test_never_emitted_fields_absent():
    never = {
        "source_ref",
        "author",
        "evidence_role",
        "used_for_purpose",
        "canonical_url",
        "external_url",
    }
    assert never.isdisjoint(minimal_record().keys())


def test_validation_invalid_note_id_chars_raises():
    with pytest.raises(NotebookLMNoteError) as excinfo:
        minimal_record(note=make_note(id="bad-id!"))
    assert_error_class(excinfo, "invalid_note_id")


def test_validation_note_id_too_long_raises():
    with pytest.raises(NotebookLMNoteError) as excinfo:
        minimal_record(note=make_note(id="a" * 106))
    assert_error_class(excinfo, "invalid_note_id")


def test_validation_note_id_boundary_105_passes():
    note_id = "a" * 105
    record = minimal_record(note=make_note(id=note_id))
    assert record["source_ref_id"] == "source_notebooklm_note_" + note_id


def test_validation_naive_captured_at_raises():
    with pytest.raises(NotebookLMNoteError) as excinfo:
        minimal_record(captured_at=datetime(2026, 5, 14, 12, 0, 0))
    assert_error_class(excinfo, "naive_captured_at")


def test_validation_local_path_missing_raises(tmp_path: Path):
    with pytest.raises(NotebookLMNoteError) as excinfo:
        minimal_record(local_path=tmp_path / "missing.md")
    assert_error_class(excinfo, "local_path_missing")


def test_validation_invalid_content_hash_raises():
    with pytest.raises(NotebookLMNoteError) as excinfo:
        minimal_record(content_hash="md5:abc")
    assert_error_class(excinfo, "invalid_content_hash")


def test_validation_invalid_run_id_raises():
    with pytest.raises(NotebookLMNoteError) as excinfo:
        minimal_record(retrieved_by_run_id="42")
    assert_error_class(excinfo, "invalid_run_id")


def test_validation_title_empty_raises():
    with pytest.raises(NotebookLMNoteError) as excinfo:
        minimal_record(note=make_note(title="  "), title_override=None)
    assert_error_class(excinfo, "title_empty")


def test_output_validates_against_frozen_schema(tmp_path: Path):
    schema = load_source_record_schema()
    validator = jsonschema.Draft7Validator(schema)
    tmp_file = tmp_path / "note.md"
    tmp_file.touch()
    minimal = minimal_record()
    maximal = minimal_record(
        title_override="Custom",
        local_path=tmp_file,
        content_hash="sha256:" + "c" * 64,
        retrieved_by_run_id="run_x",
    )

    for record in (minimal, maximal):
        errors = sorted(validator.iter_errors(record), key=lambda error: error.path)
        assert errors == []

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, tzinfo
from pathlib import Path

import jsonschema
import pytest

from noeticbraid.tools.notebooklm_rpc import (
    NOTEBOOK_TAG,
    NotebookLMLifecycleError,
    notebook_to_source_record,
)


AWARE_UTC = datetime(2026, 5, 14, 12, 0, 0, tzinfo=timezone.utc)


@dataclass
class Stub:
    id: str = "nb_1"
    title: str = "My NB"
    created_at: datetime | None = None
    sources_count: int = 0
    is_owner: bool = True


class PlusNine(tzinfo):
    def utcoffset(self, dt):
        return timedelta(hours=9)

    def dst(self, dt):
        return timedelta(0)


def minimal_record(**overrides):
    params = {
        "notebook": Stub(),
        "captured_at": AWARE_UTC,
    }
    params.update(overrides)
    return notebook_to_source_record(**params)


def assert_error_class(excinfo, error_class: str):
    assert excinfo.value.error_class == error_class
    assert str(excinfo.value).startswith(f"{error_class}: ")


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
        pytest.fail("source_record_note.schema.json not reachable; obsidian package required for nser-2h")
    return json.loads(schema_path.read_text())


def test_minimal_required_only():
    record = minimal_record()
    assert record == {
        "nb_type": "source_record",
        "schema_version": "obsidian-hub-0.1",
        "contract_version": "1.3.0",
        "source_ref_id": "source_notebooklm_notebook_nb_1",
        "source_type": "user_note",
        "title": "My NB",
        "captured_at": "2026-05-14T12:00:00+00:00",
        "quality_score": "unknown",
        "relevance_score": "unknown",
        "tags": ["noeticbraid/notebooklm/notebook"],
        "source_fingerprint": "notebooklm_notebook:nb_1",
    }
    assert len(record) == 11


def test_source_ref_id_format():
    assert minimal_record()["source_ref_id"] == "source_notebooklm_notebook_nb_1"


def test_source_fingerprint_format():
    assert minimal_record()["source_fingerprint"] == "notebooklm_notebook:nb_1"


def test_source_type_is_user_note():
    assert minimal_record()["source_type"] == "user_note"


def test_tag_is_notebook_tag():
    assert minimal_record()["tags"] == [NOTEBOOK_TAG]
    assert NOTEBOOK_TAG == "noeticbraid/notebooklm/notebook"


def test_title_override_wins():
    assert minimal_record(notebook=Stub(title="X"), title_override="Custom")["title"] == "Custom"


def test_title_fallback_to_notebook_title():
    notebook = Stub(title="Notebook Title")
    assert minimal_record(notebook=notebook, title_override=None)["title"] == notebook.title


def test_title_truncation_to_512_codepoints():
    record = minimal_record(notebook=Stub(title="x" * 600))
    assert len(record["title"]) == 512
    assert record["title"] == "x" * 512


def test_captured_at_utc_isoformat():
    captured_at = datetime(2026, 5, 14, 21, 0, 0, tzinfo=PlusNine())
    assert minimal_record(captured_at=captured_at)["captured_at"] == "2026-05-14T12:00:00+00:00"


def test_quality_relevance_unknown():
    record = minimal_record()
    assert record["quality_score"] == "unknown"
    assert record["relevance_score"] == "unknown"


def test_optional_content_hash_passthrough():
    content_hash = "sha256:" + "f" * 64
    assert minimal_record(content_hash=content_hash)["content_hash"] == content_hash
    assert "content_hash" not in minimal_record()


def test_optional_retrieved_by_run_id_passthrough():
    assert minimal_record(retrieved_by_run_id="run_x")["retrieved_by_run_id"] == "run_x"
    assert "retrieved_by_run_id" not in minimal_record()


def test_never_emitted_fields_absent():
    never = {
        "canonical_url",
        "local_path",
        "source_ref",
        "external_url",
        "author",
        "evidence_role",
        "used_for_purpose",
    }
    assert never.isdisjoint(minimal_record().keys())


def test_validation_invalid_notebook_id_chars_raises():
    with pytest.raises(NotebookLMLifecycleError) as excinfo:
        minimal_record(notebook=Stub(id="bad-nb!"))
    assert_error_class(excinfo, "invalid_notebook_id")


def test_validation_notebook_id_too_long_raises():
    with pytest.raises(NotebookLMLifecycleError) as excinfo:
        minimal_record(notebook=Stub(id="a" * 102))
    assert_error_class(excinfo, "invalid_notebook_id")


def test_validation_notebook_id_boundary_101_passes():
    notebook_id = "a" * 101
    record = minimal_record(notebook=Stub(id=notebook_id))
    assert record["source_ref_id"] == "source_notebooklm_notebook_" + notebook_id


def test_validation_naive_captured_at_raises():
    with pytest.raises(NotebookLMLifecycleError) as excinfo:
        minimal_record(captured_at=datetime.utcnow())
    assert_error_class(excinfo, "naive_captured_at")


def test_validation_invalid_run_id_raises():
    with pytest.raises(NotebookLMLifecycleError) as excinfo:
        minimal_record(retrieved_by_run_id="42")
    assert_error_class(excinfo, "invalid_run_id")


def test_validation_invalid_content_hash_raises():
    with pytest.raises(NotebookLMLifecycleError) as excinfo:
        minimal_record(content_hash="md5:abc")
    assert_error_class(excinfo, "invalid_content_hash")


def test_validation_title_empty_notebook_title_raises():
    with pytest.raises(NotebookLMLifecycleError) as excinfo:
        minimal_record(notebook=Stub(title="   "), title_override=None)
    assert_error_class(excinfo, "title_empty")


def test_validation_title_override_empty_string_raises():
    with pytest.raises(NotebookLMLifecycleError) as excinfo:
        minimal_record(notebook=Stub(title="X"), title_override="")
    assert_error_class(excinfo, "title_empty")


def test_validation_title_override_whitespace_only_raises():
    with pytest.raises(NotebookLMLifecycleError) as excinfo:
        minimal_record(title_override="   ")
    assert_error_class(excinfo, "title_empty")


def test_output_validates_against_frozen_schema():
    schema = load_source_record_schema()
    validator = jsonschema.Draft7Validator(schema)
    minimal = minimal_record()
    maximal = minimal_record(
        title_override="Custom",
        retrieved_by_run_id="run_test_42",
        content_hash="sha256:" + "f" * 64,
    )

    for record in (minimal, maximal):
        errors = sorted(validator.iter_errors(record), key=lambda error: error.path)
        assert errors == []

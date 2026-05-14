from __future__ import annotations

import json
from datetime import datetime, timezone, tzinfo, timedelta
from pathlib import Path

import jsonschema
import pytest

from noeticbraid.tools.notebooklm_rpc import (
    ARTIFACT_KIND_TO_TAG,
    ArtifactKind,
    NotebookLMPoolError,
    NotebookLMSerializationError,
    artifact_to_source_record,
)


AWARE_UTC = datetime(2026, 5, 14, 12, 0, 0, tzinfo=timezone.utc)


class PlusEight(tzinfo):
    def utcoffset(self, dt):
        return timedelta(hours=8)

    def dst(self, dt):
        return timedelta(0)


def minimal_record(**overrides):
    params = {
        "artifact_id": "art_123",
        "kind": ArtifactKind.REPORT,
        "captured_at": AWARE_UTC,
    }
    params.update(overrides)
    return artifact_to_source_record(**params)


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
        pytest.fail("source_record_note.schema.json not reachable; obsidian package required for ser-3a")
    return json.loads(schema_path.read_text())


def test_minimal_required_only():
    record = minimal_record()
    assert record == {
        "nb_type": "source_record",
        "schema_version": "obsidian-hub-0.1",
        "contract_version": "1.3.0",
        "source_ref_id": "source_notebooklm_art_123",
        "source_type": "ai_output",
        "title": "NotebookLM report (art_123)",
        "captured_at": "2026-05-14T12:00:00+00:00",
        "quality_score": "unknown",
        "relevance_score": "unknown",
        "tags": ["noeticbraid/notebooklm/report"],
        "source_fingerprint": "notebooklm_artifact:art_123",
    }
    assert len(record) == 11


def test_source_ref_id_format():
    assert minimal_record()["source_ref_id"] == "source_notebooklm_art_123"


def test_source_fingerprint_format():
    assert minimal_record()["source_fingerprint"] == "notebooklm_artifact:art_123"


@pytest.mark.parametrize("kind", list(ArtifactKind))
def test_tags_byte_equal_for_each_kind(kind):
    record = minimal_record(kind=kind)
    assert record["tags"] == [ARTIFACT_KIND_TO_TAG[kind]]


def test_title_caller_provided():
    assert minimal_record(title="Custom")["title"] == "Custom"


def test_title_synthetic_fallback():
    assert minimal_record(title=None)["title"] == "NotebookLM report (art_123)"


def test_title_truncation_to_512_codepoints():
    record = minimal_record(title="x" * 600)
    assert len(record["title"]) == 512
    assert record["title"] == "x" * 512


def test_captured_at_utc_isoformat():
    captured_at = datetime(2026, 5, 14, 20, 0, 0, tzinfo=PlusEight())
    assert minimal_record(captured_at=captured_at)["captured_at"] == "2026-05-14T12:00:00+00:00"


def test_quality_relevance_unknown():
    record = minimal_record()
    assert record["quality_score"] == "unknown"
    assert record["relevance_score"] == "unknown"


def test_optional_local_path_present_when_given(tmp_path):
    local_path = tmp_path / "artifact.bin"
    local_path.touch()
    assert minimal_record(local_path=local_path)["local_path"] == str(local_path)


def test_optional_local_path_absent_when_not_given():
    assert "local_path" not in minimal_record()


def test_optional_content_hash_passthrough():
    content_hash = "sha256:" + "a" * 64
    assert minimal_record(content_hash=content_hash)["content_hash"] == content_hash
    assert "content_hash" not in minimal_record()


def test_optional_retrieved_by_run_id_passthrough():
    assert minimal_record(retrieved_by_run_id="run_test_42")["retrieved_by_run_id"] == "run_test_42"
    assert "retrieved_by_run_id" not in minimal_record()


def test_never_emitted_fields_absent():
    never = {
        "canonical_url",
        "source_ref",
        "external_url",
        "author",
        "evidence_role",
        "used_for_purpose",
    }
    assert never.isdisjoint(minimal_record().keys())


def test_validation_invalid_artifact_id_chars_raises():
    with pytest.raises(NotebookLMSerializationError) as excinfo:
        minimal_record(artifact_id="bad-id")
    assert_error_class(excinfo, "invalid_artifact_id")


def test_validation_invalid_artifact_id_too_long_raises():
    with pytest.raises(NotebookLMSerializationError) as excinfo:
        minimal_record(artifact_id="a" * 111)
    assert_error_class(excinfo, "invalid_artifact_id")


def test_validation_artifact_id_boundary_110_passes():
    artifact_id = "a" * 110
    record = minimal_record(artifact_id=artifact_id)
    assert record["source_ref_id"] == "source_notebooklm_" + artifact_id


def test_validation_invalid_artifact_id_empty_raises():
    with pytest.raises(NotebookLMSerializationError) as excinfo:
        minimal_record(artifact_id="")
    assert_error_class(excinfo, "invalid_artifact_id")


def test_validation_invalid_kind_raises():
    with pytest.raises(NotebookLMSerializationError) as excinfo:
        minimal_record(kind="not_an_enum")
    assert_error_class(excinfo, "invalid_kind")


def test_validation_naive_captured_at_raises():
    with pytest.raises(NotebookLMSerializationError) as excinfo:
        minimal_record(captured_at=datetime(2026, 5, 14, 12, 0, 0))
    assert_error_class(excinfo, "naive_captured_at")


def test_validation_local_path_missing_raises():
    with pytest.raises(NotebookLMSerializationError) as excinfo:
        minimal_record(local_path=Path("/tmp/nonexistent_xyz_d502"))
    assert_error_class(excinfo, "local_path_missing")


def test_validation_invalid_content_hash_raises():
    with pytest.raises(NotebookLMSerializationError) as excinfo:
        minimal_record(content_hash="md5:abc")
    assert_error_class(excinfo, "invalid_content_hash")


def test_validation_invalid_run_id_raises():
    with pytest.raises(NotebookLMSerializationError) as excinfo:
        minimal_record(retrieved_by_run_id="42")
    assert_error_class(excinfo, "invalid_run_id")


def test_validation_title_whitespace_only_raises():
    with pytest.raises(NotebookLMSerializationError) as excinfo:
        minimal_record(title="   ")
    assert_error_class(excinfo, "title_empty")


def test_validation_title_empty_string_raises():
    with pytest.raises(NotebookLMSerializationError) as excinfo:
        minimal_record(title="")
    assert_error_class(excinfo, "title_empty")


def test_output_validates_against_frozen_schema(tmp_path):
    schema = load_source_record_schema()
    validator = jsonschema.Draft7Validator(schema)
    minimal = minimal_record()

    local_path = tmp_path / "artifact.bin"
    local_path.touch()
    maximal = minimal_record(
        title="Custom",
        retrieved_by_run_id="run_test_42",
        local_path=local_path,
        content_hash="sha256:" + "a" * 64,
    )

    for record in (minimal, maximal):
        errors = sorted(validator.iter_errors(record), key=lambda error: error.path)
        assert errors == []


def test_output_keys_subset_of_schema_properties():
    schema = load_source_record_schema()
    assert set(minimal_record().keys()) <= set(schema["properties"].keys())


def test_output_always_contains_10_required():
    schema = load_source_record_schema()
    assert set(minimal_record().keys()) >= set(schema["required"])


def test_serialization_error_inherits_pool_error():
    assert issubclass(NotebookLMSerializationError, NotebookLMPoolError)


def test_error_class_attribute_present():
    error = NotebookLMSerializationError(error_class="invalid_kind", detail="x")
    assert error.error_class == "invalid_kind"
    assert error.detail == "x"

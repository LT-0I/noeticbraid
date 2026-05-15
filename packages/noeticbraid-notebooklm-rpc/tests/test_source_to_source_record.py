from __future__ import annotations

import json
import warnings
from datetime import datetime, timedelta, timezone, tzinfo
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from notebooklm import Source, SourceStatus, SourceType
from notebooklm.types import UnknownTypeWarning, _SOURCE_TYPE_CODE_MAP

from noeticbraid.tools.notebooklm_rpc import (
    SOURCE_TYPE_TO_TAG,
    NotebookLMSourceError,
    source_to_source_record,
)


AWARE_UTC = datetime(2026, 5, 14, 12, 0, 0, tzinfo=timezone.utc)
UNMAPPED_SOURCE_TYPES = {
    SourceType.UNKNOWN,
    SourceType.GOOGLE_DRIVE_AUDIO,
    SourceType.GOOGLE_DRIVE_VIDEO,
}
SOURCE_TYPE_TO_CODE = {source_type: code for code, source_type in _SOURCE_TYPE_CODE_MAP.items()}


class PlusSeven(tzinfo):
    def utcoffset(self, dt):
        return timedelta(hours=7)

    def dst(self, dt):
        return timedelta(0)


def make_source(**overrides: Any) -> Source:
    params = {
        "id": "src_1",
        "title": "X",
        "url": "",
        "_type_code": 3,
        "created_at": AWARE_UTC,
        "status": SourceStatus.READY,
    }
    params.update(overrides)
    return Source(**params)


def source_record_with_warning_filter(source: Source, **kwargs: Any) -> dict[str, Any]:
    params = {"captured_at": AWARE_UTC}
    params.update(kwargs)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UnknownTypeWarning)
        return source_to_source_record(source, **params)


def minimal_record(**overrides: Any) -> dict[str, Any]:
    params = {"source": make_source(), "captured_at": AWARE_UTC}
    params.update(overrides)
    return source_record_with_warning_filter(**params)


def assert_error_class(excinfo, error_class: str):
    assert excinfo.value.error_class == error_class
    assert str(excinfo.value).startswith(f"{error_class}: ")


def load_source_record_schema() -> dict[str, Any]:
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
        pytest.fail("source_record_note.schema.json not reachable; obsidian package required for sser-3a")
    return json.loads(schema_path.read_text())


def test_minimal_required_only():
    record = minimal_record()
    assert record == {
        "nb_type": "source_record",
        "schema_version": "obsidian-hub-0.1",
        "contract_version": "1.3.0",
        "source_ref_id": "source_notebooklm_source_src_1",
        "source_type": "paper",
        "title": "X",
        "captured_at": "2026-05-14T12:00:00+00:00",
        "quality_score": "unknown",
        "relevance_score": "unknown",
        "tags": ["noeticbraid/notebooklm/source/pdf"],
        "source_fingerprint": "notebooklm_source:src_1",
    }
    assert len(record) == 11
    assert "canonical_url" not in record
    assert "external_url" not in record


def test_source_ref_id_format():
    assert minimal_record()["source_ref_id"] == "source_notebooklm_source_src_1"


def test_source_fingerprint_format():
    assert minimal_record()["source_fingerprint"] == "notebooklm_source:src_1"


def test_pdf_maps_to_paper():
    assert minimal_record(source=make_source(_type_code=3))["source_type"] == "paper"


def test_web_page_maps_to_web_page():
    assert minimal_record(source=make_source(_type_code=5))["source_type"] == "web_page"


def test_youtube_maps_to_web_page():
    assert minimal_record(source=make_source(_type_code=9))["source_type"] == "web_page"


def test_epub_maps_to_paper():
    assert minimal_record(source=make_source(_type_code=17))["source_type"] == "paper"


def test_unrecognized_code_falls_back_to_user_note():
    record = minimal_record(source=make_source(_type_code=9999))
    assert record["source_type"] == "user_note"


@pytest.mark.parametrize("source_type", list(SourceType))
def test_tag_per_source_type(source_type: SourceType):
    type_code = 9999 if source_type in UNMAPPED_SOURCE_TYPES else SOURCE_TYPE_TO_CODE[source_type]
    record = minimal_record(source=make_source(_type_code=type_code))
    resolved_kind = SourceType.UNKNOWN if source_type in UNMAPPED_SOURCE_TYPES else source_type
    assert record["tags"] == [SOURCE_TYPE_TO_TAG[resolved_kind]]


def test_url_populates_canonical_and_external():
    record = minimal_record(source=make_source(url="https://example.com"))
    assert record["canonical_url"] == "https://example.com"
    assert record["external_url"] == "https://example.com"


def test_empty_url_omits_url_fields():
    record = minimal_record(source=make_source(url=""))
    assert "canonical_url" not in record
    assert "external_url" not in record


def test_none_url_omits_url_fields():
    record = minimal_record(source=make_source(url=None))
    assert "canonical_url" not in record
    assert "external_url" not in record


def test_title_override_wins():
    assert minimal_record(title_override="Custom")["title"] == "Custom"


def test_title_fallback_to_source_title():
    source = make_source(title="Source Title")
    assert minimal_record(source=source, title_override=None)["title"] == source.title


def test_title_truncation_to_512():
    record = minimal_record(source=make_source(title="x" * 600))
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
    tmp_file = tmp_path / "source.pdf"
    tmp_file.touch()
    record = minimal_record(local_path=tmp_file)
    assert record["local_path"] == str(tmp_file)


def test_optional_content_hash_passthrough():
    content_hash = "sha256:" + "c" * 64
    record = minimal_record(content_hash=content_hash)
    assert record["content_hash"] == content_hash


def test_optional_retrieved_by_run_id_passthrough():
    record = minimal_record(retrieved_by_run_id="run_x")
    assert record["retrieved_by_run_id"] == "run_x"


def test_never_emitted_fields_absent():
    never = {"source_ref", "author", "evidence_role", "used_for_purpose"}
    assert never.isdisjoint(minimal_record().keys())


def test_validation_invalid_source_id_chars_raises():
    with pytest.raises(NotebookLMSourceError) as excinfo:
        minimal_record(source=make_source(id="bad-id!"))
    assert_error_class(excinfo, "invalid_source_id")


def test_validation_source_id_too_long_raises():
    with pytest.raises(NotebookLMSourceError) as excinfo:
        minimal_record(source=make_source(id="a" * 104))
    assert_error_class(excinfo, "invalid_source_id")


def test_validation_source_id_boundary_103_passes():
    source_id = "a" * 103
    record = minimal_record(source=make_source(id=source_id))
    assert record["source_ref_id"] == "source_notebooklm_source_" + source_id


def test_validation_naive_captured_at_raises():
    with pytest.raises(NotebookLMSourceError) as excinfo:
        minimal_record(captured_at=datetime.utcnow())
    assert_error_class(excinfo, "naive_captured_at")


def test_unmapped_type_code_does_not_raise():
    record = minimal_record(source=make_source(_type_code=9999))
    assert record["source_type"] == "user_note"


def test_validation_local_path_missing_raises():
    with pytest.raises(NotebookLMSourceError) as excinfo:
        minimal_record(local_path=Path("/tmp/nonexistent_d504"))
    assert_error_class(excinfo, "local_path_missing")


def test_validation_invalid_content_hash_raises():
    with pytest.raises(NotebookLMSourceError) as excinfo:
        minimal_record(content_hash="md5:abc")
    assert_error_class(excinfo, "invalid_content_hash")


def test_validation_invalid_run_id_raises():
    with pytest.raises(NotebookLMSourceError) as excinfo:
        minimal_record(retrieved_by_run_id="42")
    assert_error_class(excinfo, "invalid_run_id")


def test_validation_title_empty_raises():
    with pytest.raises(NotebookLMSourceError) as excinfo:
        minimal_record(source=make_source(title="   "), title_override=None)
    assert_error_class(excinfo, "title_empty")


def test_output_validates_against_frozen_schema(tmp_path: Path):
    schema = load_source_record_schema()
    validator = jsonschema.Draft7Validator(schema)
    tmp_file = tmp_path / "source.pdf"
    tmp_file.touch()
    minimal = minimal_record()
    with_url = minimal_record(source=make_source(url="https://example.com"))
    with_optionals = minimal_record(
        local_path=tmp_file,
        content_hash="sha256:" + "c" * 64,
        retrieved_by_run_id="run_test_42",
    )

    for record in (minimal, with_url, with_optionals):
        errors = sorted(validator.iter_errors(record), key=lambda error: error.path)
        assert errors == []

from __future__ import annotations

import warnings
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable

import jsonschema
import pytest
from notebooklm import Note, Source, SourceStatus

from noeticbraid.tools.notebooklm_rpc import (
    ArtifactKind,
    artifact_to_source_record,
    notebook_to_source_record,
    note_to_source_record,
    source_to_source_record,
)
from noeticbraid_obsidian import WriteResult, default_settings, ingest_source_record
from noeticbraid_obsidian.frontmatter import extract_frontmatter
from noeticbraid_obsidian.path_policy import PathPolicyError
from noeticbraid_obsidian.writer import WritePolicyViolation


AWARE_UTC = datetime(2026, 5, 14, 12, 0, 0, tzinfo=timezone.utc)


@dataclass
class StubNotebook:
    id: str = "ing1n_nb"
    title: str = "Ingest Notebook"
    created_at: datetime | None = None
    sources_count: int = 0
    is_owner: bool = True


def minimal_record(**overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "nb_type": "source_record",
        "schema_version": "obsidian-hub-0.1",
        "contract_version": "1.3.0",
        "source_ref_id": "source_ingest_001",
        "source_type": "web_page",
        "title": "Ingest Source",
        "captured_at": "2026-05-14T12:00:00+00:00",
        "quality_score": "unknown",
        "relevance_score": "unknown",
        "tags": ["noeticbraid/source/test"],
    }
    record.update(overrides)
    return record


def test_dry_run_default_returns_preview_no_write(tmp_path: Path) -> None:
    result = ingest_source_record(minimal_record(), vault_root=tmp_path)

    assert result.written is False
    assert result.dry_run is True
    assert result.preview_text.startswith("---\n")
    assert not (tmp_path / result.relative_path).exists()
    assert list(tmp_path.iterdir()) == []


def test_live_mode_creates_file_at_policy_path(tmp_path: Path) -> None:
    result = ingest_source_record(
        minimal_record(),
        vault_root=tmp_path,
        settings=default_settings(write_mode="live"),
    )

    expected = tmp_path / "NoeticBraid" / "30_run_ledger" / "20_sources" / "2026" / "05" / "source_ingest_001.md"
    assert result.written is True
    assert result.dry_run is False
    assert result.absolute_path == expected
    assert result.relative_path == "NoeticBraid/30_run_ledger/20_sources/2026/05/source_ingest_001.md"
    assert expected.exists()
    assert expected.read_text(encoding="utf-8") == result.preview_text


def test_create_only_second_ingest_raises(tmp_path: Path) -> None:
    settings = default_settings(write_mode="live")
    record = minimal_record()

    ingest_source_record(record, vault_root=tmp_path, settings=settings)
    with pytest.raises(WritePolicyViolation):
        ingest_source_record(record, vault_root=tmp_path, settings=settings)


def test_record_id_is_source_ref_id(tmp_path: Path) -> None:
    record = minimal_record(source_ref_id="source_recordid_042")

    result = ingest_source_record(record, vault_root=tmp_path)

    assert PurePosixPath(result.relative_path).name == "source_recordid_042.md"


def test_date_derived_from_captured_at(tmp_path: Path) -> None:
    record = minimal_record(captured_at="2026-05-14T23:59:00+00:00")

    result = ingest_source_record(record, vault_root=tmp_path)

    assert "/2026/05/" in f"/{result.relative_path}"


def test_invalid_record_missing_required_raises(tmp_path: Path) -> None:
    record = minimal_record()
    del record["source_ref_id"]

    with pytest.raises(jsonschema.ValidationError):
        ingest_source_record(record, vault_root=tmp_path)


def test_invalid_source_type_enum_raises(tmp_path: Path) -> None:
    with pytest.raises(jsonschema.ValidationError):
        ingest_source_record(minimal_record(source_type="bogus"), vault_root=tmp_path)


def test_credential_url_rejected_by_schema(tmp_path: Path) -> None:
    record = minimal_record(canonical_url="https://example.com/page?token=secret")

    with pytest.raises(jsonschema.ValidationError):
        ingest_source_record(record, vault_root=tmp_path)


def test_naive_or_bad_captured_at_date_raises(tmp_path: Path) -> None:
    record = minimal_record(captured_at="not-a-date")

    with pytest.raises(PathPolicyError):
        ingest_source_record(record, vault_root=tmp_path)


def test_path_fragment_in_source_ref_id_rejected(tmp_path: Path) -> None:
    record = minimal_record(source_ref_id="../escape")

    with pytest.raises(jsonschema.ValidationError):
        ingest_source_record(record, vault_root=tmp_path)


def test_never_writes_user_raw(tmp_path: Path) -> None:
    result = ingest_source_record(minimal_record(), vault_root=tmp_path)

    assert result.relative_path.startswith("NoeticBraid/30_run_ledger/20_sources/")
    assert "NoeticBraid/20_episodic_memory/10_user_raw/" not in result.relative_path


def test_body_passthrough(tmp_path: Path) -> None:
    with_body = ingest_source_record(minimal_record(), vault_root=tmp_path, body="hello")
    default_body = ingest_source_record(minimal_record(source_ref_id="source_ingest_002"), vault_root=tmp_path)

    _frontmatter, body = extract_frontmatter(with_body.preview_text)
    _default_frontmatter, default_rendered_body = extract_frontmatter(default_body.preview_text)
    assert "hello" in with_body.preview_text
    assert body == "# Ingest Source\n\nhello"
    assert default_rendered_body == "# Ingest Source"


def test_project_passthrough(tmp_path: Path) -> None:
    record = minimal_record()

    default_project = ingest_source_record(record, vault_root=tmp_path)
    explicit_project = ingest_source_record(record, vault_root=tmp_path, project="projX")

    assert explicit_project.relative_path == default_project.relative_path


def test_all_d5_serializer_outputs_ingestible(tmp_path: Path) -> None:
    serializers: list[tuple[str, Callable[[], dict[str, Any]]]] = [
        (
            "artifact",
            lambda: artifact_to_source_record(
                artifact_id="ing1n_art",
                kind=ArtifactKind.REPORT,
                captured_at=AWARE_UTC,
            ),
        ),
        (
            "notebook",
            lambda: notebook_to_source_record(
                StubNotebook(),
                captured_at=AWARE_UTC,
            ),
        ),
        (
            "source",
            lambda: source_to_source_record(
                Source(
                    id="ing1n_src",
                    title="Ingest Source Item",
                    url="",
                    _type_code=3,
                    created_at=AWARE_UTC,
                    status=SourceStatus.READY,
                ),
                captured_at=AWARE_UTC,
            ),
        ),
        (
            "note",
            lambda: note_to_source_record(
                Note(
                    id="ing1n_note",
                    notebook_id="ing1n_nb",
                    title="Ingest Note",
                    content="...",
                    created_at=AWARE_UTC,
                ),
                captured_at=AWARE_UTC,
            ),
        ),
    ]

    for name, serialize in serializers:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            record = serialize()
        result = ingest_source_record(record, vault_root=tmp_path, body=f"{name} body")
        assert result.written is False
        assert result.dry_run is True
        assert result.preview_text.startswith("---\n")


def test_returns_write_result_type(tmp_path: Path) -> None:
    result = ingest_source_record(minimal_record(), vault_root=tmp_path)

    assert isinstance(result, WriteResult)
    assert result.relative_path
    assert result.written is False
    assert result.dry_run is True
    assert result.preview_text.startswith("---\n")

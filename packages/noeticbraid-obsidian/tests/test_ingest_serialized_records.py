from __future__ import annotations

import warnings
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator

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
from noeticbraid_obsidian import IngestSummary, default_settings, ingest_serialized_records
from noeticbraid_obsidian.errors import SettingsError
from noeticbraid_obsidian.writer import WritePolicyViolation


AWARE_UTC = datetime(2026, 5, 14, 12, 0, 0, tzinfo=timezone.utc)


@dataclass
class StubNotebook:
    id: str = "isr1k_nb"
    title: str = "Batch Notebook"
    created_at: datetime | None = None
    sources_count: int = 0
    is_owner: bool = True


class ExplodingRecords:
    def __init__(self) -> None:
        self.iterated = False

    def __iter__(self) -> Iterator[dict[str, Any]]:
        self.iterated = True
        raise AssertionError("records must not be iterated")
        yield {}


def minimal_record(**overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "nb_type": "source_record",
        "schema_version": "obsidian-hub-0.1",
        "contract_version": "1.3.0",
        "source_ref_id": "source_isr_001",
        "source_type": "web_page",
        "title": "Batch Ingest Source",
        "captured_at": "2026-05-14T12:00:00+00:00",
        "quality_score": "unknown",
        "relevance_score": "unknown",
        "tags": ["noeticbraid/source/test"],
    }
    record.update(overrides)
    return record


def record_path(vault_root: Path, record: dict[str, Any]) -> Path:
    year, month, _day = record["captured_at"][:10].split("-")
    return vault_root / "NoeticBraid" / "30_run_ledger" / "20_sources" / year / month / f"{record['source_ref_id']}.md"


def test_empty_iterable_returns_zero_summary(tmp_path: Path) -> None:
    summary = ingest_serialized_records([], vault_root=tmp_path)

    assert summary == IngestSummary(0, 0, 0, ())


def test_single_record_dry_run_default(tmp_path: Path) -> None:
    summary = ingest_serialized_records([minimal_record()], vault_root=tmp_path, settings=default_settings())

    assert summary.dry_run == 1
    assert summary.written == 0
    assert summary.skipped == 0
    assert len(summary.results) == 1
    assert summary.results[0].dry_run is True


def test_multiple_records_order_preserved(tmp_path: Path) -> None:
    records = [
        minimal_record(source_ref_id="source_isr_order_a"),
        minimal_record(source_ref_id="source_isr_order_b"),
        minimal_record(source_ref_id="source_isr_order_c"),
    ]

    summary = ingest_serialized_records(records, vault_root=tmp_path)

    assert [Path(result.relative_path).stem for result in summary.results] == [
        record["source_ref_id"] for record in records
    ]
    assert summary.dry_run == len(records)
    assert summary.written == 0
    assert summary.skipped == 0


def test_vault_root_none_resolves_from_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OBSIDIAN_HUB_VAULT_ROOT", str(tmp_path))

    summary = ingest_serialized_records([minimal_record(source_ref_id="source_isr_env")], vault_root=None)

    assert summary.dry_run == 1
    assert summary.results[0].absolute_path == record_path(tmp_path, minimal_record(source_ref_id="source_isr_env"))


def test_vault_root_none_missing_env_raises_settingserror(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OBSIDIAN_HUB_VAULT_ROOT", raising=False)

    with pytest.raises(SettingsError):
        ingest_serialized_records([minimal_record(source_ref_id="source_isr_missing_env")], vault_root=None)


def test_on_existing_skip_idempotent_reingest(tmp_path: Path) -> None:
    settings = default_settings(write_mode="live")
    existing = minimal_record(source_ref_id="source_isr_skip_existing")
    new_record = minimal_record(source_ref_id="source_isr_skip_new")
    ingest_serialized_records([existing], vault_root=tmp_path, settings=settings)
    existing_path = record_path(tmp_path, existing)
    existing_path.write_text("manual preservation\n", encoding="utf-8")
    before = existing_path.read_text(encoding="utf-8")

    summary = ingest_serialized_records([existing, new_record], vault_root=tmp_path, settings=settings)

    assert summary.written == 1
    assert summary.skipped == 1
    assert summary.dry_run == 0
    assert len(summary.results) == 1
    assert Path(summary.results[0].relative_path).stem == new_record["source_ref_id"]
    assert existing_path.read_text(encoding="utf-8") == before


def test_on_existing_raise_propagates_writepolicyviolation(tmp_path: Path) -> None:
    settings = default_settings(write_mode="live")
    existing = minimal_record(source_ref_id="source_isr_raise_existing")
    fresh = minimal_record(source_ref_id="source_isr_raise_fresh")
    ingest_serialized_records([existing], vault_root=tmp_path, settings=settings)

    with pytest.raises(WritePolicyViolation):
        ingest_serialized_records([fresh, existing], vault_root=tmp_path, settings=settings, on_existing="raise")

    assert record_path(tmp_path, fresh).exists()
    assert record_path(tmp_path, existing).exists()


def test_invalid_on_existing_raises_valueerror(tmp_path: Path) -> None:
    records = ExplodingRecords()

    with pytest.raises(ValueError):
        ingest_serialized_records(records, vault_root=tmp_path, on_existing="bogus")

    assert records.iterated is False


def test_invalid_record_propagates_fail_fast(tmp_path: Path) -> None:
    settings = default_settings(write_mode="live")
    before = minimal_record(source_ref_id="source_isr_fail_before")
    invalid = minimal_record(source_ref_id="source_isr_fail_invalid")
    del invalid["source_ref_id"]
    after = minimal_record(source_ref_id="source_isr_fail_after")
    events: list[str] = []

    def records() -> Iterator[dict[str, Any]]:
        events.append("before")
        yield before
        events.append("invalid")
        yield invalid
        events.append("after")
        yield after

    with pytest.raises(jsonschema.ValidationError):
        ingest_serialized_records(records(), vault_root=tmp_path, settings=settings)

    assert events == ["before", "invalid"]
    assert record_path(tmp_path, before).exists()
    assert not record_path(tmp_path, after).exists()


def test_generator_input_single_pass_consumed(tmp_path: Path) -> None:
    records = (
        minimal_record(source_ref_id=f"source_isr_generator_{index}")
        for index in range(2)
    )

    summary = ingest_serialized_records(records, vault_root=tmp_path)

    assert summary.dry_run == 2
    assert [Path(result.relative_path).stem for result in summary.results] == [
        "source_isr_generator_0",
        "source_isr_generator_1",
    ]


def test_all_four_d5_serializers_batch_ingestible(tmp_path: Path) -> None:
    serializers: list[tuple[str, Callable[[], dict[str, Any]]]] = [
        (
            "artifact",
            lambda: artifact_to_source_record(
                artifact_id="isr1k_art",
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
                    id="isr1k_src",
                    title="Batch Source Item",
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
                    id="isr1k_note",
                    notebook_id="isr1k_nb",
                    title="Batch Note",
                    content="...",
                    created_at=AWARE_UTC,
                ),
                captured_at=AWARE_UTC,
            ),
        ),
    ]
    records: list[dict[str, Any]] = []

    for _name, serialize in serializers:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            records.append(serialize())

    summary = ingest_serialized_records(records, vault_root=tmp_path)

    assert summary.dry_run == 4
    assert summary.written == 0
    assert summary.skipped == 0
    assert len(summary.results) == 4
    expected_prefix = str(tmp_path / "NoeticBraid" / "30_run_ledger" / "20_sources") + "/"
    for result in summary.results:
        assert str(result.absolute_path).startswith(expected_prefix)
        assert result.relative_path.startswith("NoeticBraid/30_run_ledger/20_sources/")


def test_summary_counts_invariant_live_written_skipped(tmp_path: Path) -> None:
    settings = default_settings(write_mode="live")
    existing = minimal_record(source_ref_id="source_isr_invariant_existing")
    new_record = minimal_record(source_ref_id="source_isr_invariant_new")
    ingest_serialized_records([existing], vault_root=tmp_path, settings=settings)

    summary = ingest_serialized_records([new_record, existing], vault_root=tmp_path, settings=settings)

    assert summary.written == 1
    assert summary.skipped == 1
    assert summary.dry_run == 0
    assert len(summary.results) == 1
    assert summary.written + summary.dry_run == len(summary.results)

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from noeticbraid_core.user_growth_llmwiki import (
    LLMWikiSourceRecord,
    LLMWikiSQLiteStore,
    VaultScanConfig,
    VaultScanner,
    build_content_reuse_plan,
    build_report_inputs,
    generate_digestion_candidates,
    generate_side_note_candidates,
    generate_structure_suggestions,
    sha256_content,
    source_record_from_text,
)

FIXED_NOW = datetime(2026, 5, 2, 12, 0, tzinfo=timezone.utc)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _profile(root: Path):
    _write(root / "Projects" / "Orphan" / "a.md", "First orphan note.\n")
    _write(root / "Projects" / "Orphan" / "b.md", "Second orphan note.\n")
    _write(root / "Notes" / "AI" / "scratch.md", "AI-ish folder without explicit zone.\n")
    return VaultScanner(VaultScanConfig(approved_fixture_roots=(root,))).scan(root, scanned_at=FIXED_NOW)


def test_content_reuse_plan_separates_layers_and_logs() -> None:
    record = source_record_from_text(
        origin="file:fixtures/source-note.md",
        text="fixture source text",
        layer="source",
        ingested_at=FIXED_NOW,
        relative_path="fixtures/source-note.md",
        title="Source Note",
        provenance={"fixture": "true"},
    )

    plan = build_content_reuse_plan([record], created_at=FIXED_NOW)

    assert record.record_id.startswith("source_")
    assert record.content_hash.startswith("sha256:")
    assert record.layer == "source"
    assert plan.layer_model == ["raw/source", "compiled/wiki", "output", "log"]
    assert [candidate.layer for candidate in plan.compiled_candidates] == ["wiki"]
    assert [candidate.layer for candidate in plan.output_candidates] == ["output"]
    assert {log.event_type for log in plan.log_records} == {"ingestion", "compilation", "output"}
    assert plan.audit_flags == []


def test_source_record_model_rejects_non_raw_source_layers() -> None:
    with pytest.raises(ValueError, match="raw/source"):
        LLMWikiSourceRecord(
            record_id="source_badlayer",
            origin="file:fixtures/output.md",
            content_hash=sha256_content("compiled output must use a candidate model"),
            layer="output",
            ingested_at=FIXED_NOW,
            relative_path="fixtures/output.md",
            title="Output",
        )


def test_candidate_generation_is_evidence_bound_and_candidate_only(tmp_path: Path) -> None:
    profile = _profile(tmp_path)
    record = source_record_from_text(
        origin="file:fixtures/profile-summary.md",
        text=profile.to_deterministic_json(),
        layer="source",
        ingested_at=FIXED_NOW,
        relative_path="fixtures/profile-summary.md",
        title="Profile Summary",
    )

    suggestions = generate_structure_suggestions(profile, created_at=FIXED_NOW, source_refs=[record.record_id])
    side_notes = generate_side_note_candidates(profile, [record], created_at=FIXED_NOW)
    digestion = generate_digestion_candidates(side_notes, created_at=FIXED_NOW)
    reports = build_report_inputs(side_notes, digestion, created_at=FIXED_NOW)

    assert suggestions
    assert all(suggestion.status == "candidate" for suggestion in suggestions)
    assert all(suggestion.to_writer_handoff_request()["no_user_original_mutation"] is True for suggestion in suggestions)
    assert all(suggestion.source_refs == [record.record_id] for suggestion in suggestions)
    assert all(note.evidence_refs for note in side_notes)
    assert all(note.owner == "noeticbraid" for note in side_notes)
    assert all(note.claim.startswith("Hypothesis:") for note in side_notes if note.note_type == "hypothesis")
    assert all(note.claim.startswith("Challenge:") for note in side_notes if note.note_type == "challenge")
    assert all(item.status == "open" for item in digestion)
    assert {item.side_note_candidate_id for item in digestion} == {note.candidate_id for note in side_notes}
    assert {report.period for report in reports} == {"daily", "weekly", "monthly"}
    for report in reports:
        assert all(note.note_type == "fact" for note in report.facts)
        assert all(note.note_type == "hypothesis" for note in report.hypotheses)
        assert all(note.note_type == "challenge" for note in report.challenges)
        assert all(note.note_type == "action" for note in report.actions)
        assert report.digestion_refs


def test_default_structure_suggestions_materialize_backing_profile_source_record(tmp_path: Path) -> None:
    profile = _profile(tmp_path)
    materialized: list[LLMWikiSourceRecord] = []

    suggestions = generate_structure_suggestions(
        profile,
        created_at=FIXED_NOW,
        materialized_source_records=materialized,
    )

    source_record_ids = {record.record_id for record in materialized}
    assert source_record_ids == {profile.profile_source_ref()}
    assert suggestions
    assert all(set(suggestion.source_refs) <= source_record_ids for suggestion in suggestions)
    assert all(record.layer in {"raw", "source"} for record in materialized)


def test_sqlite_persistence_round_trips_metadata_without_private_content(tmp_path: Path) -> None:
    record = source_record_from_text(
        origin="file:fixtures/source-note.md",
        text="raw fixture body that must not be stored",
        layer="source",
        ingested_at=FIXED_NOW,
        relative_path="fixtures/source-note.md",
        title="Source Note",
        provenance={"fixture": "true"},
    )
    plan = build_content_reuse_plan([record], created_at=FIXED_NOW)
    db_path = tmp_path / "module.sqlite3"
    store = LLMWikiSQLiteStore(db_path)

    store.put_source_record(record)
    for log in plan.log_records:
        store.append_activity(log)

    assert store.get_source_record(record.record_id) == record
    assert list(store.iter_source_records()) == [record]
    assert [log.event_id for log in store.iter_activity()] == [log.event_id for log in sorted(plan.log_records, key=lambda item: (item.created_at, item.event_id))]

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT origin, content_hash, provenance_json FROM source_records").fetchall()
    flattened = "\n".join(str(row) for row in rows)
    assert "raw fixture body" not in flattened
    assert "sha256:" in flattened


def test_sqlite_persistence_rejects_duplicate_source_record_ids_and_log_events(tmp_path: Path) -> None:
    record = source_record_from_text(
        origin="file:fixtures/source-note.md",
        text="raw fixture body that must not be stored",
        layer="source",
        ingested_at=FIXED_NOW,
        relative_path="fixtures/source-note.md",
        title="Source Note",
    )
    plan = build_content_reuse_plan([record], created_at=FIXED_NOW)
    store = LLMWikiSQLiteStore(tmp_path / "module.sqlite3")

    store.put_source_record(record)
    with pytest.raises(sqlite3.IntegrityError):
        store.put_source_record(record)

    log_record = plan.log_records[0]
    store.append_activity(log_record)
    with pytest.raises(sqlite3.IntegrityError):
        store.append_activity(log_record)

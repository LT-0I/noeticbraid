from __future__ import annotations

from noeticbraid.tools.notebooklm_bridge import to_source_records
from noeticbraid.tools.notebooklm_bridge._runlog import build_event
from noeticbraid.tools.notebooklm_bridge._types import OperationEvent


def test_to_source_records_matches_frozen_source_record_contract(source_record_contract, phase1_2_contract_path) -> None:
    records = to_source_records("notebook_abc", "Briefing text", "run_123")

    assert len(records) == 1
    record = records[0]
    allowed = set(source_record_contract["properties"])
    required = set(source_record_contract["required"])

    assert set(record) <= allowed
    assert required <= set(record)
    assert record["source_ref_id"].startswith("source_")
    assert record["retrieved_by_run_id"] == "run_123"
    assert record["source_fingerprint"].startswith("fingerprint_")
    assert record["source_type"] == "ai_output"
    assert record["evidence_role"] == "source_grounding"
    assert record["used_for_purpose"] == "source_grounding"
    assert record["quality_score"] in source_record_contract["properties"]["quality_score"]["enum"]
    assert record["relevance_score"] in source_record_contract["properties"]["relevance_score"]["enum"]
    assert record["content_hash"].startswith("sha256:")


def test_build_event_matches_frozen_run_record_contract(run_record_contract) -> None:
    event = build_event(
        OperationEvent(
            operation="push_sources",
            status="succeeded",
            notebook_id="notebook_abc",
            run_id="run_123",
            task_id="task_456",
            source_refs=["source_nb_abc"],
            artifact_refs=["artifact_notebooklm_notebook_abc"],
        )
    )

    allowed = set(run_record_contract["properties"])
    required = set(run_record_contract["required"])
    assert set(event) <= allowed
    assert required <= set(event)
    assert event["run_id"] == "run_123"
    assert event["task_id"] == "task_456"
    assert event["actor"] == "system"
    assert event["event_type"] in run_record_contract["properties"]["event_type"]["enum"]
    assert event["status"] == "recorded"
    assert event["source_refs"] == ["source_nb_abc"]
    assert event["artifact_refs"] == ["artifact_notebooklm_notebook_abc"]

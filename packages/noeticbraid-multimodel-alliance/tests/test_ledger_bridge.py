from __future__ import annotations

import json

import pytest

from noeticbraid.tools.multimodel_alliance.ledger_bridge import (
    ALLOWED_DEBATE_LOOP_EVENT_TYPES,
    LedgerBridgeError,
    build_run_record,
    record_debate_loop_ledger,
)


def test_ledger_bridge_uses_existing_event_types_only(tmp_path):
    path, records = record_debate_loop_ledger(
        tmp_path,
        run_id="run_ledger_bridge",
        task_id="task_ledger_bridge",
        route_id="route_ledger_bridge",
        debate_id="debate_ledger_bridge",
        convergence_id="convergence_ledger_bridge",
        candidate_ids=["memory_ledger_bridge"],
        model_refs=["model_claude_opus_4_7"],
        source_refs=["source_ledger_fixture"],
        artifact_refs=["artifact_route_ledger", "artifact_debate_ledger"],
        provider_mode="mock",
        decision_status="needs_more_evidence",
        blocked_decision_count=0,
    )

    assert {record["event_type"] for record in records} <= ALLOWED_DEBATE_LOOP_EVENT_TYPES
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert {row["event_type"] for row in rows} == {"artifact_created", "routing_advice_recorded", "lesson_candidate_created"}
    with pytest.raises(LedgerBridgeError):
        build_run_record(run_id="run_bad", task_id="task_bad", event_type="debate_started")


def test_ledger_bridge_records_sdd_and_artifact_refs(tmp_path):
    path, _records = record_debate_loop_ledger(
        tmp_path,
        run_id="run_ledger_sdd",
        task_id="task_ledger_sdd",
        route_id="route_ledger_sdd",
        debate_id="debate_ledger_sdd",
        convergence_id="convergence_ledger_sdd",
        candidate_ids=["memory_ledger_sdd"],
        model_refs=["model_claude_opus_4_7", "model_codex_gpt_5_5"],
        source_refs=["source_ledger_fixture"],
        artifact_refs=["artifact_route_sdd", "artifact_debate_sdd", "artifact_convergence_sdd"],
        provider_mode="mock",
        decision_status="needs_user_decision",
        blocked_decision_count=1,
    )
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

    assert all("artifact_route_sdd" in row["artifact_refs"] for row in rows)
    advice_rows = [row for row in rows if row["event_type"] == "routing_advice_recorded"]
    assert '"sdd_id":"SDD-D2-01"' in advice_rows[0]["routing_advice"]
    assert '"blocked_decision_count":1' in advice_rows[0]["routing_advice"]

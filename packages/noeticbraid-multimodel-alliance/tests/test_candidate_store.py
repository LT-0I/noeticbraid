from __future__ import annotations

import json
from pathlib import Path

import pytest

from noeticbraid.tools.multimodel_alliance.candidate_store import (
    CandidateStoreError,
    UPGRADE_RULE,
    append_candidate_record,
    build_debate_candidate,
    candidate_jsonl_path,
    validate_candidate_record,
)


def _candidate() -> dict:
    return build_debate_candidate(
        task_id="task_candidate_store",
        route_id="route_candidate_store",
        debate_id="debate_candidate_store",
        convergence_id="convergence_candidate_store",
        summary="Evidence-backed candidate summary.",
        source_refs=["source_candidate_fixture"],
        artifact_refs=["artifact_route_candidate", "artifact_debate_candidate"],
        model_refs=["model_claude_opus_4_7", "model_codex_gpt_5_5"],
        decision_status="needs_more_evidence",
        created_at="2026-05-12T00:00:00Z",
    )


def test_candidate_store_uses_state_root_candidate_jsonl(tmp_path):
    path = append_candidate_record(tmp_path, _candidate())

    assert path == candidate_jsonl_path(tmp_path)
    assert path == tmp_path / "state" / "program_memory" / "candidates" / "multimodel_debate_candidates.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["candidate_type"] == "program_memory_debate_lesson"


def test_candidate_store_rejects_confirmed_status():
    candidate = _candidate()
    candidate["status"] = "confirmed"

    with pytest.raises(CandidateStoreError, match="refuses non-candidate"):
        validate_candidate_record(candidate)


def test_candidate_store_rejects_raw_note_or_frozen_paths(tmp_path):
    with pytest.raises(CandidateStoreError, match="protected zone"):
        append_candidate_record(tmp_path / "raw_notes", _candidate())
    with pytest.raises(CandidateStoreError, match="protected zone"):
        append_candidate_record(tmp_path / "frozen", _candidate())


def test_candidate_store_emits_upgrade_rule_field(tmp_path):
    path = append_candidate_record(tmp_path, _candidate())
    row = json.loads(path.read_text(encoding="utf-8").splitlines()[0])

    assert row["upgrade_rule"] == UPGRADE_RULE
    assert "not rejected is never sufficient" in row["upgrade_rule"]

from __future__ import annotations

from pathlib import Path

import pytest

from noeticbraid.tools.multimodel_alliance.loop import DebateLoopError, run_debate_loop

ROOT = Path(__file__).resolve().parents[1]
TASK_CARD = ROOT / "examples" / "task_card_omc_ingest.json"


def test_omc_mock_loop_creates_route_debate_convergence(tmp_path):
    result = run_debate_loop(TASK_CARD, state_root=tmp_path / "state", artifact_root=tmp_path / "artifacts", mock_invocations=True)

    assert result["status"] == "completed"
    assert result["sdd_id"] == "SDD-D2-01"
    assert result["route_id"] == "route_omc_ingest_debate_loop"
    assert result["debate_id"] == "debate_omc_ingest_debate_loop"
    assert result["convergence_id"] == "convergence_omc_ingest_debate_loop"
    assert Path(result["artifact_paths"]["route"]).is_file()
    assert Path(result["artifact_paths"]["debate"]).is_file()
    assert Path(result["artifact_paths"]["convergence"]).is_file()
    assert Path(result["artifact_paths"]["convergence_markdown"]).is_file()
    assert Path(result["artifact_paths"]["candidate_jsonl"]).is_file()
    assert Path(result["artifact_paths"]["ledger_jsonl"]).is_file()


def test_loop_writes_program_memory_candidate_not_confirmed(tmp_path):
    result = run_debate_loop(TASK_CARD, state_root=tmp_path / "state", artifact_root=tmp_path / "artifacts")

    candidate = result["candidate"]
    assert candidate["status"] == "candidate"
    assert candidate["candidate_type"] == "program_memory_debate_lesson"
    assert "confirmed" not in Path(result["artifact_paths"]["candidate_jsonl"]).read_text(encoding="utf-8")
    assert "explicit user adoption OR reuse >=3" in candidate["upgrade_rule"]


def test_loop_blocks_majority_acceptance_on_critical_objection(tmp_path):
    manual = tmp_path / "critical_rounds.json"
    manual.write_text(
        """
        {
          "provider": "manual",
          "model_ref": "model_manual_provider",
          "role": "manual",
          "rounds": [
            {"role":"producer","artifact_ref":"artifact_manual_producer","verdict":"pass","summary":"producer passes","objections":[]},
            {"role":"adversary","artifact_ref":"artifact_manual_adversary","verdict":"fail","summary":"critical block","objections":[{"objection_id":"obj_manual_critical","severity":"critical","status":"needs_user_decision","summary":"User must decide this risk.","evidence_refs":["artifact_manual_adversary"]}]},
            {"role":"source_auditor","artifact_ref":"artifact_manual_audit","verdict":"pass","summary":"source audit passes","objections":[]}
          ]
        }
        """,
        encoding="utf-8",
    )
    result = run_debate_loop(
        {"task_id": "task_manual_critical", "trigger": "task_card", "source_refs": ["source_manual_fixture"]},
        state_root=tmp_path / "state",
        artifact_root=tmp_path / "artifacts",
        mock_invocations=False,
        manual_invocation_artifacts=[manual],
    )

    assert result["decision_status"] == "needs_user_decision"
    assert result["blocked_decision_count"] == 1
    assert result["convergence"]["user_decision_requirements"][0]["related_objection_refs"] == ["obj_manual_critical"]


def test_loop_requires_manual_trigger(tmp_path):
    with pytest.raises(DebateLoopError, match="manual user task-card trigger"):
        run_debate_loop(
            {"task_id": "task_cron_bad", "trigger": "cron", "source_refs": ["source_manual_fixture"]},
            state_root=tmp_path / "state",
            artifact_root=tmp_path / "artifacts",
        )


def test_loop_respects_three_to_five_round_cap_policy(tmp_path):
    rounds = [
        {"role": "producer", "artifact_ref": "artifact_cap_1", "summary": "r1", "objections": []},
        {"role": "adversary", "artifact_ref": "artifact_cap_2", "summary": "r2", "objections": []},
        {"role": "source_auditor", "artifact_ref": "artifact_cap_3", "summary": "r3", "objections": []},
        {"role": "producer", "artifact_ref": "artifact_cap_4", "summary": "r4", "objections": []},
        {"role": "adversary", "artifact_ref": "artifact_cap_5", "summary": "r5", "objections": []},
        {"role": "source_auditor", "artifact_ref": "artifact_cap_6", "summary": "r6", "objections": []},
    ]
    manual = tmp_path / "round_cap.json"
    manual.write_text('{"rounds": ' + __import__("json").dumps(rounds) + "}", encoding="utf-8")

    result = run_debate_loop(
        {"task_id": "task_round_cap", "trigger": "task_card", "source_refs": ["source_manual_fixture"]},
        state_root=tmp_path / "state",
        artifact_root=tmp_path / "artifacts",
        mock_invocations=False,
        manual_invocation_artifacts=[manual],
    )

    assert 3 <= result["round_count"] <= 5
    assert result["round_count"] == 3
    assert result["stopped_reason"] == "early_no_unresolved_high_critical"


def test_loop_uses_three_model_default_fixture(tmp_path):
    result = run_debate_loop(TASK_CARD, state_root=tmp_path / "state", artifact_root=tmp_path / "artifacts")

    assert [item["model_ref"] for item in result["route"]["selected_models"]] == [
        "model_claude_opus_4_7",
        "model_codex_gpt_5_5",
        "model_gemini_3_1_pro",
    ]
    assert [item["role"] for item in result["route"]["selected_models"]] == ["producer", "adversary", "source_auditor"]


def test_loop_early_stops_when_no_critical_objection(tmp_path):
    result = run_debate_loop(
        {"task_id": "task_early_stop", "trigger": "task_card", "source_refs": ["source_manual_fixture"]},
        state_root=tmp_path / "state",
        artifact_root=tmp_path / "artifacts",
    )

    # The packaged mock has exactly three rounds and no critical blocker; the loop does not pad toward five.
    assert result["round_count"] == 3
    assert result["round_count"] < 5


def test_loop_rejects_b1_detector_auto_trigger_in_d2_01(tmp_path):
    with pytest.raises(DebateLoopError, match="b-1 triggers are out of scope"):
        run_debate_loop(
            {"task_id": "task_b1_bad", "trigger": "task_card", "trigger_source": "b1_detector", "source_refs": ["source_manual_fixture"]},
            state_root=tmp_path / "state",
            artifact_root=tmp_path / "artifacts",
        )

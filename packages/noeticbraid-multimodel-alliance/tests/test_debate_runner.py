from __future__ import annotations

import json
from pathlib import Path

import pytest

from noeticbraid.tools.multimodel_alliance import route, run_debate, validate_debate_record
from noeticbraid.tools.multimodel_alliance.debate_runner import DebateError

FIXTURE_DIR = Path(__file__).parent.parent / "src" / "noeticbraid" / "tools" / "multimodel_alliance" / "fixtures"


def _make_minimal_route(route_type: str = "dual_review") -> dict:
    selected_by_route = {
        "dual_review": [
            ("model_test_producer", "producer"),
            ("model_test_reviewer_a", "reviewer"),
            ("model_test_reviewer_b", "reviewer"),
            ("model_test_convergence", "convergence_editor"),
        ],
        "multi_review": [
            ("model_test_producer", "producer"),
            ("model_test_reviewer", "reviewer"),
            ("model_test_adversary", "adversary"),
            ("model_test_verifier", "verifier"),
            ("model_test_convergence", "convergence_editor"),
        ],
    }
    risk_by_route = {"dual_review": "medium", "multi_review": "high"}
    capabilities_by_route = {
        "dual_review": ["planning", "writing", "code_review", "source_audit", "convergence"],
        "multi_review": ["writing", "code_review", "adversary", "verification", "convergence"],
    }
    selected = selected_by_route[route_type]
    return {
        "route_id": f"route_test_{route_type}",
        "task_id": f"task_test_{route_type}",
        "route_type": route_type,
        "trigger": "task_card",
        "risk_level": risk_by_route[route_type],
        "required_capabilities": capabilities_by_route[route_type],
        "selected_models": [
            {
                "model_ref": model_ref,
                "role": role,
                "invocation": "manual",
                "reason": f"{role} fixture participant.",
            }
            for model_ref, role in selected
        ],
        "rejected_models": [],
        "run_refs": [f"run_test_{route_type}"],
        "artifact_refs": [],
        "source_refs": [],
        "status": "selected",
        "rationale": f"Minimal {route_type} route for debate runner tests.",
    }


def _rounds_input_from_fixture_debate(fixture: dict) -> list[dict]:
    participant_roles = {
        participant["participant_id"]: participant["role"]
        for participant in fixture["debate"]["participants"]
    }
    return [
        {
            "role": participant_roles[round_record["participant_id"]],
            "artifact_ref": round_record["artifact_ref"],
            "round_type": round_record["round_type"],
            "verdict": round_record["verdict"],
            "summary": next(
                verdict["summary"]
                for verdict in fixture["debate"]["verdicts"]
                if verdict["participant_id"] == round_record["participant_id"]
            ),
            "objections": round_record["objections"],
        }
        for round_record in fixture["debate"]["rounds"]
    ]


def test_run_debate_builds_valid_debate_from_route_and_round_inputs():
    model_route = route(
        {
            "task_id": "task_prompt_cycle",
            "risk_hint": "medium",
            "required_capabilities": ["planning", "writing", "code_review", "source_audit", "convergence"],
        }
    )
    debate = run_debate(
        model_route,
        [
            {"role": "producer", "artifact_ref": "artifact_prompt_draft", "verdict": "informational", "summary": "Draft produced."},
            {
                "role": "reviewer",
                "artifact_ref": "artifact_review_a",
                "verdict": "concern",
                "summary": "Reviewer A found one issue.",
                "objections": [
                    {
                        "objection_id": "obj_prompt_inventory_missing",
                        "severity": "high",
                        "status": "accepted",
                        "summary": "Inventory evidence is required.",
                    }
                ],
            },
            {"role": "reviewer", "artifact_ref": "artifact_review_b", "verdict": "pass", "summary": "Reviewer B passes."},
        ],
    )
    validate_debate_record(debate, model_route, "generated_debate.json")
    assert debate["task_id"] == model_route["task_id"]
    assert debate["route_id"] == model_route["route_id"]
    assert len(debate["rounds"]) == 3
    assert debate["severity_summary"]["high"] == 1
    assert debate["unresolved_objections"] == []
    assert debate["status"] == "converged"


def test_run_debate_carries_unresolved_and_user_decision_objections():
    model_route = route(
        {
            "task_id": "task_disputed_convergence",
            "risk_hint": "disputed",
            "required_capabilities": ["planning", "code_review", "adversary", "verification", "convergence"],
        }
    )
    debate = run_debate(
        model_route,
        [
            {
                "role": "adversary",
                "artifact_ref": "artifact_review_block",
                "round_type": "adversarial_review",
                "verdict": "fail",
                "summary": "Policy conflict remains.",
                "objections": [
                    {
                        "objection_id": "obj_acceptance_without_user_decision",
                        "severity": "critical",
                        "status": "needs_user_decision",
                        "summary": "User must decide whether to accept the disputed scope.",
                    },
                    {
                        "objection_id": "obj_more_evidence_needed",
                        "severity": "high",
                        "status": "unresolved",
                        "summary": "Verifier evidence is missing.",
                    },
                ],
            }
        ],
    )
    validate_debate_record(debate, model_route, "generated_disputed_debate.json")
    assert set(debate["unresolved_objections"]) == {"obj_acceptance_without_user_decision", "obj_more_evidence_needed"}
    assert debate["status"] == "waiting_for_user"


def test_run_debate_rejects_unknown_role():
    model_route = route({"task_id": "task_prompt_cycle", "risk_hint": "medium"})
    with pytest.raises(DebateError):
        run_debate(model_route, [{"role": "ghost", "artifact_ref": "artifact_x", "summary": "bad"}])


def test_run_debate_logic_reviewer_fixture_reconstruction():
    """MUST-2 + T-B03: dual_review_prompt_cycle.json can drive a legal Debate."""
    fixture = json.loads((FIXTURE_DIR / "dual_review_prompt_cycle.json").read_text(encoding="utf-8"))
    route_record = fixture["model_route"]
    rounds_input = _rounds_input_from_fixture_debate(fixture)
    debate = run_debate(route_record, rounds_input)
    validate_debate_record(debate, route_record, "regenerated_dual_review.json")


def test_run_debate_preserves_objection_trace_fields():
    """MUST-5: raised_by/addressed_by survive objection normalization."""
    route_record = _make_minimal_route(route_type="dual_review")
    rounds_input = [
        {
            "round_index": 1,
            "role": "producer",
            "objections": [
                {
                    "objection_id": "obj_trace_probe",
                    "severity": "medium",
                    "status": "unresolved",
                    "summary": "needs traceability",
                    "evidence_refs": ["artifact_probe_review"],
                    "raised_by": "manual",
                    "addressed_by": "manual",
                }
            ],
        }
    ]
    debate = run_debate(route_record, rounds_input)
    obj = debate["rounds"][0]["objections"][0]
    assert obj["raised_by"] == "manual"
    assert obj["addressed_by"] == "manual"


def test_run_debate_objection_state_transition_via_addresses_ref():
    """MUST-6: later rounds can terminally address earlier unresolved objections."""
    route_record = _make_minimal_route(route_type="multi_review")
    rounds_input = [
        {
            "round_index": 1,
            "role": "reviewer",
            "objections": [
                {
                    "objection_id": "obj_initial_concern",
                    "severity": "high",
                    "status": "unresolved",
                    "summary": "needs evidence gate",
                    "evidence_refs": ["artifact_initial"],
                }
            ],
        },
        {
            "round_index": 2,
            "role": "producer",
            "objections": [
                {
                    "objection_id": "obj_resolution_response",
                    "severity": "high",
                    "status": "accepted",
                    "summary": "evidence gate added",
                    "evidence_refs": ["artifact_response"],
                    "addresses_objection_ref": "obj_initial_concern",
                }
            ],
        },
    ]
    debate = run_debate(route_record, rounds_input)
    assert "obj_initial_concern" not in debate.get("unresolved_objections", [])

from __future__ import annotations

from noeticbraid.tools.multimodel_alliance import converge, route, run_debate
from noeticbraid.tools.multimodel_alliance.validator import validate_convergence_record


def test_converge_accepts_handled_objections():
    model_route = route({"task_id": "task_prompt_cycle", "risk_hint": "medium"})
    debate = run_debate(
        model_route,
        [
            {"role": "producer", "artifact_ref": "artifact_prompt_draft", "summary": "Draft produced."},
            {
                "role": "reviewer",
                "artifact_ref": "artifact_review_a",
                "verdict": "concern",
                "summary": "Review found an accepted concern.",
                "objections": [
                    {
                        "objection_id": "obj_prompt_inventory_missing",
                        "severity": "high",
                        "status": "accepted",
                        "summary": "Inventory evidence is required.",
                    }
                ],
            },
        ],
    )
    convergence = converge(debate)
    validate_convergence_record(convergence, debate, "generated_convergence.json")
    assert convergence["decision_status"] == "accepted"
    assert [item["objection_id"] for item in convergence["accepted_objections"]] == ["obj_prompt_inventory_missing"]
    assert convergence["user_decision_requirements"] == []


def test_converge_carries_critical_disagreement_to_blocking_user_decision():
    model_route = route({"task_id": "task_disputed_convergence", "risk_hint": "disputed"})
    debate = run_debate(
        model_route,
        [
            {
                "role": "adversary",
                "artifact_ref": "artifact_review_block",
                "verdict": "fail",
                "summary": "Policy conflict remains.",
                "objections": [
                    {
                        "objection_id": "obj_acceptance_without_user_decision",
                        "severity": "critical",
                        "status": "needs_user_decision",
                        "summary": "User must decide disputed scope.",
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
    convergence = converge(debate)
    validate_convergence_record(convergence, debate, "generated_disputed_convergence.json")
    assert convergence["decision_status"] == "needs_user_decision"
    assert convergence["user_decision_requirements"][0]["blocking"] is True
    assert convergence["user_decision_requirements"][0]["related_objection_refs"] == ["obj_acceptance_without_user_decision"]
    carried = {item["objection_id"]: item["carried_to"] for item in convergence["unresolved_disagreements"]}
    assert carried["obj_acceptance_without_user_decision"] == "user_decision"
    assert carried["obj_more_evidence_needed"] == "next_action"

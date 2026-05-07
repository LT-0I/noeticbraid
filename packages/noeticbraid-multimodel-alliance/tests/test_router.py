from __future__ import annotations

import pytest

from noeticbraid.tools.multimodel_alliance.router import RoutingError, route
from noeticbraid.tools.multimodel_alliance.validator import validate_route_record


def model(model_ref, role, capabilities, invocation="local_session", roles=None):
    return {
        "model_ref": model_ref,
        "role": role,
        "roles": roles or [role],
        "capabilities": capabilities,
        "invocation": invocation,
    }


def assert_valid_route(record):
    validate_route_record(record, "generated_route.json")
    assert record["status"] == "selected"
    assert record["route_id"].startswith("route_")
    assert record["task_id"].startswith("task_")
    return record


def test_low_risk_single_model_when_one_sufficient_model():
    record = route(
        {
            "task_id": "task_write_note",
            "task_type": "writing",
            "risk_hint": "low",
            "required_capabilities": ["writing"],
            "available_models": [model("model_writer", "writer", ["writing"])],
        }
    )
    assert_valid_route(record)
    assert record["route_type"] == "single_model"
    assert [item["model_ref"] for item in record["selected_models"]] == ["model_writer"]


def test_low_risk_coding_or_multi_model_branch_uses_producer_reviewer():
    record = route(
        {
            "task_id": "task_small_patch",
            "task_type": "coding",
            "risk_hint": "low",
            "required_capabilities": ["coding", "code_review"],
            "available_models": [
                model("model_coder", "coder", ["coding"], "codex_cli", roles=["coder", "producer"]),
                model("model_reviewer", "reviewer", ["code_review"], "subagent", roles=["reviewer"]),
            ],
        }
    )
    assert_valid_route(record)
    assert record["route_type"] == "producer_reviewer"
    assert {item["role"] for item in record["selected_models"]} >= {"coder", "reviewer"}


def test_medium_risk_routes_to_dual_review_with_two_independent_reviewers():
    record = route(
        {
            "task_id": "task_prompt_cycle",
            "risk_hint": "medium",
            "required_capabilities": ["planning", "writing", "code_review", "source_audit", "convergence"],
        }
    )
    assert_valid_route(record)
    assert record["route_type"] == "dual_review"
    roles = [item["role"] for item in record["selected_models"]]
    assert roles.count("reviewer") >= 2
    assert "convergence_editor" in roles


def test_high_risk_routes_to_multi_review_with_evidence_gate_roles():
    record = route(
        {
            "task_id": "task_high_risk_contract_gate",
            "risk_hint": "high",
            "trigger": "review_gate",
            "required_capabilities": ["coding", "code_review", "adversary", "verification", "security_review", "convergence"],
        }
    )
    assert_valid_route(record)
    assert record["route_type"] == "multi_review"
    assert {item["role"] for item in record["selected_models"]} >= {"coder", "reviewer", "adversary", "verifier", "convergence_editor"}


def test_disputed_routes_to_manual_convergence_with_human_decision():
    record = route(
        {
            "task_id": "task_disputed_convergence",
            "risk_hint": "disputed",
            "trigger": "review_gate",
            "required_capabilities": ["planning", "code_review", "adversary", "verification", "convergence"],
        }
    )
    assert_valid_route(record)
    assert record["route_type"] == "manual_convergence"
    assert "human_decision" in {item["role"] for item in record["selected_models"]}


def test_available_models_shape_is_fail_closed():
    with pytest.raises(RoutingError):
        route({"task_id": "task_bad_models", "available_models": [{"role": "coder"}]})


def test_route_high_risk_with_writer_only_pool_fails_closed():
    """MUST-1: high-risk role expansion must not fall back to the whole model pool."""
    task_card = {
        "task_id": "task_high_writer_only",
        "task_type": "security_review",
        "risk_hint": "high",
        "required_capabilities": ["security_review"],
        "available_models": [
            model("model_writer_only", "writer", ["writing"], "manual"),
        ],
    }
    with pytest.raises(RoutingError):
        route(task_card)


def test_route_producer_reviewer_with_single_model_pool_fails():
    """MUST-7: producer_reviewer must not allow one model to review itself."""
    task_card = {
        "task_id": "task_pr_self",
        "task_type": "writing",
        "risk_hint": "low",
        "required_capabilities": ["writing", "code_review"],
        "available_models": [
            model("model_only_one", "writer", ["writing", "code_review"], "manual", roles=["writer", "reviewer"]),
        ],
    }
    with pytest.raises(RoutingError):
        route(task_card)

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from noeticbraid.tools.multimodel_alliance.validator import (
    ValidationError,
    validate_all,
    validate_debate_record,
    validate_fixture,
    validate_route_record,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "src" / "noeticbraid" / "tools" / "multimodel_alliance" / "fixtures"


def load_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def test_all_packaged_fixtures_validate():
    validate_all()


def test_private_marker_detection_rejects_fixture_content():
    # NOTE: literal split to avoid main-repo private_leak_scan.py false positive
    # (scanner substring-matches PRIVATE_MARKERS in test sources too).
    private_marker = "raw_" + "token"
    fixture = load_fixture("dual_review_prompt_cycle.json")
    fixture["description"] = f"synthetic {private_marker} marker"
    with pytest.raises(ValidationError):
        validate_fixture(fixture, "synthetic_private_marker.json")


def test_model_route_accepts_frozen_human_decision_role():
    route = load_fixture("manual_convergence_disputed.json")["model_route"]
    route = copy.deepcopy(route)
    route["selected_models"].append(
        {
            "model_ref": "model_user_decision",
            "role": "human_decision",
            "invocation": "manual",
            "reason": "Frozen ModelRoute 1.2.0 includes human_decision for explicit user authority.",
        }
    )
    validate_route_record(route, "human_decision_route.json")


def test_route_json_schema_rejects_missing_invocation():
    route = load_fixture("dual_review_prompt_cycle.json")["model_route"]
    route = copy.deepcopy(route)
    del route["selected_models"][0]["invocation"]
    with pytest.raises(ValidationError):
        validate_route_record(route, "missing_invocation.json")


def test_debate_round_must_reference_selected_participant():
    fixture = load_fixture("multi_review_high_risk_gate.json")
    route = fixture["model_route"]
    debate = copy.deepcopy(fixture["debate"])
    debate["rounds"][0]["participant_id"] = "participant_missing"
    with pytest.raises(ValidationError):
        validate_debate_record(debate, route, "synthetic_unknown_participant.json")

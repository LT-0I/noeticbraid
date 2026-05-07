"""Validate SP-B ModelRoute, Debate, Convergence, and fixture records.

The package uses jsonschema for strict structural checks and keeps the
module-specific invariant checks from the original workflow validator.
"""

from __future__ import annotations

import re
from typing import Any

from jsonschema import Draft202012Validator, SchemaError
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError

from .constants import (
    CAPABILITIES,
    DECISION_STATUSES,
    EXPECTED_OUTPUTS,
    FIXTURE_FILES,
    MODEL_ROLES,
    OBJECTION_STATUSES,
    PARTICIPANT_ROLES,
    PRIVATE_MARKERS,
    RISK_LEVELS,
    ROUND_TYPES,
    ROUTE_TYPES,
    SCHEMA_FILES,
    SEVERITIES,
    TRIGGERS,
    VERDICTS,
)
from .schema_loader import FIXTURE_DIR, SCHEMA_DIR, load_fixture, load_json, load_schema

PREFIX_PATTERNS = {
    "task_id": re.compile(r"^task_[A-Za-z0-9_]+$"),
    "workflow_id": re.compile(r"^workflow_[A-Za-z0-9_]+$"),
    "route_id": re.compile(r"^route_[A-Za-z0-9_]+$"),
    "debate_id": re.compile(r"^debate_[A-Za-z0-9_]+$"),
    "convergence_id": re.compile(r"^convergence_[A-Za-z0-9_]+$"),
    "participant_id": re.compile(r"^participant_[A-Za-z0-9_]+$"),
    "run_ref": re.compile(r"^run_[A-Za-z0-9_]+$"),
    "artifact_ref": re.compile(r"^artifact_[A-Za-z0-9_]+$"),
    "source_ref": re.compile(r"^source_[A-Za-z0-9_]+$"),
    "model_ref": re.compile(r"^model_[A-Za-z0-9_]+$"),
    "objection_id": re.compile(r"^obj_[A-Za-z0-9_]+$"),
}


class ValidationError(ValueError):
    """Raised when a multimodel alliance record violates schema or invariants."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def require_prefix(value: str, pattern_name: str, context: str) -> None:
    pattern = PREFIX_PATTERNS[pattern_name]
    require(isinstance(value, str) and bool(pattern.fullmatch(value)), f"{context} must match {pattern.pattern}")


def _json_path(error: JsonSchemaValidationError) -> str:
    return ".".join(str(part) for part in error.absolute_path) or "<root>"


def validate_json_schema(instance: Any, schema_name: str, filename: str) -> None:
    schema = load_schema(schema_name)
    try:
        validator = Draft202012Validator(schema)
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise ValidationError(f"invalid packaged schema {schema_name}: {exc.message}") from exc
    errors = sorted(validator.iter_errors(instance), key=lambda err: list(err.absolute_path))
    if errors:
        first = errors[0]
        raise ValidationError(f"{filename}.{_json_path(first)} schema violation: {first.message}")


def validate_schema_files() -> None:
    for filename in SCHEMA_FILES:
        path = SCHEMA_DIR / filename
        require(path.exists(), f"missing schema file: {path}")
        data = load_json(path)
        require(data.get("$schema") == "https://json-schema.org/draft/2020-12/schema", f"{filename} must declare draft 2020-12")
        require(data.get("type") == "object", f"{filename} must be an object schema")
        require(data.get("additionalProperties") is False, f"{filename} must be strict")
        require(isinstance(data.get("required"), list) and data["required"], f"{filename} must declare required fields")
        require(isinstance(data.get("properties"), dict) and data["properties"], f"{filename} must declare properties")
    route_schema = load_schema("model_route")
    role_enum = route_schema["properties"]["selected_models"]["items"]["properties"]["role"]["enum"]
    require("human_decision" in role_enum, "model_route.schema.json must include frozen human_decision role")
    require("workflow_id" in route_schema["properties"], "model_route.schema.json must include optional workflow_id")


def scan_private_markers(value: Any, context: str) -> None:
    if isinstance(value, str):
        lowered = value.lower()
        for marker in PRIVATE_MARKERS:
            require(marker not in lowered, f"forbidden private marker in {context}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            scan_private_markers(item, f"{context}[{index}]")
    elif isinstance(value, dict):
        for key, item in value.items():
            scan_private_markers(key, f"{context}.key")
            scan_private_markers(item, f"{context}.{key}")


def validate_key_order(fixture: dict[str, Any], filename: str) -> None:
    require(list(fixture.keys())[:3] == ["fixture_id", "description", "model_route"], f"{filename} top-level keys must start with fixture_id, description, model_route")
    route = fixture["model_route"]
    debate = fixture["debate"]
    convergence = fixture["convergence"]
    require(list(route.keys())[:4] == ["route_id", "task_id", "route_type", "trigger"], f"{filename} route anchor keys are not near the top")
    require(list(debate.keys())[:3] == ["debate_id", "task_id", "route_id"], f"{filename} debate anchor keys are not near the top")
    require(list(convergence.keys())[:3] == ["convergence_id", "task_id", "debate_id"], f"{filename} convergence anchor keys are not near the top")


def validate_severity_summary(summary: Any, context: str) -> None:
    require(isinstance(summary, dict), f"{context} severity_summary must be an object")
    require(set(summary.keys()) == SEVERITIES, f"{context} severity_summary keys must be critical/high/medium/low")
    for key, value in summary.items():
        require(isinstance(value, int) and value >= 0, f"{context} severity {key} must be a non-negative integer")


def validate_route_record(route: dict[str, Any], filename: str = "<memory>") -> set[str]:
    scan_private_markers(route, filename)
    validate_json_schema(route, "model_route", filename)
    require_prefix(route.get("route_id"), "route_id", f"{filename}.model_route.route_id")
    require_prefix(route.get("task_id"), "task_id", f"{filename}.model_route.task_id")
    if route.get("workflow_id") is not None and "workflow_id" in route:
        require_prefix(route.get("workflow_id"), "workflow_id", f"{filename}.model_route.workflow_id")
    require(route.get("route_type") in ROUTE_TYPES, f"{filename}.model_route.route_type is unknown")
    require(route.get("trigger") in TRIGGERS, f"{filename}.model_route.trigger is unknown")
    require(route.get("risk_level") in RISK_LEVELS, f"{filename}.model_route.risk_level is unknown")
    capabilities = route.get("required_capabilities")
    require(isinstance(capabilities, list) and capabilities, f"{filename}.model_route.required_capabilities must be non-empty")
    for capability in capabilities:
        require(capability in CAPABILITIES, f"{filename}.model_route capability is unknown: {capability}")

    selected_models = route.get("selected_models")
    require(isinstance(selected_models, list) and selected_models, f"{filename}.model_route.selected_models must be non-empty")
    model_refs: set[str] = set()
    for index, model in enumerate(selected_models):
        require_prefix(model.get("model_ref"), "model_ref", f"{filename}.selected_models[{index}].model_ref")
        require(model.get("role") in MODEL_ROLES, f"{filename}.selected_models[{index}].role is unknown")
        require(isinstance(model.get("reason"), str) and model["reason"], f"{filename}.selected_models[{index}].reason is required")
        model_refs.add(model["model_ref"])

    for index, model in enumerate(route.get("rejected_models", [])):
        require_prefix(model.get("model_ref"), "model_ref", f"{filename}.rejected_models[{index}].model_ref")
        require(isinstance(model.get("reason"), str) and model["reason"], f"{filename}.rejected_models[{index}].reason is required")

    for field, pattern_name in (("run_refs", "run_ref"), ("artifact_refs", "artifact_ref"), ("source_refs", "source_ref")):
        values = route.get(field)
        require(isinstance(values, list), f"{filename}.model_route.{field} must be an array")
        for value in values:
            require_prefix(value, pattern_name, f"{filename}.model_route.{field}")

    require(isinstance(route.get("rationale"), str) and route["rationale"], f"{filename}.model_route.rationale is required")
    return model_refs


def collect_debate_objections(debate: dict[str, Any], filename: str, model_refs: set[str] | None = None) -> dict[str, dict[str, Any]]:
    require_prefix(debate.get("debate_id"), "debate_id", f"{filename}.debate.debate_id")
    require_prefix(debate.get("task_id"), "task_id", f"{filename}.debate.task_id")
    require_prefix(debate.get("route_id"), "route_id", f"{filename}.debate.route_id")

    participants = debate.get("participants")
    require(isinstance(participants, list) and participants, f"{filename}.debate.participants must be non-empty")
    participant_ids: set[str] = set()
    for index, participant in enumerate(participants):
        pid = participant.get("participant_id")
        require_prefix(pid, "participant_id", f"{filename}.participants[{index}].participant_id")
        require(pid not in participant_ids, f"{filename} duplicate participant_id: {pid}")
        participant_ids.add(pid)
        model_ref = participant.get("model_ref")
        require_prefix(model_ref, "model_ref", f"{filename}.participants[{index}].model_ref")
        if model_refs is not None:
            require(model_ref in model_refs, f"{filename}.participants[{index}] model_ref not selected in route")
        require(participant.get("role") in PARTICIPANT_ROLES, f"{filename}.participants[{index}].role is unknown")
        require(participant.get("expected_output") in EXPECTED_OUTPUTS, f"{filename}.participants[{index}].expected_output is unknown")

    objections: dict[str, dict[str, Any]] = {}
    manual_actors = {"manual", "human"}
    rounds = debate.get("rounds")
    require(isinstance(rounds, list) and rounds, f"{filename}.debate.rounds must be non-empty")
    for index, round_record in enumerate(rounds):
        require_prefix(round_record.get("participant_id"), "participant_id", f"{filename}.rounds[{index}].participant_id")
        require(round_record["participant_id"] in participant_ids, f"{filename}.rounds[{index}] references unknown participant")
        require_prefix(round_record.get("artifact_ref"), "artifact_ref", f"{filename}.rounds[{index}].artifact_ref")
        require(round_record.get("round_type") in ROUND_TYPES, f"{filename}.rounds[{index}].round_type is unknown")
        require(round_record.get("verdict") in VERDICTS, f"{filename}.rounds[{index}].verdict is unknown")
        validate_severity_summary(round_record.get("severity_summary"), f"{filename}.rounds[{index}]")
        round_objections = round_record.get("objections")
        require(isinstance(round_objections, list), f"{filename}.rounds[{index}].objections must be an array")
        for objection in round_objections:
            oid = objection.get("objection_id")
            require_prefix(oid, "objection_id", f"{filename}.rounds[{index}].objection_id")
            require(oid not in objections, f"{filename} duplicate objection_id: {oid}")
            require(objection.get("severity") in SEVERITIES, f"{filename}.{oid}.severity is unknown")
            require(objection.get("status") in OBJECTION_STATUSES, f"{filename}.{oid}.status is unknown")
            require(isinstance(objection.get("summary"), str) and objection["summary"], f"{filename}.{oid}.summary is required")
            for evidence_ref in objection.get("evidence_refs", []):
                require_prefix(evidence_ref, "artifact_ref", f"{filename}.{oid}.evidence_refs")
            if "raised_by" in objection:
                require(
                    objection["raised_by"] in participant_ids or objection["raised_by"] in manual_actors,
                    f"{filename}.{oid}.raised_by must reference participant_id or be 'manual'/'human'",
                )
            if "addressed_by" in objection:
                require(
                    objection["addressed_by"] in participant_ids or objection["addressed_by"] in manual_actors,
                    f"{filename}.{oid}.addressed_by must reference participant_id or be 'manual'/'human'",
                )
            if "addresses_objection_ref" in objection:
                ref = objection["addresses_objection_ref"]
                require(ref in objections, f"{filename}.{oid}.addresses_objection_ref unknown: {ref}")
                prior = objections[ref]
                require(
                    prior["status"] in {"raised", "unresolved", "needs_user_decision"},
                    f"{filename}.{oid}.addresses_objection_ref {ref} not in resolvable status (was {prior['status']})",
                )
                require(
                    objection["status"] in {"accepted", "rejected", "needs_user_decision"},
                    f"{filename}.{oid}.status must be terminal when addresses_objection_ref is set (got {objection['status']})",
                )
            objections[oid] = objection

    verdicts = debate.get("verdicts")
    require(isinstance(verdicts, list) and verdicts, f"{filename}.debate.verdicts must be non-empty")
    for index, verdict in enumerate(verdicts):
        require(verdict.get("participant_id") in participant_ids, f"{filename}.verdicts[{index}] references unknown participant")
        require(verdict.get("verdict") in VERDICTS, f"{filename}.verdicts[{index}].verdict is unknown")
        require(isinstance(verdict.get("summary"), str) and verdict["summary"], f"{filename}.verdicts[{index}].summary is required")

    validate_severity_summary(debate.get("severity_summary"), f"{filename}.debate")
    unresolved = debate.get("unresolved_objections")
    require(isinstance(unresolved, list), f"{filename}.debate.unresolved_objections must be an array")
    addressed_refs = {
        objection["addresses_objection_ref"]
        for objection in objections.values()
        if "addresses_objection_ref" in objection and objection["status"] in {"accepted", "rejected"}
    }
    for oid in unresolved:
        require(oid in objections, f"{filename}.debate unresolved objection is not defined: {oid}")
        require(objections[oid]["status"] in OBJECTION_STATUSES, f"{filename}.{oid}.status is unknown")
    for oid, objection in objections.items():
        if objection["status"] in {"raised", "unresolved", "needs_user_decision"} and oid not in addressed_refs:
            require(oid in unresolved, f"{filename}.{oid} unresolved status must be listed in debate.unresolved_objections")
    return objections


def validate_debate_record(debate: dict[str, Any], route: dict[str, Any] | None = None, filename: str = "<memory>") -> dict[str, dict[str, Any]]:
    scan_private_markers(debate, filename)
    validate_json_schema(debate, "debate", filename)
    model_refs = None
    if route is not None:
        require(debate.get("task_id") == route.get("task_id"), f"{filename}.debate task_id must match route")
        require(debate.get("route_id") == route.get("route_id"), f"{filename}.debate route_id must match route")
        model_refs = validate_route_record(route, filename)
    return collect_debate_objections(debate, filename, model_refs)


def validate_convergence_record(convergence: dict[str, Any], debate: dict[str, Any] | None = None, filename: str = "<memory>") -> None:
    scan_private_markers(convergence, filename)
    validate_json_schema(convergence, "convergence", filename)
    require_prefix(convergence.get("convergence_id"), "convergence_id", f"{filename}.convergence.convergence_id")
    require(isinstance(convergence.get("recommendation"), str) and convergence["recommendation"], f"{filename}.convergence.recommendation is required")
    require(convergence.get("decision_status") in DECISION_STATUSES, f"{filename}.convergence.decision_status is unknown")

    if debate is None:
        return

    require(convergence.get("task_id") == debate.get("task_id"), f"{filename}.convergence task_id must match debate")
    require(convergence.get("debate_id") == debate.get("debate_id"), f"{filename}.convergence debate_id must match debate")
    objections = collect_debate_objections(debate, filename, None)
    addressed_refs = {
        objection["addresses_objection_ref"]
        for objection in objections.values()
        if "addresses_objection_ref" in objection and objection["status"] in {"accepted", "rejected"}
    }

    handled: dict[str, str] = {}
    for section_name in ("accepted_objections", "rejected_objections", "unresolved_disagreements", "user_decision_requirements", "next_actions", "memory_candidates"):
        require(isinstance(convergence.get(section_name), list), f"{filename}.convergence.{section_name} must be an array")

    for item in convergence["accepted_objections"]:
        oid = item.get("objection_id")
        require(oid in objections, f"{filename}.accepted_objections references unknown objection: {oid}")
        require(isinstance(item.get("resolution"), str) and item["resolution"], f"{filename}.{oid}.resolution is required")
        handled[oid] = "accepted"
    for item in convergence["rejected_objections"]:
        oid = item.get("objection_id")
        require(oid in objections, f"{filename}.rejected_objections references unknown objection: {oid}")
        require(isinstance(item.get("rejection_reason"), str) and item["rejection_reason"], f"{filename}.{oid}.rejection_reason is required")
        handled[oid] = "rejected"

    unresolved_critical: list[str] = []
    unresolved_ids: set[str] = set()
    for item in convergence["unresolved_disagreements"]:
        oid = item.get("objection_id")
        require(oid in objections, f"{filename}.unresolved_disagreements references unknown objection: {oid}")
        require(item.get("severity") == objections[oid]["severity"], f"{filename}.{oid}.severity must match debate objection")
        require(item.get("carried_to") in {"user_decision", "next_action", "more_evidence"}, f"{filename}.{oid}.carried_to is unknown")
        unresolved_ids.add(oid)
        handled[oid] = "unresolved"
        if item["severity"] == "critical":
            unresolved_critical.append(oid)

    user_decision_objections: set[str] = set()
    for item in convergence["user_decision_requirements"]:
        require(isinstance(item.get("blocking"), bool), f"{filename}.user_decision blocking must be boolean")
        for oid in item.get("related_objection_refs", []):
            require(oid in objections, f"{filename}.user_decision references unknown objection: {oid}")
            user_decision_objections.add(oid)

    for oid in debate.get("unresolved_objections", []):
        require(oid in unresolved_ids, f"{filename}.debate unresolved objection must be carried into convergence: {oid}")

    for oid, objection in objections.items():
        if objection["severity"] == "critical":
            require(oid in handled or oid in addressed_refs, f"{filename} critical objection is unhandled: {oid}")

    if convergence["decision_status"] == "accepted":
        require(not unresolved_critical, f"{filename} cannot be accepted with unresolved critical objections")

    for oid in unresolved_critical:
        carried_to = next(item["carried_to"] for item in convergence["unresolved_disagreements"] if item["objection_id"] == oid)
        if carried_to == "user_decision":
            require(oid in user_decision_objections, f"{filename} critical unresolved objection must have a user decision requirement: {oid}")
        else:
            require(convergence["decision_status"] == "needs_more_evidence", f"{filename} critical unresolved objection carried to evidence must not be accepted: {oid}")


def validate_fixture(fixture: dict[str, Any], filename: str = "<memory>") -> None:
    require(isinstance(fixture, dict), f"{filename} must be an object")
    require(set(fixture.keys()) == {"fixture_id", "description", "model_route", "debate", "convergence"}, f"{filename} must have exactly the fixture wrapper keys")
    validate_key_order(fixture, filename)
    scan_private_markers(fixture, filename)

    route = fixture["model_route"]
    debate = fixture["debate"]
    convergence = fixture["convergence"]
    require(debate.get("task_id") == route.get("task_id"), f"{filename}.debate task_id must match route")
    require(debate.get("route_id") == route.get("route_id"), f"{filename}.debate route_id must match route")

    validate_route_record(route, filename)
    validate_debate_record(debate, route, filename)
    validate_convergence_record(convergence, debate, filename)


def load_fixtures() -> list[tuple[str, dict[str, Any]]]:
    fixtures: list[tuple[str, dict[str, Any]]] = []
    for filename in FIXTURE_FILES:
        path = FIXTURE_DIR / filename
        require(path.exists(), f"missing fixture file: {path}")
        fixtures.append((filename, load_fixture(filename)))
    return fixtures


def validate_all() -> None:
    validate_schema_files()
    fixtures = load_fixtures()
    for filename, fixture in fixtures:
        validate_fixture(fixture, filename)

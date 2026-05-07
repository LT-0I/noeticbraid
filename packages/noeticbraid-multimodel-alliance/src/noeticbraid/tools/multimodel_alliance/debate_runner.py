"""Build Debate records from a selected ModelRoute and round inputs."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from typing import Any

from .constants import PARTICIPANT_ROLES, ROUND_TYPES, SEVERITIES, VERDICTS
from .validator import ValidationError, validate_debate_record, validate_route_record

_UNRESOLVED_STATUSES = {"raised", "unresolved", "needs_user_decision"}

_PARTICIPANT_ROLE_BY_MODEL_ROLE = {
    "orchestrator": "producer",
    "planner": "producer",
    "researcher": "producer",
    "producer": "producer",
    "writer": "producer",
    "coder": "producer",
    "reviewer": "reviewer",
    "adversary": "adversary",
    "source_auditor": "source_auditor",
    "verifier": "verifier",
    "convergence_editor": "convergence_editor",
}

_EXPECTED_OUTPUT_BY_PARTICIPANT_ROLE = {
    "producer": "patch",
    "reviewer": "verdict",
    "adversary": "risk_list",
    "source_auditor": "evidence",
    "logic_reviewer": "verdict",
    "verifier": "validation_result",
    "convergence_editor": "report",
}

_ROUND_TYPE_BY_PARTICIPANT_ROLE = {
    "producer": "production",
    "reviewer": "review",
    "adversary": "adversarial_review",
    "source_auditor": "review",
    "logic_reviewer": "review",
    "verifier": "verification",
    "convergence_editor": "arbitration",
}


class DebateError(ValueError):
    """Raised when a route and round list cannot form a valid Debate."""


def _stable_hash(*parts: object, length: int = 12) -> str:
    return hashlib.sha256("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:length]


def _slug(value: object, default: str = "item", max_length: int = 72) -> str:
    slug = re.sub(r"[^A-Za-z0-9_]+", "_", str(value or "")).strip("_")
    if not slug:
        slug = f"{default}_{_stable_hash(value)}"
    if len(slug) > max_length:
        slug = f"{slug[: max_length - 13].rstrip('_')}_{_stable_hash(slug)}"
    return slug


def _prefixed(prefix: str, value: object, default: str = "item", max_length: int = 128) -> str:
    slug = _slug(value, default=default, max_length=max_length - len(prefix) - 1)
    candidate = slug if slug.startswith(prefix + "_") else f"{prefix}_{slug}"
    if len(candidate) > max_length:
        candidate = f"{candidate[: max_length - 13].rstrip('_')}_{_stable_hash(candidate)}"
    return candidate


def _participants(model_route: dict[str, Any]) -> list[dict[str, str]]:
    participants: list[dict[str, str]] = []
    used_ids: set[str] = set()
    for index, selected in enumerate(model_route["selected_models"]):
        model_role = selected["role"]
        if model_role == "human_decision":
            continue
        participant_role = _PARTICIPANT_ROLE_BY_MODEL_ROLE.get(model_role)
        if participant_role is None:
            continue
        base = f"{selected['model_ref']}_{participant_role}_{index}"
        participant_id = _prefixed("participant", base, "participant")
        while participant_id in used_ids:
            participant_id = _prefixed("participant", f"{base}_{_stable_hash(participant_id)}", "participant")
        used_ids.add(participant_id)
        expected = _EXPECTED_OUTPUT_BY_PARTICIPANT_ROLE[participant_role]
        if model_role == "planner":
            expected = "plan"
        elif model_role == "writer":
            expected = "report"
        participants.append(
            {
                "participant_id": participant_id,
                "model_ref": selected["model_ref"],
                "role": participant_role,
                "expected_output": expected,
            }
        )
    if not participants:
        raise DebateError("route has no model roles that can become debate participants")
    return participants


def _severity_summary(objections: list[dict[str, Any]], supplied: Any = None) -> dict[str, int]:
    if supplied is not None:
        if not isinstance(supplied, dict):
            raise DebateError("round.severity_summary must be an object")
        result = {severity: int(supplied.get(severity, 0)) for severity in ("critical", "high", "medium", "low")}
        if any(value < 0 for value in result.values()):
            raise DebateError("round.severity_summary values must be non-negative")
        return result
    result = {severity: 0 for severity in ("critical", "high", "medium", "low")}
    for objection in objections:
        result[objection["severity"]] += 1
    return result


def _normalize_objections(raw_objections: Any, artifact_ref: str, round_seed: str) -> list[dict[str, Any]]:
    if raw_objections is None:
        return []
    if not isinstance(raw_objections, list):
        raise DebateError("round.objections must be a list")
    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_objections):
        if not isinstance(raw, dict):
            raise DebateError(f"round.objections[{index}] must be an object")
        severity = raw.get("severity", "low")
        if severity not in SEVERITIES:
            raise DebateError(f"unknown objection severity: {severity}")
        status = raw.get("status", "raised")
        if status not in {"raised", "accepted", "rejected", "unresolved", "needs_user_decision"}:
            raise DebateError(f"unknown objection status: {status}")
        evidence_refs = raw.get("evidence_refs")
        if evidence_refs is None:
            evidence_refs = [artifact_ref]
        if not isinstance(evidence_refs, list) or not all(isinstance(ref, str) for ref in evidence_refs):
            raise DebateError("objection.evidence_refs must be a list of artifact refs")
        objection_id = raw.get("objection_id") or _prefixed("obj", f"{round_seed}_{index}", "objection")
        record = {
            "objection_id": objection_id,
            "severity": severity,
            "status": status,
            "summary": raw.get("summary") or "Generated objection from debate round input.",
            "evidence_refs": evidence_refs,
        }
        if "raised_by" in raw and raw["raised_by"]:
            record["raised_by"] = str(raw["raised_by"])
        if "addressed_by" in raw and raw["addressed_by"]:
            record["addressed_by"] = str(raw["addressed_by"])
        if "addresses_objection_ref" in raw and raw["addresses_objection_ref"]:
            record["addresses_objection_ref"] = str(raw["addresses_objection_ref"])
        normalized.append(record)
    return normalized


def _participant_for_round(raw_round: dict[str, Any], participants: list[dict[str, str]], role_cursors: dict[str, int]) -> dict[str, str]:
    if "participant_id" in raw_round:
        participant_id = raw_round["participant_id"]
        for participant in participants:
            if participant["participant_id"] == participant_id:
                return participant
        raise DebateError(f"round references unknown participant_id: {participant_id}")
    role = raw_round.get("role")
    if role is None:
        return participants[0]
    if role not in PARTICIPANT_ROLES:
        raise DebateError(f"round.role is unknown: {role}")
    matches = [participant for participant in participants if participant["role"] == role]
    if not matches:
        raise DebateError(f"route has no participant for role: {role}")
    index = role_cursors[role] % len(matches)
    role_cursors[role] += 1
    return matches[index]


def _default_rounds_input(participants: list[dict[str, str]]) -> list[dict[str, Any]]:
    producer = next((item for item in participants if item["role"] == "producer"), participants[0])
    reviewer = next((item for item in participants if item["role"] == "reviewer"), None)
    rounds = [
        {
            "participant_id": producer["participant_id"],
            "artifact_ref": "artifact_generated_production",
            "round_type": "production",
            "verdict": "informational",
            "summary": "Generated production placeholder; external invocation is handled outside SP-B.",
        }
    ]
    if reviewer is not None:
        rounds.append(
            {
                "participant_id": reviewer["participant_id"],
                "artifact_ref": "artifact_generated_review",
                "round_type": "review",
                "verdict": "informational",
                "summary": "Generated review placeholder; external invocation is handled outside SP-B.",
            }
        )
    return rounds


def run_debate(route: dict[str, Any], rounds_input: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Return a validated Debate record for ``route`` and caller-supplied round data."""
    try:
        validate_route_record(route, "route_for_debate.json")
    except ValidationError as exc:
        raise DebateError(str(exc)) from exc

    participants = _participants(route)
    raw_rounds = rounds_input if rounds_input else _default_rounds_input(participants)
    if not isinstance(raw_rounds, list):
        raise DebateError("rounds_input must be a list")

    debate_id = _prefixed("debate", route["route_id"].removeprefix("route_"), "debate")
    role_cursors: dict[str, int] = defaultdict(int)
    rounds: list[dict[str, Any]] = []
    verdicts: list[dict[str, str]] = []

    for index, raw in enumerate(raw_rounds):
        if not isinstance(raw, dict):
            raise DebateError(f"rounds_input[{index}] must be an object")
        participant = _participant_for_round(raw, participants, role_cursors)
        artifact_ref = raw.get("artifact_ref") or _prefixed("artifact", f"{debate_id}_{index}", "artifact")
        round_type = raw.get("round_type") or _ROUND_TYPE_BY_PARTICIPANT_ROLE[participant["role"]]
        if round_type not in ROUND_TYPES:
            raise DebateError(f"unknown round_type: {round_type}")
        verdict = raw.get("verdict") or "informational"
        if verdict not in VERDICTS:
            raise DebateError(f"unknown verdict: {verdict}")
        round_seed = f"{debate_id}_{index}_{participant['participant_id']}"
        objections = _normalize_objections(raw.get("objections"), artifact_ref, round_seed)
        severity_summary = _severity_summary(objections, raw.get("severity_summary"))
        round_id = raw.get("round_id") or _prefixed("round", round_seed, "round")
        rounds.append(
            {
                "round_id": round_id,
                "participant_id": participant["participant_id"],
                "artifact_ref": artifact_ref,
                "round_type": round_type,
                "verdict": verdict,
                "severity_summary": severity_summary,
                "objections": objections,
            }
        )
        verdicts.append(
            {
                "participant_id": participant["participant_id"],
                "verdict": verdict,
                "summary": raw.get("summary") or f"{participant['role']} round completed with verdict={verdict}.",
            }
        )

    total = {severity: 0 for severity in ("critical", "high", "medium", "low")}
    for round_record in rounds:
        for severity in total:
            total[severity] += round_record["severity_summary"][severity]

    all_objections: dict[str, dict[str, Any]] = {}
    addressed_refs: set[str] = set()
    for round_record in rounds:
        for objection in round_record["objections"]:
            all_objections[objection["objection_id"]] = objection
            if "addresses_objection_ref" in objection and objection["status"] in {"accepted", "rejected"}:
                addressed_refs.add(objection["addresses_objection_ref"])

    unresolved_objections = [
        oid
        for oid, objection in all_objections.items()
        if oid not in addressed_refs and objection["status"] in _UNRESOLVED_STATUSES
    ]

    status = "converged"
    if unresolved_objections:
        status = "waiting_for_user" if any(
            all_objections[oid]["status"] == "needs_user_decision" for oid in unresolved_objections
        ) else "running"

    debate = {
        "debate_id": debate_id,
        "task_id": route["task_id"],
        "route_id": route["route_id"],
        "participants": participants,
        "rounds": rounds,
        "verdicts": verdicts,
        "severity_summary": total,
        "unresolved_objections": unresolved_objections,
        "status": status,
    }
    try:
        validate_debate_record(debate, route, "generated_debate.json")
    except ValidationError as exc:
        raise DebateError(str(exc)) from exc
    return debate

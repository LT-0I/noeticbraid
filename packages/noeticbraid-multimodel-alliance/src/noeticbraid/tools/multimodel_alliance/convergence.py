"""Generate Convergence records from Debate records."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from .validator import ValidationError, validate_convergence_record, validate_debate_record

_UNRESOLVED_STATUSES = {"raised", "unresolved", "needs_user_decision"}


class ConvergenceError(ValueError):
    """Raised when a Debate cannot be converted to a valid Convergence."""


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


def _collect_objections(debate: dict[str, Any]) -> list[dict[str, Any]]:
    objections: list[dict[str, Any]] = []
    for round_record in debate.get("rounds", []):
        for objection in round_record.get("objections", []):
            objections.append(objection)
    return objections


def _carried_to(objection: dict[str, Any]) -> str:
    if objection["status"] == "needs_user_decision" or objection["severity"] == "critical":
        return "user_decision"
    if objection["severity"] == "high":
        return "next_action"
    return "more_evidence"


def converge(debate: dict[str, Any]) -> dict[str, Any]:
    """Return a validated Convergence record for ``debate``.

    Convergence does not use majority vote. Objections are partitioned by
    status: accepted, rejected, or carried forward. Critical/user-decision
    objections become blocking user decision requirements.
    """
    try:
        validate_debate_record(debate, None, "debate_for_convergence.json")
    except ValidationError as exc:
        raise ConvergenceError(str(exc)) from exc

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    next_actions: list[dict[str, str]] = []
    unresolved_ids = set(debate.get("unresolved_objections", []))

    for objection in _collect_objections(debate):
        oid = objection["objection_id"]
        evidence_refs = objection.get("evidence_refs", [])
        if objection["status"] == "accepted":
            accepted.append(
                {
                    "objection_id": oid,
                    "resolution": f"Accepted objection and require follow-up in final recommendation: {objection['summary']}",
                    "evidence_refs": evidence_refs,
                }
            )
        elif objection["status"] == "rejected":
            rejected.append(
                {
                    "objection_id": oid,
                    "rejection_reason": f"Rejected after convergence review: {objection['summary']}",
                    "evidence_refs": evidence_refs,
                }
            )
        elif objection["status"] in _UNRESOLVED_STATUSES and oid in unresolved_ids:
            carried = _carried_to(objection)
            unresolved.append(
                {
                    "objection_id": oid,
                    "severity": objection["severity"],
                    "summary": objection["summary"],
                    "carried_to": carried,
                    "evidence_refs": evidence_refs,
                }
            )
            if carried == "user_decision":
                decisions.append(
                    {
                        "decision_id": _prefixed("decision", oid.removeprefix("obj_"), "decision"),
                        "question": f"How should the unresolved {objection['severity']} objection be resolved: {objection['summary']}",
                        "options": ["block_until_resolved", "accept_with_explicit_risk"],
                        "blocking": objection["severity"] in {"critical", "high"} or objection["status"] == "needs_user_decision",
                        "related_objection_refs": [oid],
                    }
                )
            elif carried == "next_action":
                next_actions.append(
                    {
                        "action_id": _prefixed("action", f"resolve_{oid}", "action"),
                        "owner": "verifier",
                        "action": f"Collect evidence or remediation for unresolved objection {oid} before final acceptance.",
                        "status": "planned",
                    }
                )
            else:
                next_actions.append(
                    {
                        "action_id": _prefixed("action", f"more_evidence_{oid}", "action"),
                        "owner": "verifier",
                        "action": f"Gather more evidence for objection {oid}.",
                        "status": "planned",
                    }
                )

    if any(item["blocking"] for item in decisions):
        decision_status = "needs_user_decision"
    elif unresolved:
        decision_status = "needs_more_evidence"
    else:
        decision_status = "accepted"

    if decision_status == "accepted":
        recommendation = "Accept the debate result: all objections are either handled or non-blocking, with no unresolved disagreement carried forward."
    elif decision_status == "needs_user_decision":
        recommendation = "Do not accept by model majority. Present blocking unresolved disagreement to the user before integration or final acceptance."
    else:
        recommendation = "Do not accept yet. Complete evidence-gathering next actions and rerun convergence afterward."

    convergence = {
        "convergence_id": _prefixed("convergence", debate["debate_id"].removeprefix("debate_"), "convergence"),
        "task_id": debate["task_id"],
        "debate_id": debate["debate_id"],
        "recommendation": recommendation,
        "accepted_objections": accepted,
        "rejected_objections": rejected,
        "unresolved_disagreements": unresolved,
        "user_decision_requirements": decisions,
        "next_actions": next_actions,
        "memory_candidates": [],
        "decision_status": decision_status,
    }
    try:
        validate_convergence_record(convergence, debate, "generated_convergence.json")
    except ValidationError as exc:
        raise ConvergenceError(str(exc)) from exc
    return convergence

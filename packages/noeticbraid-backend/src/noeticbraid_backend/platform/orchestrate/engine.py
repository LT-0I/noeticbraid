# SPDX-License-Identifier: Apache-2.0
"""Synchronous Phase-2 orchestration engine."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from noeticbraid_backend.platform.conversation import model
from noeticbraid_backend.platform.elicitation.capabilities import capability_for
from noeticbraid_backend.platform.elicitation.local_ai import sanitize_error_msg
from noeticbraid_backend.platform.orchestrate import state
from noeticbraid_backend.platform.orchestrate.critique import CritiqueResult, run_critique_loop
from noeticbraid_backend.platform.orchestrate.nodes import HubExecutionNode, LocalExecutionNode
from noeticbraid_backend.platform.workflows.selector import select_workflow


@dataclass(frozen=True, slots=True)
class OrchestrationView:
    task_id: str
    phase: str
    selected_workflow_id: str | None
    requirements: dict[str, Any]


def run_orchestration(account: str, task_id: str) -> OrchestrationView:
    requirements_payload = model.load_requirements(account, task_id)
    if requirements_payload.get("status") != "confirmed" or requirements_payload.get("legacy") is True:
        return OrchestrationView(
            task_id=task_id,
            phase=state.current_phase(account, task_id, requirements_payload),
            selected_workflow_id=None,
            requirements=requirements_payload,
        )
    requirements = [dict(item) for item in requirements_payload.get("requirements", []) if isinstance(item, dict)]
    if not requirements:
        return OrchestrationView(
            task_id=task_id,
            phase=state.current_phase(account, task_id, requirements_payload),
            selected_workflow_id=None,
            requirements=requirements_payload,
        )

    selection = select_workflow(requirements_payload, account=account, task_id=task_id)
    run_state = state.initial_state(task_id, selection.spec.id)
    run_state = state.write_state(account, task_id, run_state)
    terminal_statuses: list[str] = []
    fanout_node = _node_by_id(selection.spec.nodes, "fanout")
    critique_node = _node_by_id(selection.spec.nodes, "critique_loop")
    fanout_uses_hub = _fanout_uses_hub_agent(fanout_node)
    execution_node = HubExecutionNode() if fanout_uses_hub else LocalExecutionNode()
    reviewer_families_raw = critique_node.get("reviewer_families")
    reviewer_families = (
        tuple(str(item) for item in reviewer_families_raw if str(item or "").strip())
        if isinstance(reviewer_families_raw, list)
        else ("codex", "gemini")
    )

    for requirement in requirements:
        modality = str(requirement.get("modality") or "text").strip().lower()
        if _is_capability_blocked(requirement) and not (
            fanout_uses_hub
            and modality in {"image", "video", "slides", "poster"}
            and (__import__("os").environ.get("NOETICBRAID_PLATFORM_HUB_EXEC") or "").strip().lower()
            in {"1", "true", "yes", "on"}
        ):
            _ensure_blocked(account, task_id, requirements_payload, requirement)
            terminal_statuses.append("deferred")
            requirements_payload = model.load_requirements(account, task_id)
            continue

        _set_requirement_state(account, task_id, requirements_payload, requirement["id"], "in_progress")
        model.append_conversation_row(
            account,
            task_id,
            role="assistant",
            kind="coarse_status",
            text=f"Started: {requirement['text']}",
            requirement_id=str(requirement["id"]),
        )
        requirements_payload = model.load_requirements(account, task_id)

        execution_inputs = {
            "requirement": requirement,
            "requirement_modality": requirement.get("modality"),
            "selected_workflow_id": selection.spec.id,
            "workflow_version": selection.spec.version,
            "reviewer_families": reviewer_families,
        }
        if fanout_uses_hub:
            execution_inputs = {**execution_inputs, "account": account, "task_id": task_id}
        outcome = execution_node.execute(
            fanout_node,
            execution_inputs,
        )
        if outcome.status != "succeeded" or outcome.artifact is None:
            reason = sanitize_error_msg(outcome.reason or "local model failed", max_chars=512) or "local model failed"
            _set_requirement_state(account, task_id, requirements_payload, requirement["id"], "blocked", blocked_reason=reason)
            _append_blocked_status(account, task_id, requirement, reason)
            terminal_statuses.append(_terminal_status_for_node_defer(fanout_uses_hub, reason))
            requirements_payload = model.load_requirements(account, task_id)
            continue

        artifact_ref, evidence_id = state.write_round_artifact(
            account,
            task_id,
            1,
            f"fanout_{requirement['id']}",
            {"artifact": outcome.artifact},
        )
        run_state = state.append_round(
            run_state,
            round_no=1,
            artifact_ref=artifact_ref,
            decision_class="mechanical",
            terminated_by="fanout",
            hub=outcome.artifact.get("hub") is True,
        )
        run_state = state.write_state(account, task_id, run_state)

        critique = run_critique_loop(account, task_id, requirement, outcome.artifact, evidence_id, reviewer_families=reviewer_families)
        run_state = _merge_critique_rounds(run_state, critique)
        run_state = state.write_state(account, task_id, run_state)
        if critique.status in {"delivered", "capped"}:
            final_ref = state.write_final_artifact(
                account,
                task_id,
                f"final_{requirement['id']}",
                {"artifact": critique.artifact, "source_artifact_ref": critique.artifact_ref},
            )
            run_state = state.append_round(
                run_state,
                round_no=len(run_state["rounds"]) + 1,
                artifact_ref=final_ref,
                decision_class=critique.decision_class,
                terminated_by=critique.terminated_by,
                hub=critique.artifact.get("hub") is True,
            )
            run_state = state.write_state(account, task_id, run_state)
            _set_requirement_state(account, task_id, requirements_payload, requirement["id"], "done")
            model.append_conversation_row(
                account,
                task_id,
                role="assistant",
                kind="coarse_status",
                text=f"Completed: {requirement['text']}",
                requirement_id=str(requirement["id"]),
            )
            terminal_statuses.append(critique.status)
        elif critique.status == "deferred":
            if outcome.artifact.get("hub") is True and critique.terminated_by == "deferred":
                final_ref = state.write_final_artifact(
                    account,
                    task_id,
                    f"final_{requirement['id']}",
                    {"artifact": critique.artifact, "source_artifact_ref": critique.artifact_ref, "review_status": "deferred"},
                )
                run_state = state.append_round(
                    run_state,
                    round_no=len(run_state["rounds"]) + 1,
                    artifact_ref=final_ref,
                    decision_class=critique.decision_class,
                    terminated_by="review_deferred",
                    hub=critique.artifact.get("hub") is True,
                )
                run_state = state.write_state(account, task_id, run_state)
                _set_requirement_state(account, task_id, requirements_payload, requirement["id"], "done")
            terminal_statuses.append("deferred")
        else:
            reason = sanitize_error_msg(critique.reason or "local critique failed", max_chars=512) or "local critique failed"
            _set_requirement_state(account, task_id, requirements_payload, requirement["id"], "blocked", blocked_reason=reason)
            _append_blocked_status(account, task_id, requirement, reason)
            terminal_statuses.append("blocked" if outcome.artifact.get("hub") is True else "deferred")
        requirements_payload = model.load_requirements(account, task_id)

    final_status = _run_status(terminal_statuses)
    run_state = state.set_status(run_state, final_status)
    run_state = state.write_state(account, task_id, run_state)
    requirements_payload = model.load_requirements(account, task_id)
    return OrchestrationView(
        task_id=task_id,
        phase=run_state["status"],
        selected_workflow_id=selection.spec.id,
        requirements=requirements_payload,
    )


def _merge_critique_rounds(run_state: dict[str, Any], critique: CritiqueResult) -> dict[str, Any]:
    updated = run_state
    for row in critique.rounds:
        updated = state.append_round(
            updated,
            round_no=int(row["round"]),
            artifact_ref=str(row["artifact_ref"]),
            decision_class=str(row["decision_class"]),
            terminated_by=str(row["terminated_by"]),
            hub=row.get("hub") is True,
        )
    return updated


def _node_by_id(nodes: tuple[dict[str, Any], ...], node_id: str) -> dict[str, Any]:
    for node in nodes:
        if node.get("id") == node_id:
            return dict(node)
    raise ValueError(f"workflow node missing: {node_id}")


def _fanout_uses_hub_agent(fanout_node: dict[str, Any]) -> bool:
    agents = fanout_node.get("agents")
    if not isinstance(agents, list):
        return False
    return any(str(agent or "").strip().lower() in {"web_gpt", "web_chatgpt", "chatgpt_web", "web_ai"} for agent in agents)


def _terminal_status_for_node_defer(fanout_uses_hub: bool, reason: str) -> str:
    # Honest-Q4 aggregate distinction: gate-off/digest-gate → "deferred"
    # (feature not enabled), real hub failure → "blocked" (tried, web AI
    # failed). This reverse-engineers intent from the sanitized reason string,
    # which is correct today (sanitize_error_msg is identity for these literals)
    # but brittle. KNOWN POST-PHASE-3 DEBT: the clean fix is a NodeOutcome
    # defer-kind flag — deliberately deferred because NodeOutcome is the frozen
    # Phase-2 caller contract. Per-requirement coarse_state stays individually
    # authoritative regardless, so user-facing truth is never affected here.
    if not fanout_uses_hub:
        return "deferred"
    gate_reasons = {
        capability_for("web_ai").blocked_reason,
        "web execution is not available",
    }
    return "deferred" if reason in gate_reasons else "blocked"


def _is_capability_blocked(requirement: dict[str, Any]) -> bool:
    return str(requirement.get("capability_status") or "supported") in {"unavailable", "deferred"}


def _ensure_blocked(account: str, task_id: str, payload: dict[str, Any], requirement: dict[str, Any]) -> None:
    if requirement.get("coarse_state") == "blocked" and requirement.get("blocked_reason"):
        return
    capability = capability_for(str(requirement.get("modality") or "text"))
    _set_requirement_state(
        account,
        task_id,
        payload,
        str(requirement["id"]),
        "blocked",
        blocked_reason=capability.blocked_reason or "Capability is not available in this phase.",
    )


def _set_requirement_state(
    account: str,
    task_id: str,
    payload: dict[str, Any],
    requirement_id: str,
    coarse_state: str,
    *,
    blocked_reason: str | None = None,
) -> None:
    updated = dict(payload)
    updated_requirements: list[dict[str, Any]] = []
    for item in updated.get("requirements", []):
        if not isinstance(item, dict):
            continue
        row = dict(item)
        if row.get("id") == requirement_id:
            row["coarse_state"] = coarse_state
            if blocked_reason:
                row["blocked_reason"] = blocked_reason
            elif coarse_state != "blocked":
                row.pop("blocked_reason", None)
        updated_requirements.append(row)
    updated["requirements"] = updated_requirements
    model.write_requirements(account, task_id, updated)


def _append_blocked_status(account: str, task_id: str, requirement: dict[str, Any], reason: str) -> None:
    model.append_conversation_row(
        account,
        task_id,
        role="assistant",
        kind="coarse_status",
        text=f"Cannot complete yet: {reason}",
        requirement_id=str(requirement["id"]),
    )


def _run_status(statuses: list[str]) -> state.RunStatus:
    # Intentional precedence (honest-Q4): if ANY requirement hit the round cap,
    # the aggregate run honestly reports "capped" even when others delivered —
    # surfacing the best-effort caveat rather than hiding it behind "delivered".
    # A blocked aggregate is reserved for all-requirement real hub failures;
    # gate-off deferrals stay "deferred". Per-requirement coarse_state stays
    # individually accurate regardless.
    if "capped" in statuses:
        return "capped"
    if statuses and all(status == "blocked" for status in statuses):
        return "blocked"
    if "deferred" in statuses and "delivered" not in statuses and "capped" not in statuses:
        return "deferred"
    if "deferred" in statuses and "delivered" in statuses:
        return "delivered"
    if "delivered" in statuses:
        return "delivered"
    return "deferred"


__all__ = ["OrchestrationView", "run_orchestration"]

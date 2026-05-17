# SPDX-License-Identifier: Apache-2.0
"""Local multi-model critique loop with evidence-cited reconciliation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from noeticbraid_backend.platform.conversation import model
from noeticbraid_backend.platform.elicitation.local_ai import DEFAULT_TIMEOUT_SECONDS, run_local_task
from noeticbraid_backend.platform.orchestrate import state

MAX_ROUNDS = 3
CAP_MESSAGE = "已尽力，仍可改进 / Best effort; still can be improved."
DecisionClass = Literal["mechanical", "taste", "user_challenge"]


@dataclass(frozen=True, slots=True)
class ReviewerVerdict:
    reviewer_family: str
    issues: list[str]
    rationale: str
    confidence: float
    evidence_node_ids: list[str]

    @classmethod
    def from_json_dict(cls, payload: Any) -> "ReviewerVerdict":
        if not isinstance(payload, dict):
            raise ValueError("reviewer verdict must be an object")
        family = str(payload.get("reviewer_family") or "").strip()
        if not family:
            raise ValueError("reviewer_family required")
        issues_raw = payload.get("issues", [])
        evidence_raw = payload.get("evidence_node_ids", [])
        if not isinstance(issues_raw, list) or any(not isinstance(item, str) for item in issues_raw):
            raise ValueError("issues must be a list of strings")
        if not isinstance(evidence_raw, list) or any(not isinstance(item, str) for item in evidence_raw):
            raise ValueError("evidence_node_ids must be a list of strings")
        issues = [item.strip() for item in issues_raw if item.strip()]
        evidence = [item.strip() for item in evidence_raw if item.strip()]
        if issues and not evidence:
            raise ValueError("verdict issues require evidence_node_ids")
        confidence = float(payload.get("confidence", 0.0))
        if confidence < 0 or confidence > 1:
            raise ValueError("confidence must be in [0,1]")
        return cls(
            reviewer_family=family,
            issues=issues,
            rationale=str(payload.get("rationale") or "").strip(),
            confidence=confidence,
            evidence_node_ids=evidence,
        )

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "reviewer_family": self.reviewer_family,
            "issues": list(self.issues),
            "rationale": self.rationale,
            "confidence": self.confidence,
            "evidence_node_ids": list(self.evidence_node_ids),
        }


@dataclass(frozen=True, slots=True)
class ConsolidatedDirective:
    directive_text: str
    decision_class: DecisionClass
    evidence_node_ids: list[str]
    source_verdict_refs: list[str]

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "directive_text": self.directive_text,
            "decision_class": self.decision_class,
            "evidence_node_ids": list(self.evidence_node_ids),
            "source_verdict_refs": list(self.source_verdict_refs),
        }


@dataclass(frozen=True, slots=True)
class CritiqueResult:
    status: Literal["delivered", "capped", "deferred", "failed"]
    artifact: dict[str, Any]
    artifact_ref: str
    evidence_node_ids: list[str]
    rounds: list[dict[str, Any]] = field(default_factory=list)
    terminated_by: str = "consensus"
    decision_class: str = "mechanical"
    low_confidence: bool = False
    reason: str | None = None


def reconcile_verdicts(verdicts: list[ReviewerVerdict]) -> ConsolidatedDirective:
    material = [verdict for verdict in verdicts if verdict.issues]
    if not material:
        return ConsolidatedDirective("No material issues remain.", "mechanical", [], [])
    clusters: dict[frozenset[str], dict[str, Any]] = {}
    for verdict in material:
        key = frozenset(verdict.evidence_node_ids)
        cluster = clusters.setdefault(key, {"weight": 0.0, "issues": [], "families": []})
        cluster["weight"] += verdict.confidence * max(1, len(verdict.issues))
        cluster["issues"].extend(verdict.issues)
        cluster["families"].append(verdict.reviewer_family)
    key, cluster = max(clusters.items(), key=lambda item: (item[1]["weight"], sorted(item[0])))
    issues = _dedupe_strings(cluster["issues"])
    evidence = sorted(key)
    directive_text = "Address these evidence-cited issues: " + "; ".join(issues)
    decision_class = classify_decision(issues)
    source_refs = [f"reviewer:{family}" for family in _dedupe_strings(cluster["families"])]
    return ConsolidatedDirective(directive_text, decision_class, evidence, source_refs)


def classify_decision(issues: list[str]) -> DecisionClass:
    text = "\n".join(issues).lower()
    if any(marker in text for marker in ("contradicts user", "against the user", "user explicitly", "scope change")):
        return "user_challenge"
    if any(marker in text for marker in ("taste", "style", "tone", "preference", "voice")):
        return "taste"
    return "mechanical"


def run_critique_loop(
    account: str,
    task_id: str,
    requirement: dict[str, Any],
    artifact: dict[str, Any],
    initial_evidence_node_id: str,
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    reviewer_families: tuple[str, str] = ("codex", "gemini"),
) -> CritiqueResult:
    current_artifact = dict(artifact)
    current_evidence = [initial_evidence_node_id]
    current_ref = state.round_artifact_ref(task_id, 1, f"fanout_{requirement['id']}")
    previous_score = 0.0
    prior_directive: dict[str, Any] | None = None
    round_rows: list[dict[str, Any]] = []
    for round_no in range(1, MAX_ROUNDS + 1):
        verdicts: list[ReviewerVerdict] = []
        for family in reviewer_families:
            verdict_result = _call_reviewer(
                family,
                account=account,
                task_id=task_id,
                requirement=requirement,
                artifact=current_artifact,
                evidence_node_ids=current_evidence,
                round_no=round_no,
                prior_directive=prior_directive,
                timeout=timeout,
            )
            if isinstance(verdict_result, CritiqueResult):
                return verdict_result
            verdicts.append(verdict_result)
        families = {verdict.reviewer_family for verdict in verdicts}
        if len(families) < 2:
            return CritiqueResult(
                status="delivered",
                artifact=current_artifact,
                artifact_ref=current_ref,
                evidence_node_ids=current_evidence,
                rounds=round_rows,
                terminated_by="marginal",
                low_confidence=True,
                reason="single-reviewer, low-confidence",
            )
        if all(not verdict.issues for verdict in verdicts):
            return CritiqueResult(
                status="delivered",
                artifact=current_artifact,
                artifact_ref=current_ref,
                evidence_node_ids=current_evidence,
                rounds=round_rows,
                terminated_by="consensus",
            )
        directive = reconcile_verdicts(verdicts)
        directive_ref, directive_evidence = state.write_round_artifact(
            account,
            task_id,
            round_no,
            f"directive_{round_no}",
            {"directive": directive.to_json_dict()},
        )
        round_rows.append(
            {
                "round": round_no,
                "artifact_ref": directive_ref,
                "decision_class": directive.decision_class,
                "terminated_by": "in_progress",
            }
        )
        prior_directive = directive.to_json_dict()
        if directive.decision_class in {"taste", "user_challenge"}:
            _append_user_gate(account, task_id, requirement, directive)
            return CritiqueResult(
                status="deferred",
                artifact=current_artifact,
                artifact_ref=current_ref,
                evidence_node_ids=[*current_evidence, directive_evidence],
                rounds=round_rows,
                terminated_by=directive.decision_class,
                decision_class=directive.decision_class,
            )
        # §5 "whichever first": the cap supersedes on the final round, so the
        # marginal-delta exit below is reachable only on rounds 1–2 (and gated
        # round_no > 1 → effectively round 2). Round-3 marginal is dead by
        # construction and intentional — do not "fix" by reordering.
        if round_no == MAX_ROUNDS:
            model.append_conversation_row(
                account,
                task_id,
                role="assistant",
                kind="coarse_status",
                text=CAP_MESSAGE,
                requirement_id=str(requirement["id"]),
            )
            return CritiqueResult(
                status="capped",
                artifact=current_artifact,
                artifact_ref=current_ref,
                evidence_node_ids=[*current_evidence, directive_evidence],
                rounds=round_rows,
                terminated_by="MAX_ROUNDS",
                decision_class="mechanical",
            )
        revision = _apply_directive(requirement, current_artifact, directive, timeout=timeout)
        if revision.get("ok") is not True:
            return CritiqueResult(
                status="failed",
                artifact=current_artifact,
                artifact_ref=current_ref,
                evidence_node_ids=current_evidence,
                rounds=round_rows,
                terminated_by="failed",
                reason=str(revision.get("error") or "local model unavailable"),
            )
        revised_artifact = revision.get("artifact") if isinstance(revision.get("artifact"), dict) else None
        if revised_artifact is None:
            revised_artifact = {"text": str(revision.get("text") or revision.get("content") or "").strip()}
        revised_ref, revised_evidence = state.write_round_artifact(
            account,
            task_id,
            round_no,
            f"revision_{round_no}_{requirement['id']}",
            {"artifact": revised_artifact},
        )
        current_artifact = revised_artifact
        current_ref = revised_ref
        current_evidence = [revised_evidence]
        next_score = _score_from_result(revision, previous_score + 0.1)
        if round_no > 1 and next_score - previous_score < 0.05:
            return CritiqueResult(
                status="delivered",
                artifact=current_artifact,
                artifact_ref=current_ref,
                evidence_node_ids=current_evidence,
                rounds=round_rows,
                terminated_by="marginal",
                decision_class="mechanical",
            )
        previous_score = next_score
    return CritiqueResult(
        status="failed",
        artifact=current_artifact,
        artifact_ref=current_ref,
        evidence_node_ids=current_evidence,
        rounds=round_rows,
        terminated_by="failed",
        reason="critique loop exhausted unexpectedly",
    )


def _call_reviewer(
    family: str,
    *,
    account: str,
    task_id: str,
    requirement: dict[str, Any],
    artifact: dict[str, Any],
    evidence_node_ids: list[str],
    round_no: int,
    prior_directive: dict[str, Any] | None,
    timeout: int,
) -> ReviewerVerdict | CritiqueResult:
    result = run_local_task(
        {
            "kind": "critique_review",
            "reviewer_family": family,
            "requirement": requirement,
            "artifact": artifact,
            "evidence_node_ids": evidence_node_ids,
            "round": round_no,
            "prior_directive": prior_directive,
        },
        timeout=timeout,
    )
    if result.get("ok") is not True:
        return CritiqueResult(
            status="failed",
            artifact=artifact,
            artifact_ref=state.round_artifact_ref(task_id, round_no, f"review_failed_{round_no}"),
            evidence_node_ids=evidence_node_ids,
            terminated_by="failed",
            reason=str(result.get("error") or "local model unavailable"),
        )
    raw_verdict = result.get("verdict") if isinstance(result.get("verdict"), dict) else result
    verdict = ReviewerVerdict.from_json_dict(raw_verdict)
    state.write_round_artifact(
        account,
        task_id,
        round_no,
        f"review_{_safe_family(verdict.reviewer_family)}_{round_no}",
        {"verdict": verdict.to_json_dict()},
    )
    return verdict


def _apply_directive(
    requirement: dict[str, Any],
    artifact: dict[str, Any],
    directive: ConsolidatedDirective,
    *,
    timeout: int,
) -> dict[str, Any]:
    return run_local_task(
        {
            "kind": "apply_revision_directive",
            "requirement": requirement,
            "artifact": artifact,
            "directive": directive.to_json_dict(),
        },
        timeout=timeout,
    )


def _append_user_gate(
    account: str,
    task_id: str,
    requirement: dict[str, Any],
    directive: ConsolidatedDirective,
) -> None:
    model.append_conversation_row(
        account,
        task_id,
        role="assistant",
        kind="question",
        text=(
            "A final decision is needed before I change this requirement: "
            f"{directive.directive_text}\n\nSuggested answer: Keep my confirmed direction unless I explicitly revise it."
        ),
        requirement_id=str(requirement["id"]),
    )


def _safe_family(value: str) -> str:
    safe = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in value.strip())
    return safe[:80] or "reviewer"


def _score_from_result(result: dict[str, Any], default: float) -> float:
    try:
        score = float(result.get("score", default))
    except (TypeError, ValueError):
        return default
    if score < 0:
        return 0.0
    if score > 1:
        return 1.0
    return score


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


__all__ = [
    "CAP_MESSAGE",
    "MAX_ROUNDS",
    "ConsolidatedDirective",
    "CritiqueResult",
    "ReviewerVerdict",
    "classify_decision",
    "reconcile_verdicts",
    "run_critique_loop",
]

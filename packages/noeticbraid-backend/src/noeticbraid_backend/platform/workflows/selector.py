# SPDX-License-Identifier: Apache-2.0
"""Deterministic workflow selection for confirmed requirements."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from noeticbraid_backend.platform.conversation import model
from noeticbraid_backend.platform.elicitation.capabilities import SUPPORTED_MODALITIES, capability_for
from noeticbraid_backend.platform.workflows.loader import discover_specs
from noeticbraid_backend.platform.workflows.schema import WorkflowSpec

FALLBACK_WORKFLOW_ID = "open_orchestration"
_SELECTION_QUESTION = (
    "I can proceed with a general plan, but the confirmed requirements do not identify one specific workflow. "
    "Which final output shape should I prioritize if you want to steer the next iteration?"
)
_SELECTION_SUGGESTED = "Proceed with the general orchestration workflow unless I specify a narrower output."


@dataclass(frozen=True, slots=True)
class SelectionResult:
    spec: WorkflowSpec
    score: int
    used_fallback: bool
    question_appended: bool
    reason: str


def select_workflow(
    requirements_payload: dict[str, Any],
    *,
    account: str | None = None,
    task_id: str | None = None,
    specs: tuple[WorkflowSpec, ...] | None = None,
) -> SelectionResult:
    if requirements_payload.get("status") != "confirmed":
        raise ValueError("requirements must be confirmed before workflow selection")
    candidates = specs or discover_specs()
    fallback = _fallback(candidates)
    requirements = [item for item in requirements_payload.get("requirements", []) if isinstance(item, dict)]
    scored: list[tuple[int, WorkflowSpec]] = []
    for spec in candidates:
        if spec.id == FALLBACK_WORKFLOW_ID:
            continue
        score = _score_spec(spec, requirements)
        if score is not None:
            scored.append((score, spec))
    positive = [(score, spec) for score, spec in scored if score > 0]
    if not positive:
        appended = _append_selection_question(account, task_id)
        return SelectionResult(fallback, 0, True, appended, "none")
    positive.sort(key=lambda item: (-item[0], item[1].id))
    top_score = positive[0][0]
    tied = [item for item in positive if item[0] == top_score]
    if len(tied) != 1:
        appended = _append_selection_question(account, task_id)
        return SelectionResult(fallback, top_score, True, appended, "tie")
    return SelectionResult(tied[0][1], top_score, False, False, "matched")


def _score_spec(spec: WorkflowSpec, requirements: list[dict[str, Any]]) -> int | None:
    reachable = set(SUPPORTED_MODALITIES)
    required = {capability_for(item).modality for item in spec.selector.required_capabilities}
    if not required.issubset(reachable):
        return None
    inferred_intents = _inferred_intents(requirements)
    deliverables = _inferred_deliverables(requirements)
    intent_score = len(set(spec.selector.intent_tags).intersection(inferred_intents))
    deliverable_score = 1 if set(spec.selector.deliverable_types).intersection(deliverables) else 0
    predicate_score = sum(1 for predicate in spec.selector.requirement_predicates if _predicate_truth(predicate, requirements))
    return intent_score + deliverable_score + predicate_score


def _fallback(specs: tuple[WorkflowSpec, ...]) -> WorkflowSpec:
    matches = [spec for spec in specs if spec.id == FALLBACK_WORKFLOW_ID]
    if len(matches) != 1:
        raise ValueError("open_orchestration fallback must exist exactly once")
    return matches[0]


def _append_selection_question(account: str | None, task_id: str | None) -> bool:
    if not account or not task_id:
        return False
    text = f"{_SELECTION_QUESTION}\n\nSuggested answer: {_SELECTION_SUGGESTED}"
    model.append_conversation_row(account, task_id, role="assistant", kind="question", text=text)
    return True


def _inferred_intents(requirements: list[dict[str, Any]]) -> set[str]:
    intents: set[str] = set()
    checks = {
        "research": ("research", "analyze", "analysis", "compare", "market", "调研", "研究", "分析", "比较"),
        "compare": ("compare", "comparison", "versus", "vs", "对比", "比较"),
        "synthesize": ("synthesize", "summary", "summarize", "report", "综合", "总结", "报告"),
        "draft": ("draft", "write", "document", "brief", "copy", "撰写", "文档", "简报"),
        "refine": ("refine", "edit", "polish", "revise", "润色", "修改"),
        "code": ("code", "bug", "repo", "test", "implement", "代码", "修复", "实现"),
        "review": ("review", "critique", "check", "评审", "检查"),
        "orchestrate": ("plan", "coordinate", "multi", "workflow", "规划", "协调"),
    }
    for item in requirements:
        modality = str(item.get("modality") or "").strip().lower()
        if modality:
            intents.add(modality)
        text = str(item.get("text") or "").lower()
        for intent, needles in checks.items():
            if any(needle in text for needle in needles):
                intents.add(intent)
    return intents


def _inferred_deliverables(requirements: list[dict[str, Any]]) -> set[str]:
    deliverables: set[str] = set()
    checks = {
        "report": ("report", "memo", "analysis", "报告", "分析"),
        "comparison_table": ("table", "compare", "matrix", "表", "对比"),
        "document": ("document", "brief", "draft", "doc", "文档", "简报"),
        "patch": ("patch", "fix", "implement", "diff", "修复", "实现"),
        "review_notes": ("review", "critique", "notes", "评审", "意见"),
        "plan": ("plan", "steps", "strategy", "计划", "步骤"),
    }
    for item in requirements:
        modality = str(item.get("modality") or "").strip().lower()
        if modality in {"document", "research", "code", "text"}:
            deliverables.add(modality)
        text = str(item.get("text") or "").lower()
        for deliverable, needles in checks.items():
            if any(needle in text for needle in needles):
                deliverables.add(deliverable)
    return deliverables


def _predicate_truth(predicate: str, requirements: list[dict[str, Any]]) -> bool:
    normalized = " ".join(str(predicate or "").strip().lower().split())
    all_text = "\n".join(str(item.get("text") or "") for item in requirements).lower()
    modalities = {str(item.get("modality") or "").strip().lower() for item in requirements}
    if normalized == "needs_multi_source == true":
        return any(word in all_text for word in ("sources", "multi-source", "research", "compare", "across"))
    if normalized == "needs_revision == true":
        return any(word in all_text for word in ("refine", "edit", "revise", "polish", "draft")) or "document" in modalities
    if normalized == "touches_code == true":
        return "code" in modalities or any(word in all_text for word in ("code", "repo", "bug", "test", "patch"))
    if normalized == "open_scope == true":
        return True
    return False


__all__ = ["FALLBACK_WORKFLOW_ID", "SelectionResult", "select_workflow"]

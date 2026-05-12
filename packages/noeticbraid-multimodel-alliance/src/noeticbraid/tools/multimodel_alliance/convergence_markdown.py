"""Concise markdown rendering for D2-01 convergence review.

The markdown is generated from structured records only and is never treated as
the source of truth.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .candidate_store import SDD_ID, UPGRADE_RULE, scan_forbidden_material


class ConvergenceMarkdownError(ValueError):
    """Raised when markdown generation receives unsafe structured data."""


def _line_items(values: list[str]) -> str:
    return ", ".join(f"`{value}`" for value in values) if values else "none"


def render_convergence_markdown(
    *,
    route: dict[str, Any],
    debate: dict[str, Any],
    convergence: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> str:
    """Render a deterministic review summary from structured records."""

    structured = {"route": route, "debate": debate, "convergence": convergence, "candidates": candidates}
    try:
        scan_forbidden_material(structured, "convergence_markdown_input")
    except ValueError as exc:
        raise ConvergenceMarkdownError(str(exc)) from exc

    selected = [f"`{item['model_ref']}` as `{item['role']}`" for item in route.get("selected_models", [])]
    unresolved = convergence.get("unresolved_disagreements", [])
    decisions = convergence.get("user_decision_requirements", [])
    actions = convergence.get("next_actions", [])
    candidate_lines = [
        f"- `{candidate['candidate_id']}` — status `{candidate['status']}`; decision `{candidate['decision_status']}`; upgrade: {candidate['upgrade_rule']}"
        for candidate in candidates
    ] or ["- none"]
    unresolved_lines = [
        f"- `{item['objection_id']}` ({item['severity']} → {item['carried_to']}): {item['summary']}"
        for item in unresolved
    ] or ["- none"]
    decision_lines = [
        f"- `{item['decision_id']}` blocking={item['blocking']}: {item['question']}"
        for item in decisions
    ] or ["- none"]
    action_lines = [
        f"- `{item['action_id']}` [{item['owner']}/{item['status']}]: {item['action']}"
        for item in actions
    ] or ["- none"]

    lines = [
        "# SDD-D2-01 Multimodel Debate Convergence",
        "",
        "> Source of truth: structured ModelRoute, Debate, Convergence, and candidate JSONL records. This markdown is a concise review artifact only.",
        "",
        "## Record chain",
        "",
        f"- SDD: `{SDD_ID}`",
        f"- Task: `{route['task_id']}`",
        f"- Route: `{route['route_id']}` (`{route['route_type']}` / `{route['risk_level']}`)",
        f"- Debate: `{debate['debate_id']}` with {len(debate.get('rounds', []))} round(s)",
        f"- Convergence: `{convergence['convergence_id']}` decision `{convergence['decision_status']}`",
        "- Markdown source: structured records only; provider transcripts are excluded.",
        "",
        "## Fixed participants",
        "",
        *(f"- {item}" for item in selected),
        "",
        "## Evidence refs",
        "",
        f"- Sources: {_line_items(route.get('source_refs', []))}",
        f"- Artifacts: {_line_items(sorted({ref for round_record in debate.get('rounds', []) for ref in [round_record.get('artifact_ref')] if ref}))}",
        "",
        "## Convergence result",
        "",
        convergence.get("recommendation", ""),
        "",
        "### Unresolved disagreements",
        "",
        *unresolved_lines,
        "",
        "### User decision requirements",
        "",
        *decision_lines,
        "",
        "### Next actions",
        "",
        *action_lines,
        "",
        "## Candidate records",
        "",
        *candidate_lines,
        "",
        "## R-6 upgrade gate",
        "",
        UPGRADE_RULE,
    ]
    return "\n".join(lines)


def write_convergence_markdown(path: str | Path, **kwargs: Any) -> Path:
    """Write generated convergence markdown to ``path``."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_convergence_markdown(**kwargs), encoding="utf-8")
    return target

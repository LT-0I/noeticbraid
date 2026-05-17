# SPDX-License-Identifier: Apache-2.0
"""MECE audit for the shipped workflow library."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from noeticbraid_backend.platform.workflows.loader import discover_specs
from noeticbraid_backend.platform.workflows.selector import FALLBACK_WORKFLOW_ID
from noeticbraid_backend.platform.workflows.schema import WorkflowSpec

MAX_SELECTABLE = 6


@dataclass(frozen=True, slots=True)
class AuditResult:
    ok: bool
    messages: tuple[str, ...]
    selectable_count: int


def audit_library(library_dir: Path | None = None) -> AuditResult:
    messages: list[str] = []
    try:
        specs = discover_specs(library_dir)
    except Exception as exc:
        return AuditResult(False, (f"parse/validate FAIL: {exc}",), 0)
    ids = [spec.id for spec in specs]
    if len(ids) != len(set(ids)):
        messages.append("duplicate id FAIL")
    if len(specs) > MAX_SELECTABLE:
        messages.append(f"selectable count FAIL: {len(specs)} > {MAX_SELECTABLE}")
    fallback = [spec for spec in specs if spec.id == FALLBACK_WORKFLOW_ID]
    if len(fallback) != 1 or not _is_zero_requirement_fallback(fallback[0]):
        messages.append("open_orchestration fallback FAIL")
    seen_shapes: dict[tuple[tuple[str, ...], tuple[str, ...]], str] = {}
    for spec in specs:
        if spec.id == FALLBACK_WORKFLOW_ID:
            continue
        shape = (tuple(sorted(spec.selector.intent_tags)), tuple(sorted(spec.selector.deliverable_types)))
        other = seen_shapes.get(shape)
        if other is not None:
            messages.append(f"non-fallback overlap FAIL: {other} and {spec.id}")
        seen_shapes[shape] = spec.id
    if not messages:
        messages.append(f"MECE PASS selectable={len(specs)}")
    return AuditResult(not any("FAIL" in message for message in messages), tuple(messages), len(specs))


def _is_zero_requirement_fallback(spec: WorkflowSpec) -> bool:
    selector = spec.selector
    return not (
        selector.intent_tags
        or selector.deliverable_types
        or selector.required_capabilities
        or selector.excluded_capabilities
        or selector.requirement_predicates
    )


def main() -> int:
    result = audit_library()
    for message in result.messages:
        print(message)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["AuditResult", "audit_library", "main"]

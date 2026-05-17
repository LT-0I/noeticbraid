# SPDX-License-Identifier: Apache-2.0
"""Discovery and validation for shipped workflow specs."""

from __future__ import annotations

import json
from pathlib import Path

from noeticbraid_backend.platform.workflows.schema import WorkflowSpec

LIBRARY_DIR = Path(__file__).parent / "library"


def discover_specs(library_dir: Path | None = None) -> tuple[WorkflowSpec, ...]:
    base = library_dir or LIBRARY_DIR
    specs: list[WorkflowSpec] = []
    seen: set[str] = set()
    for path in sorted(base.glob("*.workflow.json")):
        if "/_internal/" in path.as_posix():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        spec = WorkflowSpec.from_json_dict(payload)
        if spec.id in seen:
            raise ValueError(f"duplicate workflow id: {spec.id}")
        seen.add(spec.id)
        specs.append(spec)
    specs.sort(key=lambda spec: (spec.id == "open_orchestration", spec.id))
    return tuple(specs)


def spec_by_id(workflow_id: str, specs: tuple[WorkflowSpec, ...] | None = None) -> WorkflowSpec:
    target = str(workflow_id or "").strip()
    for spec in specs or discover_specs():
        if spec.id == target:
            return spec
    raise ValueError(f"workflow id not found: {target}")


__all__ = ["LIBRARY_DIR", "discover_specs", "spec_by_id"]

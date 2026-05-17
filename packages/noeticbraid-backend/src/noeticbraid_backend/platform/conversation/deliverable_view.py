# SPDX-License-Identifier: Apache-2.0
"""Read-only per-task deliverable view for final orchestration artifacts."""

from __future__ import annotations

from typing import Any

from noeticbraid_backend.platform.conversation import model
from noeticbraid_backend.platform.elicitation.capabilities import capability_for
from noeticbraid_backend.platform.orchestrate import state
from noeticbraid_backend.platform.tasks.models import validate_task_id
from noeticbraid_backend.platform.workspace_paths import resolve_user_path


def per_task_deliverables(account: str, task_id: str) -> list[dict[str, Any]]:
    tid = validate_task_id(task_id)
    run_state = state.load_state(account, tid)
    requirements = model.load_requirements(account, tid)
    final_refs = _final_artifact_refs(account, tid, run_state)
    rows: list[dict[str, Any]] = []
    for requirement in requirements.get("requirements", []):
        if not isinstance(requirement, dict):
            continue
        req_id = str(requirement.get("id") or "")
        row: dict[str, Any] = {
            "requirement_id": req_id,
            "title": str(requirement.get("text") or ""),
        }
        download_ref = final_refs.get(req_id)
        if requirement.get("coarse_state") == "done" and download_ref:
            row["status"] = "delivered"
            row["download_ref"] = download_ref
        else:
            row["status"] = "blocked"
            row["blocked_reason"] = _blocked_reason(requirement)
        rows.append(row)
    return rows


def _final_artifact_refs(account: str, task_id: str, run_state: dict[str, Any] | None) -> dict[str, str]:
    refs: dict[str, str] = {}
    # Resolve symlinks before containment checks so a symlink inside final/
    # cannot escape the account root while still passing is_relative_to
    # (mirrors resolve_user_path's own realpath posture).
    account_root = resolve_user_path(account, ".").resolve()
    final_dir = resolve_user_path(account, f"tasks/{task_id}/orchestration/final").resolve()
    if not final_dir.is_dir() or not final_dir.is_relative_to(account_root):
        return refs
    state_refs = set()
    if run_state is not None:
        for round_row in run_state.get("rounds", []):
            if not isinstance(round_row, dict):
                continue
            artifact_ref = round_row.get("artifact_ref")
            if isinstance(artifact_ref, str) and artifact_ref.startswith(f"tasks/{task_id}/orchestration/final/"):
                state_refs.add(artifact_ref)
    for path in sorted(final_dir.glob("final_*.json")):
        resolved = path.resolve()
        if not resolved.is_file() or resolved.stat().st_size <= 0 or not resolved.is_relative_to(account_root):
            continue
        req_id = path.stem.removeprefix("final_")
        ref = f"tasks/{task_id}/orchestration/final/{path.name}"
        if state_refs and ref not in state_refs:
            continue
        refs[req_id] = ref
    return refs


def _blocked_reason(requirement: dict[str, Any]) -> str:
    reason = requirement.get("blocked_reason")
    if isinstance(reason, str) and reason:
        return reason
    capability = capability_for(str(requirement.get("modality") or "text"))
    if capability.blocked_reason:
        return capability.blocked_reason
    # House-style honest copy: zh-canonical, calm (not error-toned), matching
    # the capability-registry blocked_reason strings. The console renders
    # blocked_reason verbatim (as it does for capability/engine reasons), so a
    # single zh-canonical source keeps every blocked_reason consistent rather
    # than splitting one generic case across the i18n layer.
    return "最终结果尚未生成。"


__all__ = ["per_task_deliverables"]

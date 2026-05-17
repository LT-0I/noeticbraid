# SPDX-License-Identifier: Apache-2.0
"""Engineering-only orchestration state stored by path reference.

Forward-compat reader rule: readers MUST treat an absent ``hub`` round
field as ``false`` and MUST NOT reject unknown additive round keys.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal

from noeticbraid_backend.platform.conversation import model
from noeticbraid_backend.platform.tasks.models import validate_task_id
from noeticbraid_backend.platform.workspace_paths import resolve_user_path

SCHEMA_VERSION = 1
ORCHESTRATION_FILENAME = "orchestration.json"
RunStatus = Literal["running", "delivered", "capped", "deferred", "blocked"]
_STATUSES = frozenset({"running", "delivered", "capped", "deferred", "blocked"})
_NODE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,120}$")


def orchestration_path_for(account: str, task_id: str) -> Path:
    return resolve_user_path(account, f"tasks/{validate_task_id(task_id)}/{ORCHESTRATION_FILENAME}")


def round_artifact_ref(task_id: str, round_no: int, node_id: str) -> str:
    tid = validate_task_id(task_id)
    node = _validate_node_id(node_id)
    if round_no < 1:
        raise ValueError("round must be positive")
    return f"tasks/{tid}/orchestration/round_{round_no}/{node}.json"


def final_artifact_ref(task_id: str, node_id: str) -> str:
    tid = validate_task_id(task_id)
    node = _validate_node_id(node_id)
    return f"tasks/{tid}/orchestration/final/{node}.json"


def write_round_artifact(account: str, task_id: str, round_no: int, node_id: str, payload: dict[str, Any]) -> tuple[str, str]:
    ref = round_artifact_ref(task_id, round_no, node_id)
    model._atomic_write_json(resolve_user_path(account, ref), dict(payload))
    return ref, f"round_{round_no}:{_validate_node_id(node_id)}"


def write_final_artifact(account: str, task_id: str, node_id: str, payload: dict[str, Any]) -> str:
    ref = final_artifact_ref(task_id, node_id)
    model._atomic_write_json(resolve_user_path(account, ref), dict(payload))
    return ref


def initial_state(task_id: str, selected_workflow_id: str) -> dict[str, Any]:
    return {
        "task_id": validate_task_id(task_id),
        "schema_version": SCHEMA_VERSION,
        "selected_workflow_id": str(selected_workflow_id),
        "status": "running",
        "rounds": [],
        "updated_ts": model.now_ts(),
    }


def append_round(
    payload: dict[str, Any],
    *,
    round_no: int,
    artifact_ref: str,
    decision_class: str,
    terminated_by: str,
    hub: bool = False,
) -> dict[str, Any]:
    updated = validate_state(payload)
    rounds = list(updated["rounds"])
    row: dict[str, Any] = {
        "round": int(round_no),
        "artifact_ref": str(artifact_ref),
        "decision_class": str(decision_class),
        "terminated_by": str(terminated_by),
    }
    if hub:
        row["hub"] = True
    rounds.append(row)
    updated["rounds"] = rounds
    updated["updated_ts"] = model.now_ts()
    return validate_state(updated)


def set_status(payload: dict[str, Any], status: RunStatus) -> dict[str, Any]:
    updated = validate_state(payload)
    if status not in _STATUSES:
        raise ValueError("invalid orchestration status")
    updated["status"] = status
    updated["updated_ts"] = model.now_ts()
    return validate_state(updated)


def write_state(account: str, task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    validated = validate_state(payload, expected_task_id=task_id)
    model._atomic_write_json(orchestration_path_for(account, task_id), validated)
    return validated


def load_state(account: str, task_id: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(orchestration_path_for(account, task_id).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    if not isinstance(payload, dict):
        raise ValueError("orchestration state must be an object")
    return validate_state(payload, expected_task_id=task_id)


def current_phase(account: str, task_id: str, requirements_payload: dict[str, Any]) -> RunStatus:
    payload = load_state(account, task_id)
    if payload is not None:
        return payload["status"]
    states = {str(item.get("coarse_state") or "pending") for item in requirements_payload.get("requirements", []) if isinstance(item, dict)}
    if "in_progress" in states:
        return "running"
    if states and states.issubset({"done", "blocked"}) and "done" in states:
        return "delivered"
    if states and states.issubset({"blocked"}):
        return "blocked"
    return "deferred"


def validate_state(payload: dict[str, Any], *, expected_task_id: str | None = None) -> dict[str, Any]:
    task_id = validate_task_id(str(payload["task_id"]))
    if expected_task_id is not None and task_id != validate_task_id(expected_task_id):
        raise ValueError("orchestration task mismatch")
    if int(payload.get("schema_version")) != SCHEMA_VERSION:
        raise ValueError("unsupported orchestration schema")
    workflow_id = str(payload.get("selected_workflow_id") or "").strip()
    if not workflow_id:
        raise ValueError("selected_workflow_id required")
    status = str(payload.get("status") or "")
    if status not in _STATUSES:
        raise ValueError("invalid orchestration status")
    rounds_raw = payload.get("rounds")
    if not isinstance(rounds_raw, list):
        raise ValueError("rounds must be a list")
    rounds: list[dict[str, Any]] = []
    for item in rounds_raw:
        if not isinstance(item, dict):
            raise ValueError("round entry must be an object")
        round_no = int(item.get("round"))
        if round_no < 1:
            raise ValueError("round must be positive")
        artifact_ref = str(item.get("artifact_ref") or "").strip()
        prefix = f"tasks/{task_id}/orchestration/"
        if not artifact_ref.startswith(prefix):
            raise ValueError("artifact_ref must be task-relative orchestration path")
        row = dict(item)
        row["round"] = round_no
        row["artifact_ref"] = artifact_ref
        row["decision_class"] = str(item.get("decision_class") or "")
        row["terminated_by"] = str(item.get("terminated_by") or "")
        if item.get("hub") is True:
            row["hub"] = True
        elif "hub" in row:
            row.pop("hub", None)
        rounds.append(row)
    updated_ts = str(payload.get("updated_ts") or "").strip()
    if not updated_ts:
        raise ValueError("updated_ts required")
    return {
        "task_id": task_id,
        "schema_version": SCHEMA_VERSION,
        "selected_workflow_id": workflow_id,
        "status": status,
        "rounds": rounds,
        "updated_ts": updated_ts,
    }


def _validate_node_id(node_id: str) -> str:
    node = str(node_id or "").strip()
    if _NODE_ID_RE.fullmatch(node) is None:
        raise ValueError("invalid node id")
    return node


__all__ = [
    "ORCHESTRATION_FILENAME",
    "RunStatus",
    "append_round",
    "current_phase",
    "final_artifact_ref",
    "initial_state",
    "load_state",
    "orchestration_path_for",
    "round_artifact_ref",
    "set_status",
    "validate_state",
    "write_final_artifact",
    "write_round_artifact",
    "write_state",
]

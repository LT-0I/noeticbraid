# SPDX-License-Identifier: Apache-2.0
"""Single platform chokepoint for D10 web-ai hub dispatch."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import noeticbraid_backend.omc_workspace.web_ai_hub_automation as _automation
from noeticbraid_backend.omc_workspace import web_ai_hub_compat as compat
from noeticbraid_backend.omc_workspace.web_ai_hub_client import sanitize_error_msg
from noeticbraid_backend.platform.workspace_paths import resolve_user_path

BLOCKED_HUB_STATUSES = frozenset({"not_implemented", "HUB_NOT_BUILT", "approval_required", "error"})
redact_hub_response = _automation.redact_hub_response


def dispatch(
    op: str,
    params: dict[str, Any],
    *,
    account: str | None = None,
    task_id: str | None = None,
) -> dict[str, Any]:
    """Dispatch one closed-set hub operation and normalize fail-closed outcomes."""

    operation = str(op or "")
    if operation not in compat.DISPATCHABLE:
        payload = redact_hub_response(
            {"status": "not_implemented", "reason": "operation not dispatchable in platform C3"}
        )
        return _blocked(payload)

    if not isinstance(params, dict):
        payload = redact_hub_response({"status": "not_implemented", "reason": "params must be an object"})
        return _blocked(payload)

    raw = _automation.dispatch_web_ai(operation, dict(params), account=account, task_id=task_id)
    payload = redact_hub_response(
        raw,
        task_id=task_id,
        validated_artifact_path=_artifact_path_for_redaction(raw, account=account, task_id=task_id),
    )
    status = str(payload.get("status") or "")
    if status != "ok" or status in BLOCKED_HUB_STATUSES:
        return _blocked(payload)
    return {"outcome": "ok", "status": status or "ok", "payload": payload}


def _artifact_path_for_redaction(
    raw: object,
    *,
    account: str | None,
    task_id: str | None,
) -> Path | None:
    if not isinstance(raw, dict) or not account or not task_id:
        return None
    value = raw.get("path")
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    try:
        candidate = Path(text)
        if candidate.is_absolute():
            root = resolve_user_path(account, ".")
            artifact_path = Path(os.path.realpath(candidate))
            if not artifact_path.is_relative_to(root):
                return None
        else:
            if not text.replace("\\", "/").startswith(f"tasks/{task_id}/artifacts/"):
                return None
            artifact_path = resolve_user_path(account, text)
        if artifact_path.is_file():
            return artifact_path
    except Exception:
        return None
    return None


def _blocked(payload: dict[str, Any]) -> dict[str, Any]:
    status = str(payload.get("status") or "not_implemented")
    reason = sanitize_error_msg(
        str(payload.get("reason") or payload.get("message") or status or "hub dispatch blocked"),
        max_chars=512,
    )
    return {
        "outcome": "blocked",
        "status": status,
        "reason": reason or "hub dispatch blocked",
        "payload": payload,
    }


__all__ = ["BLOCKED_HUB_STATUSES", "dispatch", "redact_hub_response"]

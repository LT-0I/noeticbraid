# SPDX-License-Identifier: Apache-2.0
"""Single platform chokepoint for D10 web-ai hub dispatch."""

from __future__ import annotations

from typing import Any

import noeticbraid_backend.omc_workspace.web_ai_hub_automation as _automation
from noeticbraid_backend.omc_workspace import web_ai_hub_compat as compat
from noeticbraid_backend.omc_workspace.web_ai_hub_client import sanitize_error_msg

BLOCKED_HUB_STATUSES = frozenset({"not_implemented", "HUB_NOT_BUILT", "approval_required", "error"})


def redact_hub_response(raw: Any) -> dict[str, Any]:
    """Re-assert hub response redaction at the platform boundary."""

    return _automation.redact_hub_response(raw)


def dispatch(op: str, params: dict[str, Any]) -> dict[str, Any]:
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

    raw = _automation.dispatch_web_ai(operation, dict(params))
    payload = redact_hub_response(raw)
    status = str(payload.get("status") or "")
    if payload.get("ok") is not True or status in BLOCKED_HUB_STATUSES:
        return _blocked(payload)
    return {"outcome": "ok", "status": status or "ok", "payload": payload}


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

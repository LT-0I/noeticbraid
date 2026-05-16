# SPDX-License-Identifier: Apache-2.0
"""Fail-closed web-ai hub automation gate for SDD-D10-01."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from . import web_ai_hub_compat as compat
from .web_ai_hub_client import run_hub_command, sanitize_error_msg

_WAH_CDP_HOST = "WAH_CDP_HOST"
_WAH_CDP_PORT = "WAH_CDP_PORT"
_WAH_BROWSER_EXECUTABLE = "WAH_BROWSER_EXECUTABLE"
_WAH_AUTO_CONFIRM = "WAH_AUTO_CONFIRM"


def web_ai_hub_gate(operation: str, *, environ=os.environ) -> dict[str, Any]:
    """Return the D10-01 automation readiness decision without dispatching operations."""

    try:
        return _web_ai_hub_gate(operation, environ=environ)
    except Exception as exc:  # pragma: no cover - defensive fail-closed boundary
        sanitized = sanitize_error_msg(str(exc))
        return {"status": "not_implemented", "reason": sanitized or "web-ai automation gate failed"}


def build_hub_env(environ, *, pageful: bool) -> dict[str, str]:
    """Return a subprocess env copy with D10 CDP injection and confirmation scrubbed.

    ``WAH_AUTO_CONFIRM`` is scrubbed defensively: noeticbraid must never inherit or synthesize
    hub auto-confirm state; D10-02+ must carry this invariant forward.
    """

    env = {str(key): str(value) for key, value in dict(environ).items()}
    env.pop(_WAH_BROWSER_EXECUTABLE, None)
    env.pop(_WAH_AUTO_CONFIRM, None)
    if pageful:
        endpoint = _read_cdp_endpoint(environ)
        if endpoint is not None:
            host, port = endpoint
            env[_WAH_CDP_HOST] = host
            env[_WAH_CDP_PORT] = port
    return env


def _web_ai_hub_gate(operation: str, *, environ) -> dict[str, Any]:
    op = str(operation or "")

    if not compat.read_automation_enabled(environ):
        return {"status": "not_implemented", "reason": "web-ai automation opt-in disabled"}

    if not compat.is_allowed_operation(op):
        return {"status": "not_implemented", "reason": "operation not allowed"}

    hub_path_raw = environ.get(compat.HUB_PATH_ENV)
    if not hub_path_raw:
        return {"status": "not_implemented", "reason": "hub path unavailable"}
    hub_path = Path(str(hub_path_raw))
    if not hub_path.is_absolute() or not hub_path.is_dir():
        return {"status": "not_implemented", "reason": "hub path unavailable"}

    digest_status, _detail = compat.digest_matches(hub_path)
    if digest_status == "not_built":
        return {"status": "HUB_NOT_BUILT"}
    if digest_status in {"uncomputable", "mismatch"}:
        return {
            "status": "not_implemented",
            "reason": "hub exec closure unpinned/mismatch — manual review & re-pin required",
        }
    if digest_status != "ok":
        return {
            "status": "not_implemented",
            "reason": "hub exec closure unpinned/mismatch — manual review & re-pin required",
        }

    tool_names = _probe_tool_names(hub_path)
    if tool_names is None:
        return {"status": "not_implemented", "reason": "hub capability probe failed"}
    if op not in tool_names:
        return {"status": "not_implemented", "reason": "hub capability absent"}

    pageful = compat.is_pageful(op)
    if pageful:
        endpoint = _read_cdp_endpoint(environ)
        if endpoint is None:
            return {"status": "not_implemented", "reason": "trusted CDP endpoint not configured"}
        if not _cdp_endpoint_reachable(*endpoint):
            return {
                "status": "not_implemented",
                "reason": "trusted CDP endpoint unreachable — operator must provision",
            }

    return {
        "status": "ready",
        "operation": op,
        "classification": "pageful" if pageful else "launch_safe",
        "cdp_endpoint_verified": pageful,
    }


def _probe_tool_names(hub_path: Path) -> set[str] | None:
    try:
        payload = run_hub_command(["mcp:tools", "--json"], hub_path=hub_path, timeout=15)
    except Exception:
        return None
    if isinstance(payload, list):
        tools_payload: Any = payload
    elif isinstance(payload, dict):
        if payload.get("error_type") or payload.get("ok") is False:
            return None
        tools_payload = payload.get("data")
        if tools_payload is None:
            tools_payload = payload.get("tools")
    else:
        return None
    if not isinstance(tools_payload, list):
        return None
    names = {item.get("name") for item in tools_payload if isinstance(item, dict) and isinstance(item.get("name"), str)}
    return names or None


def _read_cdp_endpoint(environ) -> tuple[str, str] | None:
    host = str(environ.get(compat.CDP_HOST_ENV) or compat.CDP_HOST_DEFAULT).strip() or compat.CDP_HOST_DEFAULT
    raw_port = str(environ.get(compat.CDP_PORT_ENV) or "").strip()
    try:
        port_int = int(raw_port)
    except ValueError:
        return None
    if not 1 <= port_int <= 65535:
        return None
    return host, str(port_int)


def _cdp_endpoint_reachable(host: str, port: str) -> bool:
    url = f"http://{host}:{port}/json/version"
    response = None
    try:
        response = urllib.request.urlopen(url, timeout=compat.CDP_PREFLIGHT_TIMEOUT_SECONDS)
        status = getattr(response, "status", None)
        if status is None and hasattr(response, "getcode"):
            status = response.getcode()
        if not isinstance(status, int) or not 200 <= status < 300:
            return False
        json.loads(response.read().decode("utf-8"))
    except (
        AttributeError,
        OSError,
        TimeoutError,
        urllib.error.URLError,
        urllib.error.HTTPError,
        ValueError,
        json.JSONDecodeError,
    ):
        return False
    finally:
        if response is not None and hasattr(response, "close"):
            response.close()
    return True


__all__ = ["build_hub_env", "web_ai_hub_gate"]

# SPDX-License-Identifier: Apache-2.0
"""Fail-closed web-ai hub automation gate for SDD-D10-01."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from . import web_ai_hub_compat as compat
from .web_ai_hub_client import run_hub_command, sanitize_error_msg

_WAH_CDP_HOST = "WAH_CDP_HOST"
_WAH_CDP_PORT = "WAH_CDP_PORT"
_WAH_BROWSER_EXECUTABLE = "WAH_BROWSER_EXECUTABLE"
_WAH_AUTO_CONFIRM = "WAH_AUTO_CONFIRM"
_CONFIRMED = "confirmed"


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
    env.pop(_CONFIRMED, None)
    if pageful:
        endpoint = _read_cdp_endpoint(environ)
        if endpoint is not None:
            host, port = endpoint
            env[_WAH_CDP_HOST] = host
            env[_WAH_CDP_PORT] = port
    return env


def dispatch_web_ai(operation: str, params, *, environ=os.environ) -> dict[str, Any]:
    """Dispatch the D10-02 web-ai hub operation subset with fail-closed guards."""

    try:
        snap = dict(environ)
        gate = web_ai_hub_gate(operation, environ=snap)
        if gate.get("status") != "ready":
            return gate

        op = str(operation or "")
        if op not in compat.DISPATCHABLE_D10_02:
            return {"status": "not_implemented", "reason": "operation not dispatchable in D10-02"}

        argv_tail, err = compat.validate_request(op, params)
        if err is not None or argv_tail is None:
            return {"status": "not_implemented", "reason": err or "request rejected: invalid request"}

        hub_path_raw = snap.get(compat.HUB_PATH_ENV)
        if not hub_path_raw:
            return {"status": "not_implemented", "reason": "hub path unavailable"}
        hub_path = Path(str(hub_path_raw))
        if not hub_path.is_absolute() or not hub_path.is_dir():
            return {"status": "not_implemented", "reason": "hub path unavailable"}

        digest_status, _detail = compat.digest_matches(hub_path)
        if digest_status == "not_built":
            return {"status": "HUB_NOT_BUILT"}
        if digest_status != "ok":
            return {
                "status": "not_implemented",
                "reason": "hub exec closure unpinned/mismatch — manual review & re-pin required",
            }

        pageful = compat.is_pageful(op)
        env = build_hub_env(snap, pageful=pageful)
        raw = run_hub_command(
            argv_tail,
            hub_path=hub_path,
            env=env,
            timeout=compat.AUTOMATION_TIMEOUT_SECONDS,
        )
        return redact_hub_response(raw)
    except Exception as exc:  # pragma: no cover - defensive fail-closed boundary
        sanitized = sanitize_error_msg(str(exc))
        return {"status": "not_implemented", "reason": sanitized or "web-ai automation dispatch failed"}


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
    if host not in compat.CDP_LOOPBACK_HOSTS and not compat.parse_opt_in(environ.get(compat.CDP_ALLOW_NONLOOPBACK_ENV)):
        return None
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


def redact_hub_response(raw: Any) -> dict[str, Any]:
    """Return a response-key allowlisted and strictly redacted hub payload."""

    if not isinstance(raw, dict):
        return {"status": "not_implemented", "reason": "hub response not an object"}
    try:
        return _redact_hub_response(raw)
    except Exception:  # pragma: no cover - final fail-closed boundary
        return {"status": "not_implemented", "reason": "hub response redaction failed"}


def _redact_hub_response(raw: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in raw.items():
        if key not in compat.RESPONSE_KEY_ALLOWLIST:
            continue
        try:
            redacted = _redact_response_value(key, value)
        except Exception:
            continue
        if redacted is not None:
            result[key] = redacted

    if "status" not in result:
        if result.get("ok") is True:
            result["status"] = "ok"
        else:
            result["status"] = "error"
    return result


def _redact_response_value(key: str, value: Any) -> Any | None:
    if key in {"response_text", "summary", "message"}:
        text = _strict_redact(str(value))
        return text[: compat.RESPONSE_TEXT_MAX_CHARS]
    if key == "chat_url":
        return _sanitize_chat_url(value)
    if key == "conversation_id":
        text = str(value)
        if "://" in text or not _conversation_id_valid(text):
            return None
        return text
    if key == "task_id":
        text = str(value)
        if compat.TASK_ID_RE.fullmatch(text) is None:
            return None
        return text
    if key in {"ok", "completion_detected", "elapsed_ms", "wait_ms", "reuse_conversation"}:
        if isinstance(value, (bool, int, float)):
            return value
        return None
    if key in {"status", "errorCode", "error_code", "model_used", "progress_label", "reason", "requiredFor", "required_for"}:
        return sanitize_error_msg(str(value), max_chars=compat.SCALAR_MAX_CHARS)
    return None


def _conversation_id_valid(value: str) -> bool:
    return compat._CONVERSATION_ID_RE.fullmatch(value) is not None


def _strict_redact(value: str) -> str:
    text = str(value)
    home = str(Path.home())
    if home:
        text = text.replace(home, "[home]")
    username = os.getenv("USER") or os.getenv("USERNAME") or ""
    if username:
        text = text.replace(username, "[user]")

    text = compat._EMAIL_RE.sub("[email]", text)
    text = compat._JWT_RE.sub("[redacted]", text)
    text = compat._BEARER_SECRET_RE.sub(r"\1 [redacted]", text)
    text = compat._SECRET_ASSIGNMENT_RE.sub(r"\1\2[redacted]", text)
    text = compat._OAUTH_ASSIGNMENT_RE.sub(r"\1\2[redacted]", text)
    text = compat._COOKIE_PAIR_RE.sub(r"\1=[redacted];", text)
    text = compat._WINDOWS_ABSOLUTE_PATH_RE.sub("[path]", text)
    text = compat._POSIX_ABSOLUTE_PATH_RE.sub("[path]", text)

    if _contains_high_risk_secret(text):
        return "[omitted]"
    return text


def _contains_high_risk_secret(value: str) -> bool:
    return any(
        pattern.search(value)
        for pattern in (
            compat._JWT_RE,
            compat._BEARER_SECRET_RE,
            compat._SECRET_ASSIGNMENT_RE,
            compat._OAUTH_ASSIGNMENT_RE,
            compat._COOKIE_PAIR_RE,
        )
    )


def _sanitize_chat_url(value: Any) -> str | None:
    parsed = urllib.parse.urlsplit(str(value))
    host = (parsed.hostname or "").lower()
    if host not in compat.CHAT_URL_HOST_ALLOWLIST:
        return None
    if parsed.scheme not in {"http", "https"}:
        return None
    for segment in parsed.path.split("/"):
        if compat._CHAT_URL_FORBIDDEN_PATH_SEGMENT_RE.search(segment):
            return None
    path = parsed.path or ""
    return urllib.parse.urlunsplit((parsed.scheme, host, path, "", ""))


__all__ = ["build_hub_env", "dispatch_web_ai", "redact_hub_response", "web_ai_hub_gate"]

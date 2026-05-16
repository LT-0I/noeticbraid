# SPDX-License-Identifier: Apache-2.0
"""Fail-closed web-ai hub automation gate for SDD-D10-01."""

from __future__ import annotations

import json
import os
import re
import stat
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from . import web_ai_hub_compat as compat
from .web_ai_hub_client import run_hub_command, sanitize_error_msg
from noeticbraid_backend.platform.tasks.models import TASK_ID_RE as PLATFORM_TASK_ID_RE
from noeticbraid_backend.platform.workspace_paths import resolve_user_path

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


def dispatch_web_ai(
    operation: str,
    params,
    *,
    environ=os.environ,
    account: str | None = None,
    task_id: str | None = None,
) -> dict[str, Any]:
    """Dispatch the D10-02 web-ai hub operation subset with fail-closed guards."""

    try:
        snap = dict(environ)
        gate = web_ai_hub_gate(operation, environ=snap)
        if gate.get("status") != "ready":
            return gate

        op = str(operation or "")
        if op not in compat.DISPATCHABLE:
            return {"status": "not_implemented", "reason": "operation not dispatchable in D10-02"}

        governed_dir: Path | None = None
        if _requires_artifact_download_dir(op):
            governed_dir = _resolve_governed_artifact_dir(account=account, task_id=task_id)
            if governed_dir is None:
                return {"status": "not_implemented", "reason": "artifact path governance violation"}

        argv_tail, err = compat.validate_request(
            op,
            params,
            download_dir=str(governed_dir) if governed_dir is not None else None,
        )
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
        validated_artifact_path: Path | None = None
        if _requires_artifact_download_dir(op):
            validated_artifact_path = _reconfine_returned_artifact_path(raw, governed_dir)
            if validated_artifact_path is None:
                return {"status": "not_implemented", "reason": "artifact path governance violation"}
        return redact_hub_response(raw, task_id=task_id, validated_artifact_path=validated_artifact_path)
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


def _requires_artifact_download_dir(operation: str) -> bool:
    return operation.endswith("_generate_image") or operation == "webai_gemini_generate_video"


def _resolve_governed_artifact_dir(*, account: str | None, task_id: str | None) -> Path | None:
    if not isinstance(task_id, str) or PLATFORM_TASK_ID_RE.fullmatch(task_id) is None:
        return None
    try:
        governed_dir = resolve_user_path(str(account or ""), f"tasks/{task_id}/artifacts")
        governed_dir.mkdir(parents=True, exist_ok=True)
        governed_dir.chmod(0o700)
    except (OSError, ValueError):
        return None
    return governed_dir


def _reconfine_returned_artifact_path(raw: Any, governed_dir: Path | None) -> Path | None:
    if governed_dir is None or not isinstance(raw, dict):
        return None
    returned_path = raw.get("path")
    if not isinstance(returned_path, str) or not returned_path:
        return None
    try:
        governed_root = Path(os.path.realpath(governed_dir))
        artifact_path = Path(os.path.realpath(returned_path))
        if not artifact_path.is_relative_to(governed_root):
            return None
        artifact_stat = os.lstat(artifact_path)
    except (OSError, ValueError):
        return None
    if stat.S_ISLNK(artifact_stat.st_mode) or not stat.S_ISREG(artifact_stat.st_mode):
        return None
    if artifact_stat.st_size > compat.ARTIFACT_FILE_MAX_BYTES:
        return None
    return artifact_path


def redact_hub_response(
    raw: Any,
    *,
    task_id: str | None = None,
    validated_artifact_path: Path | str | None = None,
) -> dict[str, Any]:
    """Return a response-key allowlisted and strictly redacted hub payload."""

    if not isinstance(raw, dict):
        return {"status": "not_implemented", "reason": "hub response not an object"}
    try:
        return _redact_hub_response(raw, task_id=task_id, validated_artifact_path=validated_artifact_path)
    except Exception:  # pragma: no cover - final fail-closed boundary
        return {"status": "not_implemented", "reason": "hub response redaction failed"}


def _redact_hub_response(
    raw: dict[str, Any],
    *,
    task_id: str | None = None,
    validated_artifact_path: Path | str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in raw.items():
        if key not in compat.RESPONSE_KEY_ALLOWLIST:
            continue
        try:
            redacted = _redact_response_value(
                key,
                value,
                task_id=task_id,
                validated_artifact_path=validated_artifact_path,
            )
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


def _redact_response_value(
    key: str,
    value: Any,
    *,
    task_id: str | None = None,
    validated_artifact_path: Path | str | None = None,
) -> Any | None:
    if key == "path":
        return _redact_artifact_path(task_id=task_id, validated_artifact_path=validated_artifact_path)
    if key == "download_filename":
        return _redact_download_filename(value)
    if key == "sha256":
        text = str(value)
        if compat._PIN_FORMAT_RE.fullmatch(text) is None:
            return None
        return text
    if key == "size_bytes":
        if isinstance(value, bool) or not isinstance(value, int):
            return None
        if not 0 <= value <= compat.ARTIFACT_FILE_MAX_BYTES:
            return None
        return value
    if key == "dimensions":
        return None
    if key == "conversation_url":
        return _sanitize_gemini_conversation_url(value)
    if key in {"response_text", "summary", "message"}:
        text = _strict_redact(str(value))
        return text[: compat.RESPONSE_TEXT_MAX_CHARS]
    if key in {"chat_url", "url"}:
        return _sanitize_chat_url(value)
    if key in {"conversation_id", "conversationId"}:
        text = str(value)
        if "://" in text or not _conversation_id_valid(text):
            return None
        return text
    if key == "task_id":
        text = str(value)
        if compat.TASK_ID_RE.fullmatch(text) is None:
            return None
        return text
    if key == "dialog_opened":
        if isinstance(value, bool):
            return value
        return None
    if key in {"files_uploaded_count", "results_count"}:
        if isinstance(value, bool) or not isinstance(value, int):
            return None
        return value
    if key in {"attachment_names", "files_in_chip", "results", "items"}:
        if not isinstance(value, list) or len(value) > 64 or any(not isinstance(item, str) for item in value):
            return None
        return [_strict_redact(item)[: compat.SCALAR_MAX_CHARS] for item in value]
    if key in {"ok", "completion_detected", "elapsed_ms", "wait_ms", "reuse_conversation"}:
        if isinstance(value, (bool, int, float)):
            return value
        return None
    if key in {
        "status",
        "errorCode",
        "error_code",
        "model_used",
        "progress_label",
        "reason",
        "requiredFor",
        "required_for",
        "action",
        "surface",
    }:
        return sanitize_error_msg(str(value), max_chars=compat.SCALAR_MAX_CHARS)
    return None


def _redact_artifact_path(*, task_id: str | None, validated_artifact_path: Path | str | None) -> str | None:
    if not isinstance(task_id, str) or PLATFORM_TASK_ID_RE.fullmatch(task_id) is None:
        return None
    if validated_artifact_path is None:
        return None
    basename = os.path.basename(os.fspath(validated_artifact_path))
    if not basename or basename in {".", ".."}:
        return None
    safe_basename = _strict_redact(basename)[: compat.SCALAR_MAX_CHARS]
    if not safe_basename or "/" in safe_basename or "\\" in safe_basename:
        return None
    return f"tasks/{task_id}/artifacts/{safe_basename}"


def _redact_download_filename(value: Any) -> str | None:
    basename = os.path.basename(str(value))
    if not basename or basename in {".", ".."}:
        return None
    safe = _strict_redact(basename)[: compat.SCALAR_MAX_CHARS]
    if not safe or "/" in safe or "\\" in safe:
        return None
    return safe


def _conversation_id_valid(value: str) -> bool:
    return compat._CONVERSATION_ID_RE.fullmatch(value) is not None


def _strict_redact(value: str) -> str:
    text = str(value)
    home = str(Path.home())
    if home:
        text = text.replace(home, "[home]")
    username = os.getenv("USER") or os.getenv("USERNAME") or ""
    if len(username) >= 3:
        text = re.sub(r"\b" + re.escape(username) + r"\b", "[user]", text)

    text = compat._EMAIL_RE.sub("[email]", text)
    text = compat._JWT_RE.sub("[redacted]", text)
    text = compat._BEARER_SECRET_RE.sub(r"\1 [redacted]", text)
    text = compat._SECRET_ASSIGNMENT_RE.sub(r"\1\2[redacted]", text)
    text = compat._OAUTH_ASSIGNMENT_RE.sub(r"\1\2[redacted]", text)
    text = compat._COOKIE_PAIR_RE.sub(r"\1=[redacted];", text)
    text = compat._COOKIE_NOSEMI_RE.sub(r"\1=[redacted]", text)
    text = compat._PROVIDER_PREFIX_TOKEN_RE.sub("[redacted]", text)
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
            compat._PROVIDER_PREFIX_TOKEN_RE,
            compat._LONG_B64_RUN_RE,
            compat._LONG_HEX_RUN_RE,
            compat._COOKIE_NOSEMI_RE,
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


def _sanitize_gemini_conversation_url(value: Any) -> str | None:
    sanitized = _sanitize_chat_url(value)
    if sanitized is None:
        return None
    if (urllib.parse.urlsplit(sanitized).hostname or "").lower() != "gemini.google.com":
        return None
    return sanitized


__all__ = ["build_hub_env", "dispatch_web_ai", "redact_hub_response", "web_ai_hub_gate"]

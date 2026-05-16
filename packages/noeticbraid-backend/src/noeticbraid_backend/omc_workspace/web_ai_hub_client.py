# SPDX-License-Identifier: Apache-2.0
"""Fail-soft web-ai-capability-hub CLI client for ChatGPT Web health checks."""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from json import JSONDecodeError
from pathlib import Path
from typing import Any

CHATGPT_PROFILE = "chatgpt"
ERROR_MSG_MAX_LENGTH = 256

_POSIX_ABSOLUTE_PATH_RE = re.compile(r"(?<![\w.-])/(?:[^\s\"'`<>|;:]+)")
_WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"[A-Za-z]:\\[^\s\"'`<>|;:]+")
_EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(token|api[_-]?key|password|credential|secret|authorization|auth)(\s*[:=]\s*)([^\s,;]+)"
)
_BEARER_RE = re.compile(r"(?i)\b(bearer)\s+[^\s,;]+")

_CONSUMER_ERROR_CODES = {
    "HUB_NOT_BUILT",
    "BROWSER_NOT_LAUNCHED",
    "PROFILE_NOT_FOUND",
    "TARGET_PAGE_MISSING",
    "LOGIN_REQUIRED",
    "CAPABILITY_DB_NOT_INIT",
    "COMMAND_TIMEOUT",
    "INVALID_JSON",
    "POLICY_APPROVAL_REQUIRED",
    "UNKNOWN",
}
_CONSUMER_KEYS = {
    "ok",
    "target",
    "profile",
    "connected",
    "pageCount",
    "loginLikeState",
    "status",
    "errorCode",
    "message",
    "checkedAt",
}


def sanitize_error_msg(msg: str, max_chars: int = ERROR_MSG_MAX_LENGTH) -> str:
    """Redact local/user/secret details and truncate a health-check error."""

    text = str(msg or "").strip()
    if not text:
        return ""
    home = str(Path.home())
    if home:
        text = text.replace(home, "[home]")
    text = _EMAIL_RE.sub("[email]", text)
    text = _SECRET_ASSIGNMENT_RE.sub(r"\1\2[redacted]", text)
    text = _BEARER_RE.sub(r"\1 [redacted]", text)
    text = _WINDOWS_ABSOLUTE_PATH_RE.sub("[path]", text)
    text = _POSIX_ABSOLUTE_PATH_RE.sub("[path]", text)
    username = os.getenv("USER") or os.getenv("USERNAME") or ""
    if username:
        text = text.replace(username, "[user]")
    text = " ".join(text.split())
    return text[:max_chars]


def _cli_path(hub_path: Path) -> Path:
    if hub_path.name == "cli.js" or hub_path.suffix == ".js":
        return hub_path
    return hub_path / "dist" / "src" / "cli.js"


def _error_dict(error_type: str, message: object, *, exit_code: int | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": False,
        "error_type": error_type,
        "error": sanitize_error_msg(str(message)) or "web-ai-capability-hub command failed",
    }
    if exit_code is not None:
        payload["exitCode"] = exit_code
    return payload


def run_hub_command(
    args: list[str],
    *,
    hub_path: Path,
    timeout: int = 15,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Run the hub CLI with argv-list subprocess semantics and parse JSON stdout.

    Failures are represented as sanitized dictionaries instead of exceptions so
    the API can return HTTP 200 with unhealthy/not_implemented status.
    """

    argv = ["node", str(_cli_path(Path(hub_path))), *args]
    run_kwargs: dict[str, Any] = {
        "capture_output": True,
        "timeout": timeout,
        "check": False,
        "text": True,
    }
    if env is not None:
        run_kwargs["env"] = env
    try:
        completed = subprocess.run(argv, **run_kwargs)
    except subprocess.TimeoutExpired:
        return _error_dict("timeout", f"hub command timed out after {timeout} seconds")
    except FileNotFoundError as exc:
        return _error_dict("file_not_found", exc)
    except OSError as exc:
        return _error_dict("os_error", exc)
    except subprocess.SubprocessError as exc:
        return _error_dict("subprocess_error", exc)

    if completed.returncode != 0:
        message = completed.stderr or completed.stdout or f"hub command exited {completed.returncode}"
        return _error_dict("non_zero_exit", message, exit_code=completed.returncode)

    try:
        parsed = json.loads(completed.stdout or "{}")
    except JSONDecodeError as exc:
        return _error_dict("json_parse_error", f"hub command returned invalid JSON: {exc}")
    if isinstance(parsed, dict):
        return parsed
    return {"data": parsed}


def _checked_at_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _consumer_health_error_dict(error_code: str, message: object) -> dict[str, Any]:
    code = error_code if error_code in _CONSUMER_ERROR_CODES else "UNKNOWN"
    return {
        "ok": False,
        "target": CHATGPT_PROFILE,
        "profile": CHATGPT_PROFILE,
        "connected": False,
        "pageCount": 0,
        "loginLikeState": "not_implemented",
        "status": "needs_review",
        "errorCode": code,
        "message": sanitize_error_msg(str(message)) or "web-ai-capability-hub command failed",
        "checkedAt": _checked_at_now(),
    }


def _error_code_from_run_failure(payload: dict[str, Any]) -> str:
    error_type = str(payload.get("error_type") or "")
    message = str(payload.get("error") or "")
    upper_message = message.upper()
    for code in _CONSUMER_ERROR_CODES:
        if code in upper_message:
            return code
    if error_type == "timeout":
        return "COMMAND_TIMEOUT"
    if error_type == "json_parse_error":
        return "INVALID_JSON"
    lowered = message.lower()
    if error_type == "non_zero_exit" and (
        "cannot find module" in lowered
        or "dist/src/cli.js" in lowered
        or "hub dist cli" in lowered
    ):
        return "HUB_NOT_BUILT"
    return "UNKNOWN"


def check_chatgpt_consumer_health(hub_path: Path) -> dict[str, Any]:
    """Call ``consumer:health`` and return its consumer-contract response.

    Subprocess, timeout, and JSON failures are converted to the same allowlist
    key shape with a stable consumer error code and sanitized message.
    """

    payload = run_hub_command(
        [
            "consumer:health",
            "--target",
            CHATGPT_PROFILE,
            "--profile",
            CHATGPT_PROFILE,
            "--json",
        ],
        hub_path=hub_path,
        timeout=15,
    )
    if payload.get("error_type"):
        return _consumer_health_error_dict(
            _error_code_from_run_failure(payload),
            payload.get("error") or "web-ai-capability-hub command failed",
        )
    if _CONSUMER_KEYS.issubset(payload):
        return payload
    return _consumer_health_error_dict(
        "INVALID_JSON",
        "Hub consumer health returned a non-contract JSON payload.",
    )


__all__ = [
    "CHATGPT_PROFILE",
    "ERROR_MSG_MAX_LENGTH",
    "check_chatgpt_consumer_health",
    "run_hub_command",
    "sanitize_error_msg",
]

# SPDX-License-Identifier: Apache-2.0
"""Fail-soft web-ai-capability-hub CLI client for ChatGPT Web health checks."""

from __future__ import annotations

import json
import os
import re
import subprocess
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

CHATGPT_PROFILE = "chatgpt"
CHATGPT_VERSION_MAX_LENGTH = 64
ERROR_MSG_MAX_LENGTH = 256

_POSIX_ABSOLUTE_PATH_RE = re.compile(r"(?<![\w.-])/(?:[^\s\"'`<>|;:]+)")
_WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"[A-Za-z]:\\[^\s\"'`<>|;:]+")
_EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(token|api[_-]?key|password|credential|secret|authorization|auth)(\s*[:=]\s*)([^\s,;]+)"
)
_BEARER_RE = re.compile(r"(?i)\b(bearer)\s+[^\s,;]+")


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


def _sanitize_page_title(title: str, max_chars: int = CHATGPT_VERSION_MAX_LENGTH) -> str:
    """Return a redacted, bounded ChatGPT title suitable for ``version``."""

    return sanitize_error_msg(title, max_chars=max_chars)


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


def run_hub_command(args: list[str], *, hub_path: Path, timeout: int = 15) -> dict[str, Any]:
    """Run the hub CLI with argv-list subprocess semantics and parse JSON stdout.

    Failures are represented as sanitized dictionaries instead of exceptions so
    the API can return HTTP 200 with unhealthy/not_implemented status.
    """

    argv = ["node", str(_cli_path(Path(hub_path))), *args]
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            timeout=timeout,
            check=False,
            text=True,
        )
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


def check_hub_browser_status(hub_path: Path) -> dict[str, Any]:
    """Return a safe subset of ``browser:status --profile chatgpt --json``."""

    payload = run_hub_command(
        ["browser:status", "--profile", CHATGPT_PROFILE, "--json"],
        hub_path=hub_path,
        timeout=5,
    )
    if payload.get("ok") is False:
        return {"connected": False, "lastError": payload.get("error")}
    last_error = payload.get("lastError")
    safe: dict[str, Any] = {
        "connected": bool(payload.get("connected")),
        "lastError": sanitize_error_msg(str(last_error)) if last_error else None,
    }
    if isinstance(payload.get("browser"), str):
        safe["browser"] = sanitize_error_msg(str(payload["browser"]))
    pages = payload.get("pages")
    if isinstance(pages, list):
        safe["pageCount"] = len(pages)
    return safe


def get_chatgpt_pages(hub_path: Path) -> list[dict[str, Any]]:
    """Return safe page metadata from ``browser:pages --profile chatgpt --json``."""

    payload = run_hub_command(
        ["browser:pages", "--profile", CHATGPT_PROFILE, "--json"],
        hub_path=hub_path,
        timeout=15,
    )
    if payload.get("ok") is False:
        return [{"_hub_error": payload.get("error") or "browser:pages failed"}]
    pages: Any
    if isinstance(payload.get("data"), list):
        pages = payload["data"]
    elif isinstance(payload.get("pages"), list):
        pages = payload["pages"]
    elif isinstance(payload, list):  # pragma: no cover - defensive; run_hub_command wraps lists.
        pages = payload
    else:
        pages = []

    safe_pages: list[dict[str, Any]] = []
    for page in pages:
        if not isinstance(page, dict):
            continue
        safe_pages.append(
            {
                "id": str(page.get("id") or ""),
                "url": str(page.get("url") or ""),
                "title": _sanitize_page_title(str(page.get("title") or "")),
            }
        )
    return safe_pages


def _is_chatgpt_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return parsed.scheme == "https" and parsed.netloc.lower() == "chatgpt.com"


def _title_indicates_login(title: str) -> bool:
    normalized = title.lower()
    return any(marker in normalized for marker in ("log in", "login", "sign in", "sign-in"))


def parse_chatgpt_login_state(
    pages: list[dict[str, Any]],
) -> tuple[Literal["healthy", "unhealthy", "not_implemented"], str | None, str | None]:
    """Infer ChatGPT Web health from browser page URL/title metadata only."""

    for page in pages:
        hub_error = page.get("_hub_error")
        if hub_error:
            return "unhealthy", None, sanitize_error_msg(str(hub_error))

    chatgpt_pages = [page for page in pages if _is_chatgpt_url(str(page.get("url") or ""))]
    if not chatgpt_pages:
        return (
            "not_implemented",
            None,
            "Chrome 未打开 ChatGPT 页, 请在 hub 内手动 browser:launch + browser:open https://chatgpt.com/",
        )

    for page in chatgpt_pages:
        title = str(page.get("title") or "")
        if _title_indicates_login(title):
            return "unhealthy", None, "ChatGPT Web 未登录"

    for page in chatgpt_pages:
        title = str(page.get("title") or "")
        if "chatgpt" in title.lower():
            version = _sanitize_page_title(title) or None
            return "healthy", version, None

    return "unhealthy", None, "ChatGPT Web 页面状态不可判定"


__all__ = [
    "CHATGPT_PROFILE",
    "CHATGPT_VERSION_MAX_LENGTH",
    "check_hub_browser_status",
    "get_chatgpt_pages",
    "parse_chatgpt_login_state",
    "run_hub_command",
    "sanitize_error_msg",
    "_sanitize_page_title",
]

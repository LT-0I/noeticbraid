# SPDX-License-Identifier: Apache-2.0
"""Read-only Phase-1 account status observation."""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from collections.abc import Callable, Iterable, Mapping
from datetime import datetime, timezone
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

LoginState = Literal["logged_in", "logged_out", "unknown"]
HealthState = Literal["ok", "fail", "unknown"]
SnapshotState = Literal["ok", "racing"]

PHASE1_STATUS_CAPABILITY_IDS: tuple[str, ...] = (
    "cap_claude_code_cli",
    "cap_codex_cli",
    "cap_gemini_cli",
    "cap_gemini_web",
)

DEFAULT_CLI_TIMEOUT_SECONDS = 5
WEB_HUB_TIMEOUT_SECONDS = 15
GEMINI_WEB_HUB_PROFILE = "gemini"

_DEFAULT_CAPABILITIES: tuple[dict[str, Any], ...] = (
    {
        "capability_id": "cap_claude_code_cli",
        "display_name": "Claude Code CLI",
        "provider": "anthropic",
        "end_type": "cli",
        "command": "claude",
    },
    {
        "capability_id": "cap_codex_cli",
        "display_name": "Codex CLI",
        "provider": "openai",
        "end_type": "cli",
        "command": "codex",
    },
    {
        "capability_id": "cap_gemini_cli",
        "display_name": "Gemini CLI",
        "provider": "google",
        "end_type": "cli",
        "command": "gemini",
    },
    {
        "capability_id": "cap_gemini_web",
        "display_name": "Gemini Web",
        "provider": "google",
        "end_type": "web",
        "command": None,
    },
)

_POSIX_ABSOLUTE_PATH_RE = re.compile(r"(?<![\w.-])/(?:[^\s\"'`<>|;:]+)")
_WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"[A-Za-z]:\\[^\s\"'`<>|;:]+")
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(token|api[_-]?key|password|credential|secret|authorization|cookie)(\s*[:=]\s*)([^\s,;]+)"
)


class AccountStatusRecord(BaseModel):
    """Sanitized internal per-capability status record."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    capability_id: str
    display_name: str
    provider: str
    end_type: Literal["cli", "web"]
    login_state: LoginState
    health: HealthState
    checked_at: datetime
    snapshot_state: SnapshotState


def observe_status(
    capabilities: Iterable[Mapping[str, Any]] | None = None,
    *,
    now_fn: Callable[[], datetime] | None = None,
    home_path: Path | None = None,
    version_runner: Callable[[str, int], subprocess.CompletedProcess[str]] | None = None,
    cli_timeout_seconds: int = DEFAULT_CLI_TIMEOUT_SECONDS,
    sanitize_message: Callable[[object], str] | None = None,
    gemini_web_probe: Callable[[], Mapping[str, Any] | None] | None = None,
) -> list[AccountStatusRecord]:
    """Return read-only sanitized status for the Phase-1 first-batch caps."""

    checked_at = _aware_utc((now_fn or _utc_now)())
    sanitize = sanitize_message or _sanitize_and_truncate
    run_version = version_runner or _run_version_command
    home = home_path or Path.home()
    items = _phase1_capability_items(capabilities or _DEFAULT_CAPABILITIES)
    records: list[AccountStatusRecord] = []

    for capability_id in PHASE1_STATUS_CAPABILITY_IDS:
        item = items.get(capability_id)
        if item is None:
            continue
        try:
            health: HealthState = "unknown"
            login_state: LoginState = "unknown"
            snapshot_state: SnapshotState = "ok"
            if capability_id == "cap_gemini_web":
                login_state, health = _observe_gemini_web(
                    gemini_web_probe=gemini_web_probe,
                    sanitize_message=sanitize,
                )
            elif str(item.get("end_type")) == "cli":
                command = item.get("command")
                if isinstance(command, str) and command:
                    health = _observe_cli_health(
                        command,
                        version_runner=run_version,
                        timeout_seconds=cli_timeout_seconds,
                        sanitize_message=sanitize,
                    )
                else:
                    health = "fail"
                if capability_id == "cap_gemini_cli":
                    login_state, snapshot_state = _observe_gemini_cli_snapshot(home)

            records.append(
                AccountStatusRecord(
                    capability_id=capability_id,
                    display_name=str(item["display_name"]),
                    provider=str(item["provider"]),
                    end_type=str(item["end_type"]),
                    login_state=login_state,
                    health=health,
                    checked_at=checked_at,
                    snapshot_state=snapshot_state,
                )
            )
        except Exception as exc:  # pragma: no cover - defensive fail-soft boundary
            sanitize(exc)
            records.append(
                AccountStatusRecord(
                    capability_id=capability_id,
                    display_name=str(item.get("display_name") or capability_id),
                    provider=str(item.get("provider") or "unknown"),
                    end_type="web" if item.get("end_type") == "web" else "cli",
                    login_state="unknown",
                    health="unknown",
                    checked_at=checked_at,
                    snapshot_state="racing",
                )
            )

    return records


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _phase1_capability_items(capabilities: Iterable[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    items: dict[str, Mapping[str, Any]] = {}
    for item in capabilities:
        capability_id = item.get("capability_id")
        if isinstance(capability_id, str) and capability_id in PHASE1_STATUS_CAPABILITY_IDS:
            items[capability_id] = item
    return items


def _run_version_command(command: str, timeout_seconds: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [command, "--version"],
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
        text=True,
    )


def _observe_cli_health(
    command: str,
    *,
    version_runner: Callable[[str, int], subprocess.CompletedProcess[str]],
    timeout_seconds: int,
    sanitize_message: Callable[[object], str],
) -> HealthState:
    try:
        completed = version_runner(command, timeout_seconds)
        if completed.returncode != 0:
            sanitize_message(completed.stderr)
            return "fail"
        return "ok" if _first_sanitized_line(completed.stdout, sanitize_message=sanitize_message) else "fail"
    except subprocess.TimeoutExpired:
        return "fail"
    except FileNotFoundError:
        return "fail"
    except (OSError, subprocess.SubprocessError) as exc:
        sanitize_message(exc)
        return "fail"


def _first_sanitized_line(value: str | None, *, sanitize_message: Callable[[object], str]) -> str:
    for raw_line in (value or "").splitlines():
        line = sanitize_message(raw_line)
        if line:
            return line
    return ""


def _observe_gemini_cli_snapshot(home: Path) -> tuple[LoginState, SnapshotState]:
    path = home / ".gemini" / "google_accounts.json"
    for attempt in range(2):
        try:
            before = path.stat()
        except FileNotFoundError:
            return "logged_out", "ok"
        except OSError:
            return "unknown", "racing"

        try:
            text = path.read_text(encoding="utf-8")
            after = path.stat()
        except FileNotFoundError:
            return "unknown", "racing"
        except (OSError, UnicodeDecodeError):
            if attempt == 0:
                time.sleep(0.01)
                continue
            return "unknown", "racing"

        if _stat_signature(before) != _stat_signature(after):
            if attempt == 0:
                time.sleep(0.01)
                continue
            return "unknown", "racing"

        if not text.strip():
            return "logged_out", "ok"

        try:
            payload = json.loads(text)
        except JSONDecodeError:
            if attempt == 0:
                time.sleep(0.01)
                continue
            return "unknown", "racing"
        return ("logged_in" if _has_active_gemini_account(payload) else "logged_out"), "ok"

    return "unknown", "racing"


def _stat_signature(value: os.stat_result) -> tuple[int, int, int]:
    return (value.st_ino, value.st_size, value.st_mtime_ns)


def _has_active_gemini_account(payload: object) -> bool:
    if not isinstance(payload, Mapping):
        return False
    active = payload.get("active")
    if isinstance(active, str):
        return bool(active.strip())
    return bool(active)


def _observe_gemini_web(
    *,
    gemini_web_probe: Callable[[], Mapping[str, Any] | None] | None,
    sanitize_message: Callable[[object], str],
) -> tuple[LoginState, HealthState]:
    probe = gemini_web_probe or _default_gemini_web_probe
    try:
        payload = probe()
    except Exception as exc:
        sanitize_message(exc)
        return "unknown", "unknown"
    if not isinstance(payload, Mapping):
        return "unknown", "unknown"
    login_like_state = str(payload.get("loginLikeState") or "").strip().lower()
    if login_like_state == "healthy":
        return "logged_in", "ok"
    if login_like_state == "unhealthy":
        return "logged_out", "fail"
    return "unknown", "unknown"


def _default_gemini_web_probe() -> Mapping[str, Any] | None:
    hub_path_value = os.getenv("NOETICBRAID_WEB_AI_HUB_PATH")
    if not hub_path_value:
        return None
    hub_path = Path(hub_path_value)
    if not hub_path.is_absolute():
        return None
    cli_path = hub_path if hub_path.name == "cli.js" or hub_path.suffix == ".js" else hub_path / "dist" / "src" / "cli.js"
    try:
        completed = subprocess.run(
            [
                "node",
                str(cli_path),
                "consumer:health",
                "--target",
                "gemini",
                "--profile",
                GEMINI_WEB_HUB_PROFILE,
                "--json",
            ],
            capture_output=True,
            timeout=WEB_HUB_TIMEOUT_SECONDS,
            check=False,
            text=True,
        )
    except (FileNotFoundError, OSError, subprocess.SubprocessError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        _sanitize_and_truncate(completed.stderr or completed.stdout)
        return None
    try:
        payload = json.loads(completed.stdout or "{}")
    except JSONDecodeError:
        return None
    return payload if isinstance(payload, Mapping) else None


def _sanitize_and_truncate(message: object, *, max_length: int = 256) -> str:
    text = str(message or "").strip()
    if not text:
        return ""
    home = str(Path.home())
    if home:
        text = text.replace(home, "[home]")
    username = os.getenv("USER") or os.getenv("USERNAME") or ""
    if username:
        text = text.replace(username, "[user]")
    text = _SECRET_ASSIGNMENT_RE.sub(r"\1\2[redacted]", text)
    text = _WINDOWS_ABSOLUTE_PATH_RE.sub("[path]", text)
    text = _POSIX_ABSOLUTE_PATH_RE.sub("[path]", text)
    text = " ".join(text.split())
    return text[:max_length]


__all__ = [
    "AccountStatusRecord",
    "HealthState",
    "LoginState",
    "PHASE1_STATUS_CAPABILITY_IDS",
    "SnapshotState",
    "observe_status",
]

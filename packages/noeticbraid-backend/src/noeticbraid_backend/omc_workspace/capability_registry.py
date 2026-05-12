# SPDX-License-Identifier: Apache-2.0
"""First-stage OMC capability registry and opt-in real health checks."""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from subprocess import run
from typing import Any

from noeticbraid_core.schemas import CapabilityHealthResult, CapabilityRegistryEntry

CAPABILITIES: tuple[dict[str, Any], ...] = (
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

GEMINI_WEB_DEFERRED_ERROR = "real ping deferred to SDD-D2-03-hotfix-01"
ERROR_MSG_MAX_LENGTH = 256
VERSION_MAX_LENGTH = 256
LIVE_SUBPROCESS_TIMEOUT_SECONDS = 5

_POSIX_ABSOLUTE_PATH_RE = re.compile(r"(?<![\w.-])/(?:[^\s\"'`<>|;:]+)")
_WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"[A-Za-z]:\\[^\s\"'`<>|;:]+")
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(token|api[_-]?key|password|credential|secret)(\s*[:=]\s*)([^\s,;]+)"
)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso_z(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _sanitize_and_truncate(message: object, *, max_length: int = ERROR_MSG_MAX_LENGTH) -> str:
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


def _first_sanitized_line(value: str | None) -> str:
    for raw_line in (value or "").splitlines():
        line = _sanitize_and_truncate(raw_line, max_length=VERSION_MAX_LENGTH)
        if line:
            return line
    return ""


def _relative_if_possible(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        # Outside-project artifacts should not leak host paths; keep only the
        # stable filename so callers still receive a usable artifact reference.
        return path.name


def _write_live_artifact(
    *,
    project_root: Path,
    capability_id: str,
    status: str,
    version: str | None,
    last_checked: datetime,
    error_msg: str | None,
    duration_ms: int | None,
    exit_code: int | None,
) -> str | None:
    """Write the SDD-D2-03 safe live CLI artifact, failing soft on I/O errors."""

    try:
        artifact_root = project_root / ".omx" / "artifacts"
        artifact_root.mkdir(parents=True, exist_ok=True)
        artifact_path = artifact_root / f"health-check-{capability_id}-{last_checked.strftime('%Y%m%dT%H%M%SZ')}.json"
        payload: dict[str, Any] = {
            "sdd_id": "SDD-D2-03",
            "artifact_schema_version": "capability-health/v1",
            "capability_id": capability_id,
            "mode": "live",
            "status": status,
            "version": version,
            "last_checked": _iso_z(last_checked),
            "error_msg": error_msg,
            "artifact_created_at": _iso_z(_now()),
        }
        if duration_ms is not None:
            payload["duration_ms"] = duration_ms
        if exit_code is not None:
            payload["exit_code"] = exit_code
        artifact_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except OSError:
        return None
    return _relative_if_possible(artifact_path, project_root)


def _health_result(
    *,
    item: dict[str, Any],
    mode: str,
    status: str,
    checked_at: datetime,
    summary: str,
    artifact_ref: str | None = None,
    version: str | None = None,
    error_msg: str | None = None,
    set_last_checked: bool = False,
) -> CapabilityHealthResult:
    return CapabilityHealthResult(
        capability_id=item["capability_id"],
        mode=mode,
        status=status,
        checked_at=checked_at,
        summary=summary,
        artifact_ref=artifact_ref,
        version=version,
        last_checked=checked_at if set_last_checked else None,
        error_msg=error_msg,
    )


def _run_version_command(cli_path: str) -> subprocess.CompletedProcess[str]:
    return run(
        [cli_path, "--version"],
        capture_output=True,
        timeout=LIVE_SUBPROCESS_TIMEOUT_SECONDS,
        check=False,
        text=True,
    )


def _live_cli_health_result(
    *,
    item: dict[str, Any],
    checked_at: datetime,
    project_root: Path,
) -> CapabilityHealthResult:
    command = str(item["command"])
    started = time.monotonic()
    exit_code: int | None = None
    version: str | None = None
    error_msg: str | None = None
    try:
        completed = _run_version_command(command)
        exit_code = completed.returncode
        if completed.returncode != 0:
            stderr = _sanitize_and_truncate(completed.stderr)
            error_msg = stderr or f"{command} --version exited {completed.returncode}"
            status = "unhealthy"
        else:
            parsed = _first_sanitized_line(completed.stdout)
            if parsed:
                version = parsed
                status = "healthy"
            else:
                error_msg = "version output was empty"
                status = "unhealthy"
    except subprocess.TimeoutExpired:
        status = "unhealthy"
        error_msg = f"health-check timed out after {LIVE_SUBPROCESS_TIMEOUT_SECONDS} seconds"
    except FileNotFoundError:
        status = "unhealthy"
        error_msg = (
            _sanitize_and_truncate(f"{command} executable not found")
            or "executable not found"
        )
    except (OSError, subprocess.SubprocessError) as exc:
        status = "unhealthy"
        error_msg = _sanitize_and_truncate(exc) or "subprocess health-check failed"
    duration_ms = int((time.monotonic() - started) * 1000)
    artifact_ref = _write_live_artifact(
        project_root=project_root,
        capability_id=item["capability_id"],
        status=status,
        version=version,
        last_checked=checked_at,
        error_msg=error_msg,
        duration_ms=duration_ms,
        exit_code=exit_code,
    )
    summary = (
        f"Live health OK for {item['display_name']}; version parsed."
        if status == "healthy"
        else f"Live health-check failed safely for {item['display_name']}."
    )
    return _health_result(
        item=item,
        mode="live_opt_in",
        status=status,
        checked_at=checked_at,
        summary=summary,
        artifact_ref=artifact_ref,
        version=version,
        error_msg=error_msg,
        set_last_checked=True,
    )


def _gemini_web_placeholder_result(*, item: dict[str, Any], checked_at: datetime) -> CapabilityHealthResult:
    return _health_result(
        item=item,
        mode="live_opt_in",
        status="not_implemented",
        checked_at=checked_at,
        summary=GEMINI_WEB_DEFERRED_ERROR,
        version=None,
        error_msg=GEMINI_WEB_DEFERRED_ERROR,
        set_last_checked=True,
    )


def list_capabilities() -> list[dict[str, Any]]:
    return [
        CapabilityRegistryEntry(
            capability_id=item["capability_id"],
            display_name=item["display_name"],
            provider=item["provider"],
            end_type=item["end_type"],
            status="unknown",
            health_mode="mock",
            last_checked_at=None,
            last_result=None,
            source_ref="source_ai_invocation_reference",
            first_stage=True,
        ).model_dump(mode="json")
        for item in CAPABILITIES
    ]


def _entry_by_id(capability_id: str) -> dict[str, Any] | None:
    for item in CAPABILITIES:
        if item["capability_id"] == capability_id:
            return dict(item)
    return None


def health_check(capability_id: str, *, project_root: Path) -> dict[str, Any]:
    item = _entry_by_id(capability_id)
    if item is None:
        raise KeyError(capability_id)
    live = os.getenv("NOETICBRAID_HEALTH_CHECK_LIVE") == "1"
    checked_at = _now()
    if not live:
        result = _health_result(
            item=item,
            mode="mock",
            status="available",
            checked_at=checked_at,
            summary=f"Mock health OK for {item['display_name']}; live provider checks are opt-in.",
        )
    elif item.get("command"):
        result = _live_cli_health_result(item=item, checked_at=checked_at, project_root=project_root)
    else:
        result = _gemini_web_placeholder_result(item=item, checked_at=checked_at)
    capability = CapabilityRegistryEntry(
        capability_id=item["capability_id"],
        display_name=item["display_name"],
        provider=item["provider"],
        end_type=item["end_type"],
        status=result.status,
        health_mode=result.mode,
        last_checked_at=result.checked_at,
        last_result=result,
        source_ref="source_ai_invocation_reference",
        first_stage=True,
    )
    return {"capability": capability.model_dump(mode="json"), "result": result.model_dump(mode="json")}


__all__ = ["CAPABILITIES", "health_check", "list_capabilities"]

# SPDX-License-Identifier: Apache-2.0
"""First-stage OMC capability registry and mock/default health checks."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
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


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _artifact_root(project_root: Path) -> Path:
    preferred = project_root / ".omx" / "artifacts"
    try:
        preferred.mkdir(parents=True, exist_ok=True)
        return preferred
    except OSError:
        fallback = os.getenv("NOETICBRAID_ARTIFACTS_DIR")
        if fallback:
            path = Path(fallback)
            path.mkdir(parents=True, exist_ok=True)
            return path
        raise


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


def _relative_if_possible(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def health_check(capability_id: str, *, project_root: Path) -> dict[str, Any]:
    item = _entry_by_id(capability_id)
    if item is None:
        raise KeyError(capability_id)
    live = os.getenv("NOETICBRAID_HEALTH_CHECK_LIVE") == "1"
    checked_at = _now()
    if not live:
        result = CapabilityHealthResult(
            capability_id=capability_id,
            mode="mock",
            status="available",
            checked_at=checked_at,
            summary=f"Mock health OK for {item['display_name']}; live provider checks are opt-in.",
        )
    else:
        summary = "live opt-in check completed"
        status = "available"
        command = item.get("command")
        if command:
            completed = subprocess.run([str(command), "--version"], capture_output=True, text=True, timeout=10, check=False)
            output = (completed.stdout or completed.stderr or "").strip()
            status = "available" if completed.returncode == 0 else "degraded"
            summary = output[:512] or f"{command} --version exited {completed.returncode}"
        else:
            summary = "Gemini Web live opt-in selected; manual browser/session ping is not automated in D2-02."
            status = "degraded"
        artifact_path = _artifact_root(project_root) / f"capability-health-{capability_id}-{checked_at.strftime('%Y%m%dT%H%M%SZ')}.json"
        payload = {
            "capability_id": capability_id,
            "display_name": item["display_name"],
            "mode": "live_opt_in",
            "status": status,
            "checked_at": checked_at.isoformat().replace("+00:00", "Z"),
            "summary": summary,
        }
        artifact_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        result = CapabilityHealthResult(
            capability_id=capability_id,
            mode="live_opt_in",
            status=status,
            checked_at=checked_at,
            summary=summary,
            artifact_ref=_relative_if_possible(artifact_path, project_root),
        )
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

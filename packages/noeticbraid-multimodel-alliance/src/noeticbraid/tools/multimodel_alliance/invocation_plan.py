"""Provider command-plan generation for SDD-D2-01 debate loops.

Plans follow AI_INVOCATION_REFERENCE.md, but no provider is called unless the
caller explicitly opts into provider execution.
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .candidate_store import assert_safe_output_root

DEFAULT_WORKSPACE = Path(os.getenv("NOETICBRAID_WORKSPACE_ROOT") or Path(__file__).resolve().parents[7])
CODEX_REASONING_FLAG = "model_reasoning_effort='\"xhigh\"'"
GEMINI_MODEL = "gemini-3.1-pro-preview"
CLAUDE_MODEL = "claude-opus-4-7[1m]"


class InvocationPlanError(ValueError):
    """Raised when provider invocation is attempted outside explicit opt-in."""


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _slug(value: object) -> str:
    text = "".join(ch.lower() if ch.isalnum() else "-" for ch in str(value or "task"))
    return "-".join(part for part in text.split("-") if part)[:64] or "task"


def _prompt(task_card: dict[str, Any], role: str) -> str:
    task_id = task_card.get("task_id", "task_generated")
    return (
        f"SDD-D2-01 multimodel debate role={role}. Review task {task_id}. "
        "Return concise structured objections/evidence only; do not perform external side effects. "
        f"Task card JSON: {json.dumps(task_card, ensure_ascii=False, sort_keys=True)}"
    )


def build_invocation_plan(
    task_card: dict[str, Any],
    *,
    artifact_root: str | Path,
    provider_mode: bool = False,
    workspace: str | Path = DEFAULT_WORKSPACE,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Return Codex/Gemini/Claude command plans without running them."""

    root = assert_safe_output_root(artifact_root)
    root.mkdir(parents=True, exist_ok=True)
    stamp = timestamp or utc_stamp()
    task_slug = _slug(task_card.get("task_id") or task_card.get("title") or "debate-loop")
    workspace_path = str(Path(workspace))

    codex_artifact = root / f"ask-codex-{task_slug}-{stamp}.md"
    gemini_artifact = root / f"ask-gemini31pro-{task_slug}-{stamp}.md"
    claude_artifact = root / f"ask-claude-{task_slug}-{stamp}.md"

    plans = [
        {
            "provider": "codex",
            "model_ref": "model_codex_gpt_5_5",
            "role": "adversary",
            "artifact_path": str(codex_artifact),
            "argv": [
                "omx",
                "exec",
                "--sandbox",
                "read-only",
                "--skip-git-repo-check",
                "--ignore-rules",
                "-c",
                CODEX_REASONING_FLAG,
                "-C",
                workspace_path,
                "-o",
                str(codex_artifact),
                _prompt(task_card, "codex_adversary"),
            ],
            "env": {},
            "enabled": provider_mode,
        },
        {
            "provider": "gemini",
            "model_ref": "model_gemini_3_1_pro",
            "role": "source_auditor",
            "artifact_path": str(gemini_artifact),
            "argv": [
                "gemini",
                "-m",
                GEMINI_MODEL,
                "--approval-mode",
                "plan",
                "-p",
                _prompt(task_card, "gemini_source_auditor"),
            ],
            "env": {},
            "enabled": provider_mode,
        },
        {
            "provider": "claude",
            "model_ref": "model_claude_opus_4_7",
            "role": "producer_convergence",
            "artifact_path": str(claude_artifact),
            "argv": ["omc", "ask", "claude", "--prompt", _prompt(task_card, "claude_producer_convergence")],
            "env": {"ANTHROPIC_MODEL": CLAUDE_MODEL, "CLAUDE_CODE_EFFORT_LEVEL": "max"},
            "enabled": provider_mode,
        },
    ]
    return {
        "provider_mode": "provider" if provider_mode else "mock_or_manual",
        "may_execute": provider_mode,
        "artifact_root": str(root),
        "plans": plans,
    }


def ensure_provider_mode(plan: dict[str, Any], *, provider_mode: bool) -> None:
    if not provider_mode or not plan.get("may_execute"):
        raise InvocationPlanError("provider CLIs are disabled unless provider_mode=True is explicit")


def execute_invocation_plan(plan: dict[str, Any], *, provider_mode: bool = False, timeout_seconds: int = 900) -> list[dict[str, Any]]:
    """Execute an explicit provider plan and capture outputs under artifact_root.

    Tests and default loop paths do not call this function. It exists so the
    provider-mode boundary is explicit and artifact-backed when a user opts in.
    """

    ensure_provider_mode(plan, provider_mode=provider_mode)
    results: list[dict[str, Any]] = []
    for item in plan.get("plans", []):
        artifact_path = Path(item["artifact_path"])
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        completed = subprocess.run(  # noqa: S603 - explicit user/provider-mode boundary.
            item["argv"],
            env={**os.environ, **item.get("env", {})},
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        if not artifact_path.exists():
            artifact_path.write_text((completed.stdout or "") + (completed.stderr or ""), encoding="utf-8")
        results.append(
            {
                "provider": item["provider"],
                "model_ref": item["model_ref"],
                "role": item["role"],
                "artifact_path": str(artifact_path),
                "returncode": completed.returncode,
            }
        )
    return results

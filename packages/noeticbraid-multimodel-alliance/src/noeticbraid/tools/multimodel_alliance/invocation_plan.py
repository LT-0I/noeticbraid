"""Provider command-plan generation for SDD-D2-01 debate loops.

Plans follow AI_INVOCATION_REFERENCE.md, but no provider is called unless the
caller explicitly opts into provider execution.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .candidate_store import assert_safe_output_root

DEFAULT_WORKSPACE = Path(os.getenv("NOETICBRAID_WORKSPACE_ROOT") or Path(__file__).resolve().parents[7])
CODEX_REASONING_FLAG = 'model_reasoning_effort="xhigh"'
GEMINI_MODEL = "gemini-3.1-pro-preview"
CLAUDE_MODEL = "claude-opus-4-7[1m]"
STRUCTURED_ROUND_JSON_INSTRUCTION = '\n\nAfter your prose, emit exactly one fenced ```json``` block matching this schema (no extra keys): {"objections":[{"objection_id":"obj_*","severity":"low|medium|high|critical","status":"raised|unresolved|needs_user_decision","summary":"<≤200 chars>","evidence_refs":[]}],"recommendation":"<≤500 chars>","summary":"<≤500 chars>"}. Use stable obj_ ids. If you have no objections, return objections: [].'
GEMINI_RETRY_BACKOFF_SECONDS: tuple[int, ...] = (30, 60, 120)
RATE_LIMIT_SIGNALS = ("429", "rate limit", "resource_exhausted", "quota exceeded")
OMC_ASK_LINK_RE = re.compile(r"(?<![A-Za-z0-9_/-])(\.omc/artifacts/ask/[A-Za-z0-9_./\-]+\.md)")


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
        + STRUCTURED_ROUND_JSON_INSTRUCTION
    )


def _is_rate_limited(stdout: str, stderr: str) -> bool:
    blob = (stdout + "\n" + stderr).lower()
    return any(signal.lower() in blob for signal in RATE_LIMIT_SIGNALS)


def _follow_claude_ask_link(stdout: str, *, workspace_root: Path) -> Path | None:
    match = OMC_ASK_LINK_RE.search(stdout)
    if not match:
        return None
    candidate = (workspace_root / match.group(1)).resolve()
    workspace_root_resolved = workspace_root.resolve()
    try:
        candidate.relative_to(workspace_root_resolved)
    except ValueError:
        return None
    assert_safe_output_root(candidate.parent)
    return candidate if candidate.is_file() else None


def _artifact_has_full_content(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 256


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
        retries_attempted = 0
        completed: subprocess.CompletedProcess[str] | None = None
        delays = (0,) + GEMINI_RETRY_BACKOFF_SECONDS
        for attempt_index, delay in enumerate(delays):
            if delay:
                time.sleep(delay)
            completed = subprocess.run(  # noqa: S603 - explicit user/provider-mode boundary.
                item["argv"],
                env={**os.environ, **item.get("env", {})},
                text=True,
                capture_output=True,
                timeout=timeout_seconds,
                check=False,
            )
            should_retry = (
                item["provider"] == "gemini"
                and completed.returncode != 0
                and _is_rate_limited(completed.stdout or "", completed.stderr or "")
                and attempt_index < len(delays) - 1
            )
            if not should_retry:
                break
            retries_attempted += 1
        if completed is None:
            raise InvocationPlanError("provider plan execution produced no subprocess result")

        copied_claude_link = False
        if item["provider"] == "claude" and not _artifact_has_full_content(artifact_path):
            linked = _follow_claude_ask_link(
                completed.stdout or "",
                workspace_root=Path(os.getenv("NOETICBRAID_WORKSPACE_ROOT", str(DEFAULT_WORKSPACE))),
            )
            if linked is not None:
                content = linked.read_text(encoding="utf-8")
                artifact_path.write_text(content + f"\n<!-- copied from {linked} -->\n", encoding="utf-8")
                copied_claude_link = True

        if not artifact_path.exists() or (item["provider"] == "claude" and not copied_claude_link and not _artifact_has_full_content(artifact_path)):
            artifact_path.write_text((completed.stdout or "") + (completed.stderr or ""), encoding="utf-8")
        results.append(
            {
                "provider": item["provider"],
                "model_ref": item["model_ref"],
                "role": item["role"],
                "artifact_path": str(artifact_path),
                "returncode": completed.returncode,
                "retries_attempted": retries_attempted,
            }
        )
    return results

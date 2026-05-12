from __future__ import annotations

import pytest

from noeticbraid.tools.multimodel_alliance.invocation_plan import (
    CODEX_REASONING_FLAG,
    GEMINI_MODEL,
    InvocationPlanError,
    build_invocation_plan,
    ensure_provider_mode,
)


def _plan(tmp_path, provider_mode=False):
    return build_invocation_plan({"task_id": "task_invocation_plan", "trigger": "task_card"}, artifact_root=tmp_path, provider_mode=provider_mode, timestamp="20260512T000000Z")


def test_codex_plan_uses_read_only_xhigh_artifact_output(tmp_path):
    plan = _plan(tmp_path)
    codex = next(item for item in plan["plans"] if item["provider"] == "codex")

    assert codex["argv"][:5] == ["omx", "exec", "--sandbox", "read-only", "--skip-git-repo-check"]
    assert "--ignore-rules" in codex["argv"]
    assert CODEX_REASONING_FLAG in codex["argv"]
    assert "-o" in codex["argv"]
    assert codex["artifact_path"].endswith("ask-codex-task-invocation-plan-20260512T000000Z.md")
    assert codex["enabled"] is False


def test_gemini_plan_uses_31_preview_plan_mode_argv_prompt(tmp_path):
    plan = _plan(tmp_path)
    gemini = next(item for item in plan["plans"] if item["provider"] == "gemini")

    assert gemini["argv"][:6] == ["gemini", "-m", GEMINI_MODEL, "--approval-mode", "plan", "-p"]
    assert "task_invocation_plan" in gemini["argv"][6]
    assert gemini["artifact_path"].endswith("ask-gemini31pro-task-invocation-plan-20260512T000000Z.md")


def test_provider_plan_never_runs_without_explicit_provider_mode(tmp_path):
    plan = _plan(tmp_path, provider_mode=False)

    assert plan["may_execute"] is False
    with pytest.raises(InvocationPlanError, match="disabled"):
        ensure_provider_mode(plan, provider_mode=False)

    enabled = _plan(tmp_path, provider_mode=True)
    ensure_provider_mode(enabled, provider_mode=True)
    assert all(item["enabled"] for item in enabled["plans"])

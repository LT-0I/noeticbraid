from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from noeticbraid.tools.multimodel_alliance import invocation_plan as module


def _claude_item(artifact_path: Path) -> dict[str, Any]:
    return {
        "provider": "claude",
        "model_ref": "model_claude_opus_4_7",
        "role": "producer",
        "artifact_path": str(artifact_path),
        "argv": ["omc", "ask", "claude"],
        "env": {},
    }


def _plan(item: dict[str, Any]) -> dict[str, Any]:
    return {"may_execute": True, "plans": [item]}


def _patch_run(monkeypatch: pytest.MonkeyPatch, stdout: str) -> None:
    def fake_run(argv: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)


def test_claude_full_direct_artifact_is_left_unchanged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    artifact = tmp_path / "claude.md"
    content = "direct artifact\n" + ("x" * 300)
    artifact.write_text(content, encoding="utf-8")
    linked = workspace / ".omc" / "artifacts" / "ask" / "answer.md"
    linked.parent.mkdir(parents=True)
    linked.write_text("linked content", encoding="utf-8")
    monkeypatch.setenv("NOETICBRAID_WORKSPACE_ROOT", str(workspace))
    _patch_run(monkeypatch, "see .omc/artifacts/ask/answer.md")

    module.execute_invocation_plan(_plan(_claude_item(artifact)), provider_mode=True)

    assert artifact.read_text(encoding="utf-8") == content
    assert "copied from" not in artifact.read_text(encoding="utf-8")


def test_claude_link_inside_workspace_is_copied_with_trailer(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    linked = workspace / ".omc" / "artifacts" / "ask" / "answer.md"
    linked.parent.mkdir(parents=True)
    linked.write_text("linked longform answer", encoding="utf-8")
    artifact = tmp_path / "claude.md"
    monkeypatch.setenv("NOETICBRAID_WORKSPACE_ROOT", str(workspace))
    _patch_run(monkeypatch, "saved at .omc/artifacts/ask/answer.md")

    module.execute_invocation_plan(_plan(_claude_item(artifact)), provider_mode=True)

    text = artifact.read_text(encoding="utf-8")
    assert text.startswith("linked longform answer\n")
    assert f"<!-- copied from {linked.resolve()} -->" in text


def test_claude_link_escape_outside_workspace_is_refused_and_stdout_written(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("do not copy", encoding="utf-8")
    artifact = tmp_path / "claude.md"
    stdout = "saved at .omc/artifacts/ask/../../../../outside.md"
    monkeypatch.setenv("NOETICBRAID_WORKSPACE_ROOT", str(workspace))
    _patch_run(monkeypatch, stdout)

    module.execute_invocation_plan(_plan(_claude_item(artifact)), provider_mode=True)

    assert artifact.read_text(encoding="utf-8") == stdout

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from noeticbraid.tools.multimodel_alliance import invocation_plan as module


def _item(provider: str, artifact_path: Path) -> dict[str, Any]:
    return {
        "provider": provider,
        "model_ref": f"model_{provider}",
        "role": provider,
        "artifact_path": str(artifact_path),
        "argv": [provider],
        "env": {},
    }


def _plan(item: dict[str, Any]) -> dict[str, Any]:
    return {"may_execute": True, "plans": [item]}


def _completed(provider: str, returncode: int, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([provider], returncode, stdout=stdout, stderr=stderr)


def _patch_run(monkeypatch: pytest.MonkeyPatch, responses: list[subprocess.CompletedProcess[str]]) -> list[list[str]]:
    calls: list[list[str]] = []

    def fake_run(argv: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return responses.pop(0)

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    return calls


def test_gemini_success_first_try_has_no_retry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    sleeps: list[int] = []
    calls = _patch_run(monkeypatch, [_completed("gemini", 0, stdout="ok")])
    monkeypatch.setattr(module.time, "sleep", lambda delay: sleeps.append(delay))

    result = module.execute_invocation_plan(_plan(_item("gemini", tmp_path / "gemini.md")), provider_mode=True)

    assert len(calls) == 1
    assert sleeps == []
    assert result[0]["returncode"] == 0
    assert result[0]["retries_attempted"] == 0


def test_gemini_429_retries_once_then_succeeds(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    sleeps: list[int] = []
    calls = _patch_run(
        monkeypatch,
        [
            _completed("gemini", 1, stderr="429 rate limit"),
            _completed("gemini", 0, stdout="ok after retry"),
        ],
    )
    monkeypatch.setattr(module.time, "sleep", lambda delay: sleeps.append(delay))

    artifact = tmp_path / "gemini.md"
    result = module.execute_invocation_plan(_plan(_item("gemini", artifact)), provider_mode=True)

    assert len(calls) == 2
    assert sleeps == [30]
    assert result[0]["returncode"] == 0
    assert result[0]["retries_attempted"] == 1
    assert artifact.read_text(encoding="utf-8") == "ok after retry"


def test_gemini_persistent_429_uses_three_deterministic_retries(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    sleeps: list[int] = []
    calls = _patch_run(
        monkeypatch,
        [
            _completed("gemini", 1, stderr="quota exceeded"),
            _completed("gemini", 1, stderr="resource_exhausted"),
            _completed("gemini", 1, stdout="rate limit"),
            _completed("gemini", 1, stderr="429"),
        ],
    )
    monkeypatch.setattr(module.time, "sleep", lambda delay: sleeps.append(delay))

    artifact = tmp_path / "gemini.md"
    result = module.execute_invocation_plan(_plan(_item("gemini", artifact)), provider_mode=True)

    assert len(calls) == 4
    assert sleeps == [30, 60, 120]
    assert result[0]["returncode"] == 1
    assert result[0]["retries_attempted"] == 3
    assert artifact.read_text(encoding="utf-8") == "429"


def test_non_gemini_error_does_not_retry_even_with_rate_limit_text(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    sleeps: list[int] = []
    calls = _patch_run(monkeypatch, [_completed("codex", 1, stderr="429 rate limit")])
    monkeypatch.setattr(module.time, "sleep", lambda delay: sleeps.append(delay))

    result = module.execute_invocation_plan(_plan(_item("codex", tmp_path / "codex.md")), provider_mode=True)

    assert len(calls) == 1
    assert sleeps == []
    assert result[0]["returncode"] == 1
    assert result[0]["retries_attempted"] == 0

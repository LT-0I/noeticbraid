# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parent.parent
for path in (REPO_ROOT / "packages" / "noeticbraid-core" / "src", PACKAGE_ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from noeticbraid_backend.omc_workspace.capability_registry import health_check

FIXTURE_PATH = PACKAGE_ROOT / "tests" / "fixtures" / "capability_health_live_subprocess_mock.json"


def _fixture() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _artifact_payload(tmp_path: Path, result: dict[str, Any]) -> dict[str, Any]:
    artifact_ref = result["artifact_ref"]
    assert artifact_ref is not None
    artifact_path = tmp_path / artifact_ref
    assert artifact_path.exists()
    return json.loads(artifact_path.read_text(encoding="utf-8"))


def test_real_health_check_returns_version_when_cli_exists(tmp_path: Path, monkeypatch) -> None:
    fixture = _fixture()["cap_codex_cli"]
    calls: list[tuple[list[str], dict[str, Any]]] = []
    monkeypatch.setenv("NOETICBRAID_HEALTH_CHECK_LIVE", "1")

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(**fixture)

    monkeypatch.setattr("noeticbraid_backend.omc_workspace.capability_registry.subprocess.run", fake_run)

    payload = health_check("cap_codex_cli", project_root=tmp_path)

    assert calls == [
        (
            ["codex", "--version"],
            {"capture_output": True, "timeout": 5, "check": False, "text": True},
        )
    ]
    result = payload["result"]
    assert result["mode"] == "live_opt_in"
    assert result["status"] == "healthy"
    assert result["version"] == "codex 5.5"
    assert result["last_checked"] is not None
    assert result["error_msg"] is None
    artifact = _artifact_payload(tmp_path, result)
    assert artifact["mode"] == "live"
    assert artifact["status"] == "healthy"
    assert artifact["version"] == "codex 5.5"
    assert artifact["sdd_id"] == "SDD-D2-03"


def test_real_health_check_fail_soft_on_subprocess_timeout(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("NOETICBRAID_HEALTH_CHECK_LIVE", "1")

    def fake_run(_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd=["codex", "--version"], timeout=5)

    monkeypatch.setattr("noeticbraid_backend.omc_workspace.capability_registry.subprocess.run", fake_run)

    result = health_check("cap_codex_cli", project_root=tmp_path)["result"]

    assert result["status"] == "unhealthy"
    assert result["version"] is None
    assert result["last_checked"] is not None
    assert "timed out after 5 seconds" in result["error_msg"]
    assert "[" not in result["error_msg"]
    assert _artifact_payload(tmp_path, result)["status"] == "unhealthy"


def test_real_health_check_fail_soft_on_subprocess_filenotfound(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("NOETICBRAID_HEALTH_CHECK_LIVE", "1")

    def fake_run(_args, **_kwargs):
        raise FileNotFoundError("No such file or directory: /home/l1u/bin/codex")

    monkeypatch.setattr("noeticbraid_backend.omc_workspace.capability_registry.subprocess.run", fake_run)

    result = health_check("cap_codex_cli", project_root=tmp_path)["result"]

    assert result["status"] == "unhealthy"
    assert result["version"] is None
    assert result["error_msg"] == "codex executable not found"
    assert _artifact_payload(tmp_path, result)["error_msg"] == "codex executable not found"


def test_real_health_check_fail_soft_on_subprocess_nonzero_exit(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("NOETICBRAID_HEALTH_CHECK_LIVE", "1")
    monkeypatch.setenv("USER", "l1u")

    def fake_run(_args, **_kwargs):
        return SimpleNamespace(
            returncode=2,
            stdout="",
            stderr="fatal config at /home/l1u/.config/noetic/token=secret-value",
        )

    monkeypatch.setattr("noeticbraid_backend.omc_workspace.capability_registry.subprocess.run", fake_run)

    result = health_check("cap_codex_cli", project_root=tmp_path)["result"]

    assert result["status"] == "unhealthy"
    assert result["version"] is None
    assert result["error_msg"] is not None
    assert "/home/l1u" not in result["error_msg"]
    assert "secret-value" not in result["error_msg"]
    assert _artifact_payload(tmp_path, result)["exit_code"] == 2


def test_real_health_check_error_msg_truncated_to_256_chars(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("NOETICBRAID_HEALTH_CHECK_LIVE", "1")

    def fake_run(_args, **_kwargs):
        return SimpleNamespace(returncode=9, stdout="", stderr="x" * 400)

    monkeypatch.setattr("noeticbraid_backend.omc_workspace.capability_registry.subprocess.run", fake_run)

    result = health_check("cap_codex_cli", project_root=tmp_path)["result"]

    assert result["status"] == "unhealthy"
    assert len(result["error_msg"]) == 256
    assert len(_artifact_payload(tmp_path, result)["error_msg"]) == 256


def test_real_health_check_error_msg_does_not_leak_raw_subprocess_output(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("NOETICBRAID_HEALTH_CHECK_LIVE", "1")
    monkeypatch.setenv("USER", "l1u")

    def fake_run(_args, **_kwargs):
        return SimpleNamespace(
            returncode=1,
            stdout="RAW_STDOUT_SHOULD_NOT_LEAK",
            stderr="failure in /home/l1u/private/profile with token=abc123",
        )

    monkeypatch.setattr("noeticbraid_backend.omc_workspace.capability_registry.subprocess.run", fake_run)

    payload = health_check("cap_codex_cli", project_root=tmp_path)
    serialized = json.dumps(payload, ensure_ascii=False)
    artifact = _artifact_payload(tmp_path, payload["result"])
    artifact_serialized = json.dumps(artifact, ensure_ascii=False)

    assert payload["result"]["status"] == "unhealthy"
    assert "RAW_STDOUT_SHOULD_NOT_LEAK" not in serialized
    assert "RAW_STDOUT_SHOULD_NOT_LEAK" not in artifact_serialized
    assert "/home/l1u" not in serialized
    assert "/home/l1u" not in artifact_serialized
    assert "abc123" not in serialized
    assert "abc123" not in artifact_serialized
    forbidden = {"stdout", "stderr", "raw_output", "command_output", "env", "cwd", "token"}
    assert forbidden.isdisjoint(artifact)


def test_gemini_web_returns_not_implemented_placeholder_with_hotfix_note(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("NOETICBRAID_HEALTH_CHECK_LIVE", "1")

    def explode(*_args, **_kwargs):
        raise AssertionError("Gemini Web placeholder must not execute subprocess or browser automation")

    monkeypatch.setattr("noeticbraid_backend.omc_workspace.capability_registry.subprocess.run", explode)

    result = health_check("cap_gemini_web", project_root=tmp_path)["result"]

    assert result["status"] == "not_implemented"
    assert result["version"] is None
    assert result["error_msg"] == "real ping deferred to SDD-D2-03-hotfix-01"
    assert result["last_checked"] is not None
    assert result["artifact_ref"] is None
    assert not (tmp_path / ".omx" / "artifacts").exists()


def test_real_health_check_writes_ledger_artifact_with_live_mode_only(tmp_path: Path, monkeypatch) -> None:
    def explode(*_args, **_kwargs):
        raise AssertionError("mock mode must not execute provider CLI")

    monkeypatch.delenv("NOETICBRAID_HEALTH_CHECK_LIVE", raising=False)
    monkeypatch.setattr("noeticbraid_backend.omc_workspace.capability_registry.subprocess.run", explode)

    mock_result = health_check("cap_codex_cli", project_root=tmp_path)["result"]
    assert mock_result["mode"] == "mock"
    assert mock_result["artifact_ref"] is None
    assert not (tmp_path / ".omx" / "artifacts").exists()

    monkeypatch.setenv("NOETICBRAID_HEALTH_CHECK_LIVE", "1")
    monkeypatch.setattr(
        "noeticbraid_backend.omc_workspace.capability_registry.subprocess.run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="codex 5.5\n", stderr=""),
    )

    live_result = health_check("cap_codex_cli", project_root=tmp_path)["result"]
    artifact = _artifact_payload(tmp_path, live_result)

    assert live_result["artifact_ref"].startswith(".omx/artifacts/health-check-cap_codex_cli-")
    assert artifact["sdd_id"] == "SDD-D2-03"
    assert artifact["artifact_schema_version"] == "capability-health/v1"
    assert artifact["capability_id"] == "cap_codex_cli"
    assert artifact["mode"] == "live"
    assert artifact["status"] == "healthy"
    assert artifact["version"] == "codex 5.5"
    assert artifact["last_checked"] == live_result["last_checked"]
    assert artifact["error_msg"] is None
    assert artifact["artifact_created_at"].endswith("Z")
    assert "duration_ms" in artifact
    assert artifact["exit_code"] == 0
    forbidden = {"stdout", "stderr", "raw_output", "command_output", "env", "cwd", "argv", "token"}
    assert forbidden.isdisjoint(artifact)


def test_mock_mode_unchanged_when_env_not_set(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("NOETICBRAID_HEALTH_CHECK_LIVE", raising=False)

    def explode(*_args, **_kwargs):
        raise AssertionError("mock health check must not execute provider CLI")

    monkeypatch.setattr("noeticbraid_backend.omc_workspace.capability_registry.subprocess.run", explode)

    payload = health_check("cap_codex_cli", project_root=tmp_path)
    result = payload["result"]

    assert result["mode"] == "mock"
    assert result["status"] == "available"
    assert result["summary"] == "Mock health OK for Codex CLI; live provider checks are opt-in."
    assert result["artifact_ref"] is None
    assert result["version"] is None
    assert result["last_checked"] is None
    assert result["error_msg"] is None
    assert payload["capability"]["health_mode"] == "mock"
    assert not (tmp_path / ".omx" / "artifacts").exists()

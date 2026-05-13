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

from noeticbraid_backend.omc_workspace import web_ai_hub_client as target_module


def _consumer_health(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": True,
        "target": "chatgpt",
        "profile": "chatgpt",
        "connected": True,
        "pageCount": 2,
        "loginLikeState": "healthy",
        "status": "ok",
        "errorCode": None,
        "message": "ChatGPT target is available.",
        "checkedAt": "2026-05-13T08:29:20.508Z",
    }
    payload.update(overrides)
    return payload


def _assert_consumer_error_shape(result: dict[str, Any], *, error_code: str) -> None:
    assert result["ok"] is False
    assert result["target"] == "chatgpt"
    assert result["profile"] == "chatgpt"
    assert result["connected"] is False
    assert result["pageCount"] == 0
    assert result["loginLikeState"] == "not_implemented"
    assert result["status"] == "needs_review"
    assert result["errorCode"] == error_code
    assert isinstance(result["message"], str) and result["message"]
    assert isinstance(result["checkedAt"], str) and result["checkedAt"]


def test_run_hub_command_success_parses_json(tmp_path: Path, monkeypatch) -> None:
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout='{"connected": true}', stderr="")

    monkeypatch.setattr(target_module.subprocess, "run", fake_run)

    result = target_module.run_hub_command(
        ["consumer:health", "--target", "chatgpt", "--profile", "chatgpt", "--json"],
        hub_path=tmp_path,
        timeout=15,
    )

    assert result == {"connected": True}
    assert calls == [
        (
            [
                "node",
                str(tmp_path / "dist" / "src" / "cli.js"),
                "consumer:health",
                "--target",
                "chatgpt",
                "--profile",
                "chatgpt",
                "--json",
            ],
            {"capture_output": True, "timeout": 15, "check": False, "text": True},
        )
    ]


def test_run_hub_command_timeout_fail_soft(tmp_path: Path, monkeypatch) -> None:
    def fake_run(_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd=["node", "cli.js"], timeout=15)

    monkeypatch.setattr(target_module.subprocess, "run", fake_run)

    result = target_module.run_hub_command(["consumer:health"], hub_path=tmp_path)

    assert result["ok"] is False
    assert result["error_type"] == "timeout"
    assert "timed out after 15 seconds" in result["error"]


def test_run_hub_command_file_not_found_fail_soft(tmp_path: Path, monkeypatch) -> None:
    def fake_run(_args, **_kwargs):
        raise FileNotFoundError("missing /home/l1u/bin/node")

    monkeypatch.setattr(target_module.subprocess, "run", fake_run)

    result = target_module.run_hub_command(["consumer:health"], hub_path=tmp_path)

    assert result["ok"] is False
    assert result["error_type"] == "file_not_found"
    assert "/home/l1u" not in result["error"]


def test_run_hub_command_non_zero_exit_fail_soft(tmp_path: Path, monkeypatch) -> None:
    def fake_run(_args, **_kwargs):
        return SimpleNamespace(returncode=2, stdout="", stderr="fatal token=secret-value at /home/l1u/profile")

    monkeypatch.setattr(target_module.subprocess, "run", fake_run)

    result = target_module.run_hub_command(["consumer:health"], hub_path=tmp_path)

    assert result["ok"] is False
    assert result["error_type"] == "non_zero_exit"
    assert result["exitCode"] == 2
    assert "secret-value" not in result["error"]
    assert "/home/l1u" not in result["error"]


def test_check_chatgpt_consumer_health_happy_path_returns_contract_unchanged(tmp_path: Path, monkeypatch) -> None:
    payload = _consumer_health()
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(target_module.subprocess, "run", fake_run)

    result = target_module.check_chatgpt_consumer_health(tmp_path)

    assert result == payload
    assert calls == [
        (
            [
                "node",
                str(tmp_path / "dist" / "src" / "cli.js"),
                "consumer:health",
                "--target",
                "chatgpt",
                "--profile",
                "chatgpt",
                "--json",
            ],
            {"capture_output": True, "timeout": 15, "check": False, "text": True},
        )
    ]


def test_check_chatgpt_consumer_health_non_zero_hub_not_built(tmp_path: Path, monkeypatch) -> None:
    def fake_run(_args, **_kwargs):
        return SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="HUB_NOT_BUILT: Hub dist CLI is missing; run npm run build in /home/l1u/hub.",
        )

    monkeypatch.setattr(target_module.subprocess, "run", fake_run)

    result = target_module.check_chatgpt_consumer_health(tmp_path)

    _assert_consumer_error_shape(result, error_code="HUB_NOT_BUILT")
    assert "/home/l1u" not in result["message"]
    assert "Hub dist CLI is missing" in result["message"]


def test_check_chatgpt_consumer_health_command_timeout(tmp_path: Path, monkeypatch) -> None:
    def fake_run(_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd=["node", "cli.js"], timeout=15)

    monkeypatch.setattr(target_module.subprocess, "run", fake_run)

    result = target_module.check_chatgpt_consumer_health(tmp_path)

    _assert_consumer_error_shape(result, error_code="COMMAND_TIMEOUT")
    assert "timed out" in result["message"]


def test_check_chatgpt_consumer_health_invalid_json(tmp_path: Path, monkeypatch) -> None:
    def fake_run(_args, **_kwargs):
        return SimpleNamespace(returncode=0, stdout="{not-json", stderr="")

    monkeypatch.setattr(target_module.subprocess, "run", fake_run)

    result = target_module.check_chatgpt_consumer_health(tmp_path)

    _assert_consumer_error_shape(result, error_code="INVALID_JSON")
    assert "invalid JSON" in result["message"]


def test_check_chatgpt_consumer_health_tolerates_extra_forbidden_field(tmp_path: Path, monkeypatch) -> None:
    payload = _consumer_health(cdpEndpoint="http://127.0.0.1:9222")

    def fake_run(_args, **_kwargs):
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(target_module.subprocess, "run", fake_run)

    result = target_module.check_chatgpt_consumer_health(tmp_path)

    assert result["ok"] is True
    assert result["cdpEndpoint"] == "http://127.0.0.1:9222"


def test_sanitize_error_msg_redacts_home_path_email_token(monkeypatch) -> None:
    monkeypatch.setenv("USER", "l1u")
    message = "ChatGPT /home/l1u/private /tmp/file alice@example.com token=secret Bearer abcdef"

    sanitized = target_module.sanitize_error_msg(message)

    assert "/home/l1u" not in sanitized
    assert "/tmp/file" not in sanitized
    assert "alice@example.com" not in sanitized
    assert "secret" not in sanitized
    assert "abcdef" not in sanitized
    assert "l1u" not in sanitized
    assert "[email]" in sanitized
    assert "[redacted]" in sanitized

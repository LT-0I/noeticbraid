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

FIXTURE_PATH = PACKAGE_ROOT / "tests" / "fixtures" / "chatgpt_web_browser_pages_mock.json"


def _fixture(key: str) -> list[dict[str, Any]]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))[key]


def test_run_hub_command_success_parses_json(tmp_path: Path, monkeypatch) -> None:
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout='{"connected": true}', stderr="")

    monkeypatch.setattr(target_module.subprocess, "run", fake_run)

    result = target_module.run_hub_command(
        ["browser:status", "--profile", "chatgpt", "--json"], hub_path=tmp_path, timeout=5
    )

    assert result == {"connected": True}
    assert calls == [
        (
            ["node", str(tmp_path / "dist" / "src" / "cli.js"), "browser:status", "--profile", "chatgpt", "--json"],
            {"capture_output": True, "timeout": 5, "check": False, "text": True},
        )
    ]


def test_run_hub_command_timeout_fail_soft(tmp_path: Path, monkeypatch) -> None:
    def fake_run(_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd=["node", "cli.js"], timeout=15)

    monkeypatch.setattr(target_module.subprocess, "run", fake_run)

    result = target_module.run_hub_command(["browser:pages"], hub_path=tmp_path)

    assert result["ok"] is False
    assert result["error_type"] == "timeout"
    assert "timed out after 15 seconds" in result["error"]


def test_run_hub_command_file_not_found_fail_soft(tmp_path: Path, monkeypatch) -> None:
    def fake_run(_args, **_kwargs):
        raise FileNotFoundError("missing /home/l1u/bin/node")

    monkeypatch.setattr(target_module.subprocess, "run", fake_run)

    result = target_module.run_hub_command(["browser:status"], hub_path=tmp_path)

    assert result["ok"] is False
    assert result["error_type"] == "file_not_found"
    assert "/home/l1u" not in result["error"]


def test_run_hub_command_non_zero_exit_fail_soft(tmp_path: Path, monkeypatch) -> None:
    def fake_run(_args, **_kwargs):
        return SimpleNamespace(returncode=2, stdout="", stderr="fatal token=secret-value at /home/l1u/profile")

    monkeypatch.setattr(target_module.subprocess, "run", fake_run)

    result = target_module.run_hub_command(["browser:status"], hub_path=tmp_path)

    assert result["ok"] is False
    assert result["error_type"] == "non_zero_exit"
    assert result["exitCode"] == 2
    assert "secret-value" not in result["error"]
    assert "/home/l1u" not in result["error"]


def test_check_hub_browser_status_returns_dict(tmp_path: Path, monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run_hub_command(args, *, hub_path, timeout=15):
        calls.append(args)
        assert hub_path == tmp_path
        assert timeout == 5
        return {"connected": True, "lastError": None, "pages": [{"url": "https://chatgpt.com/"}]}

    monkeypatch.setattr(target_module, "run_hub_command", fake_run_hub_command)

    status = target_module.check_hub_browser_status(tmp_path)

    assert calls == [["browser:status", "--profile", "chatgpt", "--json"]]
    assert status == {"connected": True, "lastError": None, "pageCount": 1}


def test_parse_chatgpt_login_state_healthy() -> None:
    status, version, error_msg = target_module.parse_chatgpt_login_state(_fixture("logged-in"))

    assert status == "healthy"
    assert version == "ChatGPT"
    assert error_msg is None


def test_parse_chatgpt_login_state_unhealthy_login_required() -> None:
    status, version, error_msg = target_module.parse_chatgpt_login_state(_fixture("login-required"))

    assert status == "unhealthy"
    assert version is None
    assert error_msg == "ChatGPT Web 未登录"


def test_parse_chatgpt_login_state_not_implemented_no_chatgpt_page() -> None:
    status, version, error_msg = target_module.parse_chatgpt_login_state(_fixture("no-chatgpt-page"))

    assert status == "not_implemented"
    assert version is None
    assert error_msg == "Chrome 未打开 ChatGPT 页, 请在 hub 内手动 browser:launch + browser:open https://chatgpt.com/"


def test_sanitize_page_title_truncates_to_64() -> None:
    title = "ChatGPT " + ("x" * 100)

    sanitized = target_module._sanitize_page_title(title)

    assert len(sanitized) == 64
    assert len(sanitized) != 256


def test_sanitize_page_title_redacts_home_path_email_token(monkeypatch) -> None:
    monkeypatch.setenv("USER", "l1u")
    title = "ChatGPT /home/l1u/private /tmp/file alice@example.com token=secret Bearer abcdef"

    sanitized = target_module._sanitize_page_title(title, max_chars=256)

    assert "/home/l1u" not in sanitized
    assert "/tmp/file" not in sanitized
    assert "alice@example.com" not in sanitized
    assert "secret" not in sanitized
    assert "abcdef" not in sanitized
    assert "l1u" not in sanitized
    assert "[email]" in sanitized
    assert "[redacted]" in sanitized

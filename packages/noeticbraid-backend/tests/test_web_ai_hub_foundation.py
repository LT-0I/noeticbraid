# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import subprocess
import urllib.error
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from noeticbraid_backend.omc_workspace import web_ai_hub_automation as automation
from noeticbraid_backend.omc_workspace import web_ai_hub_client as client
from noeticbraid_backend.omc_workspace import web_ai_hub_compat as compat


LAUNCH_SAFE_OP = "webai_task_status"
PAGEFUL_OP = "webai_chatgpt_send_prompt"


class _FakeCdpResponse:
    def __init__(self, *, status: int = 200, body: bytes = b'{"Browser":"Chrome"}') -> None:
        self.status = status
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        return None

    def read(self) -> bytes:
        return self._body


def _write_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_hub(root: Path, *, label: str = "hub") -> Path:
    hub = root / label
    _write_file(hub / "dist" / "src" / "cli.js", "console.log('cli');\n")
    _write_file(hub / "dist" / "z.txt", "z\n")
    for dep in compat.ENUMERATED_OFF_DIST_DEPS:
        _write_file(hub / "node_modules" / dep / "package.json", f'{{"name":"{dep}"}}\n')
        _write_file(hub / "node_modules" / dep / "index.js", f"module.exports = '{dep}';\n")
    return hub


def _env(hub: Path | None = None, **overrides: str) -> dict[str, str]:
    environ = {compat.AUTOMATION_ENV: "1"}
    if hub is not None:
        environ[compat.HUB_PATH_ENV] = str(hub)
    environ.update(overrides)
    return environ


def _pin_digest(monkeypatch: pytest.MonkeyPatch, hub: Path) -> str:
    digest = compat.compute_exec_digest(hub)
    assert digest not in {None, "HUB_NOT_BUILT"}
    assert isinstance(digest, str)
    monkeypatch.setattr(compat, "PINNED_HUB_EXEC_DIGEST", digest)
    return digest


def _tools_payload(*names: str) -> dict[str, Any]:
    return {"data": [{"name": name, "description": "", "inputSchema": {}} for name in names]}


def test_opt_in_parser_mirrors_d9_values() -> None:
    for raw in ("1", "true", " TRUE "):
        assert compat.parse_opt_in(raw) is True
    for raw in ("0", "yes", "", None, "2"):
        assert compat.parse_opt_in(raw) is False

    assert compat.read_automation_enabled({compat.AUTOMATION_ENV: "true"}) is True
    assert compat.read_automation_enabled({compat.AUTOMATION_ENV: "yes"}) is False


def test_gate_disabled_opt_in_short_circuits_before_digest_or_spawn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_digest(_hub: Path) -> str:
        calls.append("digest")
        return "unexpected"

    def fake_run(*_args, **_kwargs):
        calls.append("spawn")
        return _tools_payload(LAUNCH_SAFE_OP)

    monkeypatch.setattr(compat, "compute_exec_digest", fake_digest)
    monkeypatch.setattr(automation, "run_hub_command", fake_run)

    result = automation.web_ai_hub_gate(
        LAUNCH_SAFE_OP,
        environ={compat.HUB_PATH_ENV: str(tmp_path)},
    )

    assert result == {"status": "not_implemented", "reason": "web-ai automation opt-in disabled"}
    assert calls == []


@pytest.mark.parametrize("operation", ["unknown_tool", "browser_launch", "research_aiaa_search"])
def test_gate_disallowed_and_hard_excluded_operations_do_not_spawn(
    operation: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(compat, "compute_exec_digest", lambda _hub: calls.append("digest") or "unexpected")
    monkeypatch.setattr(automation, "run_hub_command", lambda *_args, **_kwargs: calls.append("spawn"))

    result = automation.web_ai_hub_gate(operation, environ={compat.AUTOMATION_ENV: "1"})

    assert result == {"status": "not_implemented", "reason": "operation not allowed"}
    assert calls == []
    if operation != "unknown_tool":
        assert compat.is_hard_excluded(operation) is True


@pytest.mark.parametrize(
    "environ",
    [
        {compat.AUTOMATION_ENV: "1"},
        {compat.AUTOMATION_ENV: "1", compat.HUB_PATH_ENV: "relative/hub"},
        {compat.AUTOMATION_ENV: "1", compat.HUB_PATH_ENV: "/path/that/does/not/exist"},
    ],
)
def test_gate_hub_path_unavailable_short_circuits_before_digest_or_spawn(
    environ: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(compat, "compute_exec_digest", lambda _hub: calls.append("digest") or "unexpected")
    monkeypatch.setattr(automation, "run_hub_command", lambda *_args, **_kwargs: calls.append("spawn"))

    result = automation.web_ai_hub_gate(LAUNCH_SAFE_OP, environ=environ)

    assert result == {"status": "not_implemented", "reason": "hub path unavailable"}
    assert calls == []


def test_compute_exec_digest_missing_or_empty_dist_returns_hub_not_built(tmp_path: Path) -> None:
    assert compat.compute_exec_digest(tmp_path / "missing") == "HUB_NOT_BUILT"

    empty_hub = tmp_path / "empty"
    (empty_hub / "dist").mkdir(parents=True)
    for dep in compat.ENUMERATED_OFF_DIST_DEPS:
        _write_file(empty_hub / "node_modules" / dep / "package.json", f'{{"name":"{dep}"}}\n')
    assert compat.compute_exec_digest(empty_hub) == "HUB_NOT_BUILT"


def test_compute_exec_digest_is_deterministic_and_changes_on_file_bytes(tmp_path: Path) -> None:
    hub_a = _make_hub(tmp_path, label="a")
    hub_b = tmp_path / "b"
    for dep in reversed(compat.ENUMERATED_OFF_DIST_DEPS):
        _write_file(hub_b / "node_modules" / dep / "index.js", f"module.exports = '{dep}';\n")
        _write_file(hub_b / "node_modules" / dep / "package.json", f'{{"name":"{dep}"}}\n')
    _write_file(hub_b / "dist" / "z.txt", "z\n")
    _write_file(hub_b / "dist" / "src" / "cli.js", "console.log('cli');\n")

    digest_a = compat.compute_exec_digest(hub_a)
    digest_b = compat.compute_exec_digest(hub_b)

    assert isinstance(digest_a, str)
    assert digest_a == digest_b

    (hub_b / "dist" / "z.txt").write_text("changed\n", encoding="utf-8")
    assert compat.compute_exec_digest(hub_b) != digest_a


def test_compute_exec_digest_symlink_entries_and_symlink_roots_return_none(tmp_path: Path) -> None:
    hub = _make_hub(tmp_path, label="entry_symlink")
    (hub / "dist" / "link.js").symlink_to(hub / "dist" / "src" / "cli.js")
    assert compat.compute_exec_digest(hub) is None

    dist_symlink_hub = tmp_path / "dist_symlink_root"
    real_dist = tmp_path / "real_dist"
    real_dist.mkdir()
    (dist_symlink_hub).mkdir()
    (dist_symlink_hub / "dist").symlink_to(real_dist, target_is_directory=True)
    assert compat.compute_exec_digest(dist_symlink_hub) is None

    dep_symlink_hub = _make_hub(tmp_path, label="dep_symlink_root")
    dep_root = dep_symlink_hub / "node_modules" / compat.ENUMERATED_OFF_DIST_DEPS[0]
    for child in dep_root.iterdir():
        child.unlink()
    dep_root.rmdir()
    real_dep = tmp_path / "real_dep"
    real_dep.mkdir()
    dep_root.symlink_to(real_dep, target_is_directory=True)
    assert compat.compute_exec_digest(dep_symlink_hub) is None


def test_compute_exec_digest_walk_oserror_and_missing_dependency_return_none(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hub = _make_hub(tmp_path, label="walk_error")

    def broken_walk(*_args, **_kwargs):
        raise OSError("cannot walk /private/path")

    monkeypatch.setattr(compat.os, "walk", broken_walk)
    assert compat.compute_exec_digest(hub) is None

    missing_dep_hub = tmp_path / "missing_dep"
    _write_file(missing_dep_hub / "dist" / "src" / "cli.js", "console.log('cli');\n")
    assert compat.compute_exec_digest(missing_dep_hub) is None


def test_unset_pinned_digest_fails_closed_before_capability_probe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hub = _make_hub(tmp_path)
    calls: list[str] = []
    monkeypatch.setattr(compat, "PINNED_HUB_EXEC_DIGEST", "UNSET")
    monkeypatch.setattr(automation, "run_hub_command", lambda *_args, **_kwargs: calls.append("spawn"))

    result = automation.web_ai_hub_gate(LAUNCH_SAFE_OP, environ=_env(hub))

    assert result == {
        "status": "not_implemented",
        "reason": "hub exec closure unpinned/mismatch — manual review & re-pin required",
    }
    assert calls == []


def test_capability_probe_success_absent_error_and_malformed_payloads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hub = _make_hub(tmp_path)
    _pin_digest(monkeypatch, hub)
    calls: list[dict[str, Any]] = []

    def fake_run(_args, **kwargs):
        calls.append(kwargs)
        return _tools_payload(LAUNCH_SAFE_OP)

    monkeypatch.setattr(automation, "run_hub_command", fake_run)
    result = automation.web_ai_hub_gate(LAUNCH_SAFE_OP, environ=_env(hub))
    assert result == {
        "status": "ready",
        "operation": LAUNCH_SAFE_OP,
        "classification": "launch_safe",
        "cdp_endpoint_verified": False,
    }
    assert "env" not in calls[-1]

    monkeypatch.setattr(automation, "run_hub_command", lambda *_args, **_kwargs: _tools_payload("browser_status"))
    result = automation.web_ai_hub_gate(LAUNCH_SAFE_OP, environ=_env(hub))
    assert result == {"status": "not_implemented", "reason": "hub capability absent"}

    monkeypatch.setattr(automation, "run_hub_command", lambda *_args, **_kwargs: {"ok": False, "error_type": "timeout"})
    result = automation.web_ai_hub_gate(LAUNCH_SAFE_OP, environ=_env(hub))
    assert result == {"status": "not_implemented", "reason": "hub capability probe failed"}

    monkeypatch.setattr(automation, "run_hub_command", lambda *_args, **_kwargs: {"ok": True, "data": [{"title": "bad"}]})
    result = automation.web_ai_hub_gate(LAUNCH_SAFE_OP, environ=_env(hub))
    assert result == {"status": "not_implemented", "reason": "hub capability probe failed"}


@pytest.mark.parametrize(
    ("urlopen_result", "expected_reason"),
    [
        (urllib.error.URLError("refused"), "trusted CDP endpoint unreachable — operator must provision"),
        (TimeoutError("timeout"), "trusted CDP endpoint unreachable — operator must provision"),
        (_FakeCdpResponse(status=404), "trusted CDP endpoint unreachable — operator must provision"),
        (_FakeCdpResponse(status=500), "trusted CDP endpoint unreachable — operator must provision"),
        (_FakeCdpResponse(status=200, body=b"not-json"), "trusted CDP endpoint unreachable — operator must provision"),
    ],
)
def test_pageful_cdp_preflight_failures_return_not_implemented_after_probe_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    urlopen_result,
    expected_reason: str,
) -> None:
    hub = _make_hub(tmp_path)
    _pin_digest(monkeypatch, hub)
    probe_calls: list[list[str]] = []
    monkeypatch.setattr(
        automation,
        "run_hub_command",
        lambda args, **_kwargs: probe_calls.append(args) or _tools_payload(PAGEFUL_OP),
    )

    def fake_urlopen(_url, *, timeout):
        assert timeout == compat.CDP_PREFLIGHT_TIMEOUT_SECONDS
        if isinstance(urlopen_result, BaseException):
            raise urlopen_result
        return urlopen_result

    monkeypatch.setattr(automation.urllib.request, "urlopen", fake_urlopen)

    result = automation.web_ai_hub_gate(
        PAGEFUL_OP,
        environ=_env(hub, **{compat.CDP_PORT_ENV: "9222"}),
    )

    assert result == {"status": "not_implemented", "reason": expected_reason}
    assert probe_calls == [["mcp:tools", "--json"]]


def test_pageful_missing_cdp_port_is_not_configured_after_capability_probe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hub = _make_hub(tmp_path)
    _pin_digest(monkeypatch, hub)
    probe_calls: list[list[str]] = []
    monkeypatch.setattr(
        automation,
        "run_hub_command",
        lambda args, **_kwargs: probe_calls.append(args) or _tools_payload(PAGEFUL_OP),
    )
    monkeypatch.setattr(automation.urllib.request, "urlopen", lambda *_args, **_kwargs: pytest.fail("CDP should not be probed"))

    result = automation.web_ai_hub_gate(PAGEFUL_OP, environ=_env(hub))

    assert result == {"status": "not_implemented", "reason": "trusted CDP endpoint not configured"}
    assert probe_calls == [["mcp:tools", "--json"]]


def test_pageful_cdp_preflight_success_returns_ready(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hub = _make_hub(tmp_path)
    _pin_digest(monkeypatch, hub)
    monkeypatch.setattr(automation, "run_hub_command", lambda *_args, **_kwargs: _tools_payload(PAGEFUL_OP))
    monkeypatch.setattr(
        automation.urllib.request,
        "urlopen",
        lambda _url, *, timeout: _FakeCdpResponse(status=200, body=b'{"Browser":"Chrome"}'),
    )

    result = automation.web_ai_hub_gate(
        PAGEFUL_OP,
        environ=_env(hub, **{compat.CDP_HOST_ENV: "127.0.0.1", compat.CDP_PORT_ENV: "9222"}),
    )

    assert result == {
        "status": "ready",
        "operation": PAGEFUL_OP,
        "classification": "pageful",
        "cdp_endpoint_verified": True,
    }


def test_launch_safe_ready_skips_cdp_preflight(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hub = _make_hub(tmp_path)
    _pin_digest(monkeypatch, hub)
    monkeypatch.setattr(automation, "run_hub_command", lambda *_args, **_kwargs: _tools_payload(LAUNCH_SAFE_OP))
    monkeypatch.setattr(automation.urllib.request, "urlopen", lambda *_args, **_kwargs: pytest.fail("CDP should be skipped"))

    result = automation.web_ai_hub_gate(LAUNCH_SAFE_OP, environ=_env(hub))

    assert result == {
        "status": "ready",
        "operation": LAUNCH_SAFE_OP,
        "classification": "launch_safe",
        "cdp_endpoint_verified": False,
    }


def test_build_hub_env_scrubs_browser_executable_and_auto_confirm_without_mutating_input() -> None:
    environ = {
        compat.CDP_HOST_ENV: "10.0.0.2",
        compat.CDP_PORT_ENV: "9444",
        compat.CDP_ALLOW_NONLOOPBACK_ENV: "1",
        "WAH_BROWSER_EXECUTABLE": "/usr/bin/chrome",
        "WAH_AUTO_CONFIRM": "1",
        "KEEP": "yes",
    }

    pageful_env = automation.build_hub_env(environ, pageful=True)
    launch_safe_env = automation.build_hub_env(environ, pageful=False)

    assert pageful_env["WAH_CDP_HOST"] == "10.0.0.2"
    assert pageful_env["WAH_CDP_PORT"] == "9444"
    assert "WAH_BROWSER_EXECUTABLE" not in pageful_env
    assert "WAH_AUTO_CONFIRM" not in pageful_env
    assert "WAH_CDP_HOST" not in launch_safe_env
    assert "WAH_CDP_PORT" not in launch_safe_env
    assert "WAH_BROWSER_EXECUTABLE" not in launch_safe_env
    assert "WAH_AUTO_CONFIRM" not in launch_safe_env
    assert environ["WAH_BROWSER_EXECUTABLE"] == "/usr/bin/chrome"
    assert environ["WAH_AUTO_CONFIRM"] == "1"


def test_decision_order_short_circuits_env_allowlist_path_digest_probe_then_cdp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hub = _make_hub(tmp_path)
    digest = compat.compute_exec_digest(hub)
    assert isinstance(digest, str)
    events: list[str] = []

    def record_digest(_hub: Path) -> str:
        events.append("digest")
        return digest

    def record_probe(_args, **_kwargs):
        events.append("probe")
        return _tools_payload(PAGEFUL_OP)

    def record_cdp(_url, *, timeout):
        events.append("cdp")
        return _FakeCdpResponse(status=500)

    monkeypatch.setattr(compat, "compute_exec_digest", record_digest)
    monkeypatch.setattr(compat, "PINNED_HUB_EXEC_DIGEST", digest)
    monkeypatch.setattr(automation, "run_hub_command", record_probe)
    monkeypatch.setattr(automation.urllib.request, "urlopen", record_cdp)

    assert automation.web_ai_hub_gate(PAGEFUL_OP, environ={})["reason"] == "web-ai automation opt-in disabled"
    assert events == []

    assert automation.web_ai_hub_gate("browser_launch", environ={compat.AUTOMATION_ENV: "1"})["reason"] == "operation not allowed"
    assert events == []

    assert automation.web_ai_hub_gate(PAGEFUL_OP, environ={compat.AUTOMATION_ENV: "1"})["reason"] == "hub path unavailable"
    assert events == []

    monkeypatch.setattr(compat, "PINNED_HUB_EXEC_DIGEST", "different")
    assert "exec closure" in automation.web_ai_hub_gate(PAGEFUL_OP, environ=_env(hub))["reason"]
    assert events == []

    monkeypatch.setattr(compat, "PINNED_HUB_EXEC_DIGEST", "0" * 64 if digest != "0" * 64 else "1" * 64)
    assert "exec closure" in automation.web_ai_hub_gate(PAGEFUL_OP, environ=_env(hub))["reason"]
    assert events == ["digest"]

    events.clear()
    monkeypatch.setattr(compat, "PINNED_HUB_EXEC_DIGEST", digest)
    monkeypatch.setattr(automation, "run_hub_command", lambda *_args, **_kwargs: events.append("probe") or {"ok": False})
    assert automation.web_ai_hub_gate(PAGEFUL_OP, environ=_env(hub))["reason"] == "hub capability probe failed"
    assert events == ["digest", "probe"]

    events.clear()
    monkeypatch.setattr(automation, "run_hub_command", record_probe)
    assert automation.web_ai_hub_gate(PAGEFUL_OP, environ=_env(hub, **{compat.CDP_PORT_ENV: "9222"}))["reason"] == (
        "trusted CDP endpoint unreachable — operator must provision"
    )
    assert events == ["digest", "probe", "cdp"]


def test_run_hub_command_env_kwarg_is_backward_compatible_and_optional(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout='{"ok": true}', stderr="")

    monkeypatch.setattr(client.subprocess, "run", fake_run)

    assert client.run_hub_command(["mcp:tools", "--json"], hub_path=tmp_path) == {"ok": True}
    assert "env" not in calls[-1][1]
    assert calls[-1][1] == {"capture_output": True, "timeout": 15, "check": False, "text": True}

    env = {"A": "B"}
    assert client.run_hub_command(["mcp:tools", "--json"], hub_path=tmp_path, env=env) == {"ok": True}
    assert calls[-1][1]["env"] is env


def test_gate_failure_paths_return_dicts_and_do_not_raise(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hub = _make_hub(tmp_path)

    monkeypatch.setattr(compat, "digest_matches", lambda _hub: (_ for _ in ()).throw(RuntimeError("/secret/path")))
    result = automation.web_ai_hub_gate(LAUNCH_SAFE_OP, environ=_env(hub))
    assert isinstance(result, dict)
    assert result["status"] == "not_implemented"
    assert "/secret/path" not in result["reason"]

    monkeypatch.setattr(compat, "digest_matches", lambda _hub: ("ok", None))
    monkeypatch.setattr(automation, "run_hub_command", lambda *_args, **_kwargs: (_ for _ in ()).throw(subprocess.SubprocessError("boom")))
    result = automation.web_ai_hub_gate(LAUNCH_SAFE_OP, environ=_env(hub))
    assert result == {"status": "not_implemented", "reason": "hub capability probe failed"}

    monkeypatch.setattr(automation, "run_hub_command", lambda *_args, **_kwargs: _tools_payload(PAGEFUL_OP))
    monkeypatch.setattr(automation.urllib.request, "urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("boom")))
    result = automation.web_ai_hub_gate(PAGEFUL_OP, environ=_env(hub, **{compat.CDP_PORT_ENV: "9222"}))
    assert result == {
        "status": "not_implemented",
        "reason": "trusted CDP endpoint unreachable — operator must provision",
    }

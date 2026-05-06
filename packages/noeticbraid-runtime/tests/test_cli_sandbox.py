from __future__ import annotations

import sys
from pathlib import Path

import pytest

import noeticbraid_runtime.cli.sandbox as sandbox_module
from noeticbraid_runtime.cli.sandbox import CLISandbox, CLISandboxCommandDenied, CLISandboxCwdDenied, CLISandboxTimeout


def test_cli_sandbox_runs_allowlisted_command_inside_allowed_root(tmp_path: Path) -> None:
    sandbox = CLISandbox(allowed_commands=[Path(sys.executable).name], allowed_roots=[tmp_path])

    stdout, stderr, returncode = sandbox.run(
        [sys.executable, "-c", "import os; print(os.environ.get('VISIBLE')); print(os.environ.get('SECRET'))"],
        cwd=str(tmp_path),
        env_overlay={"VISIBLE": "yes", "SECRET": "hidden"},
        env_allowlist=["VISIBLE"],
        timeout_s=5,
    )

    assert returncode == 0
    assert stdout.splitlines() == ["yes", "None"]
    assert stderr == ""


def test_cli_sandbox_rejects_command_not_in_allowlist(tmp_path: Path) -> None:
    sandbox = CLISandbox(allowed_commands=["definitely-not-python"], allowed_roots=[tmp_path])

    with pytest.raises(CLISandboxCommandDenied):
        sandbox.run([sys.executable, "-c", "print('no')"], cwd=str(tmp_path))


def test_cli_sandbox_rejects_cwd_outside_allowed_root(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    outside = tmp_path / "outside"
    allowed.mkdir()
    outside.mkdir()
    sandbox = CLISandbox(allowed_commands=[Path(sys.executable).name], allowed_roots=[allowed])

    with pytest.raises(CLISandboxCwdDenied):
        sandbox.run([sys.executable, "-c", "print('no')"], cwd=str(outside))


def test_cli_sandbox_timeout_kills_process(tmp_path: Path) -> None:
    sandbox = CLISandbox(allowed_commands=[Path(sys.executable).name], allowed_roots=[tmp_path])

    with pytest.raises(CLISandboxTimeout) as excinfo:
        sandbox.run([sys.executable, "-c", "import time; time.sleep(5)"], cwd=str(tmp_path), timeout_s=0.2)

    assert excinfo.value.timeout_s == 0.2
    assert excinfo.value.returncode is not None


def test_cli_sandbox_timeout_invokes_process_tree_kill(tmp_path: Path, monkeypatch) -> None:
    killed_pids: list[int] = []

    def fake_kill_tree(proc) -> None:
        killed_pids.append(proc.pid)
        proc.kill()

    monkeypatch.setattr(sandbox_module, "_kill_tree", fake_kill_tree)
    sandbox = CLISandbox(allowed_commands=[Path(sys.executable).name], allowed_roots=[tmp_path])

    code = "import subprocess, sys, time; subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)']); time.sleep(30)"
    with pytest.raises(CLISandboxTimeout):
        sandbox.run([sys.executable, "-c", code], cwd=str(tmp_path), timeout_s=0.2)

    assert killed_pids

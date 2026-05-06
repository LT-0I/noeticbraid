# SPDX-License-Identifier: Apache-2.0
"""Allowlisted CLI sandbox wrapper."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path


class CLISandboxError(Exception):
    """Base class for CLI sandbox failures."""


class CLISandboxCommandDenied(CLISandboxError):
    """Raised when the executable is not allowlisted."""


class CLISandboxCwdDenied(CLISandboxError):
    """Raised when cwd is outside configured roots."""


class CLISandboxTimeout(CLISandboxError):
    """Raised when a child process exceeds timeout and is killed."""

    def __init__(self, timeout_s: float, stdout: str = "", stderr: str = "", returncode: int | None = None) -> None:
        super().__init__(f"CLI command timed out after {timeout_s} seconds and was killed")
        self.timeout_s = timeout_s
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


class CLISandbox:
    """Run allowlisted commands under cwd/env guards.

    - `allowed_commands` is matched against executable basename and stem.
    - `allowed_roots` are resolved and cwd must stay inside one of them.
    - environment is isolated by default; only `env_allowlist` overlay keys are passed.
    - `env_overlay` keys are deny-by-default: keys not listed in `env_allowlist`
      are silently discarded instead of being injected into the child environment.
    - timeout starts the child in a killable process group and terminates the tree
      before raising `CLISandboxTimeout`.
    """

    def __init__(self, *, allowed_commands: list[str] | tuple[str, ...], allowed_roots: list[str | Path] | tuple[str | Path, ...]) -> None:
        if not allowed_commands:
            raise ValueError("allowed_commands must be non-empty")
        if not allowed_roots:
            raise ValueError("allowed_roots must be non-empty")
        self.allowed_commands = {_normalize_command_name(command) for command in allowed_commands}
        self.allowed_roots = tuple(Path(root).resolve() for root in allowed_roots)

    def run(
        self,
        cmd: list[str],
        *,
        cwd: str,
        env_overlay: dict[str, str] | None = None,
        env_allowlist: list[str] | tuple[str, ...] | None = None,
        timeout_s: float = 120,
        capture_output: bool = True,
    ) -> tuple[str, str, int]:
        """Run a command and return `(stdout, stderr, returncode)`."""

        if not cmd:
            raise ValueError("cmd must be non-empty")
        if timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        self._check_command(cmd[0])
        resolved_cwd = self._check_cwd(cwd)
        env = self._build_env(env_overlay=env_overlay, env_allowlist=env_allowlist)
        popen_kwargs = {
            "cwd": str(resolved_cwd),
            "env": env,
            "shell": False,
            "stdout": subprocess.PIPE if capture_output else None,
            "stderr": subprocess.PIPE if capture_output else None,
            "text": True,
        }
        if sys.platform == "win32":
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            popen_kwargs["start_new_session"] = True
        proc = subprocess.Popen(cmd, **popen_kwargs)
        try:
            stdout, stderr = proc.communicate(timeout=timeout_s)
        except subprocess.TimeoutExpired as exc:
            _kill_tree(proc)
            try:
                stdout, stderr = proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                stdout, stderr = "", ""
            stdout = stdout if stdout is not None else _decode_timeout_stream(exc.stdout)
            stderr = stderr if stderr is not None else _decode_timeout_stream(exc.stderr)
            raise CLISandboxTimeout(timeout_s, stdout=stdout or "", stderr=stderr or "", returncode=-9) from None
        return stdout or "", stderr or "", proc.returncode

    def _check_command(self, executable: str) -> None:
        name = _normalize_command_name(executable)
        stem = Path(executable).stem.lower()
        if name not in self.allowed_commands and stem not in self.allowed_commands:
            raise CLISandboxCommandDenied(f"command is not allowlisted: {Path(executable).name}")

    def _check_cwd(self, cwd: str) -> Path:
        resolved = Path(cwd).resolve()
        if not resolved.exists() or not resolved.is_dir():
            raise CLISandboxCwdDenied(f"cwd is not a directory inside allowed roots: {cwd}")
        for root in self.allowed_roots:
            if resolved == root or root in resolved.parents:
                return resolved
        raise CLISandboxCwdDenied(f"cwd is outside allowed roots: {cwd}")

    def _build_env(self, *, env_overlay: dict[str, str] | None, env_allowlist: list[str] | tuple[str, ...] | None) -> dict[str, str]:
        env: dict[str, str] = {}
        if os.name == "nt":
            # Windows needs SystemRoot for subprocess startup in many environments.
            for key in ("SystemRoot", "ComSpec", "PATHEXT", "WINDIR"):
                if key in os.environ:
                    env[key] = os.environ[key]
        allowed = set(env_allowlist or [])
        for key, value in (env_overlay or {}).items():
            if key in allowed:
                env[key] = value
        return env


def _normalize_command_name(command: str) -> str:
    path = Path(command)
    return path.name.lower()


def _decode_timeout_stream(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _kill_tree(proc: subprocess.Popen[str]) -> None:
    """Kill a subprocess and its descendants best-effort."""

    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.poll() is None:
            proc.kill()
        return
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        if proc.poll() is None:
            proc.kill()


__all__ = [
    "CLISandbox",
    "CLISandboxCommandDenied",
    "CLISandboxCwdDenied",
    "CLISandboxError",
    "CLISandboxTimeout",
]

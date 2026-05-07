"""Guarded step execution for SP-E."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from .cards import ExecutionPolicy, WorkflowStep
from .errors import ExecutionDeniedError
from .redaction import redact_text


@dataclass(frozen=True)
class StepExecutionResult:
    step_id: str
    status: str
    execution_kind: str
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""
    reason: str = ""


class StepExecutor:
    def __init__(
        self,
        *,
        policy: ExecutionPolicy | None = None,
        allowed_cwd_roots: Iterable[Path | str] | None = None,
        allowed_shell_commands: Iterable[Sequence[str]] | None = None,
        default_timeout_seconds: int | None = None,
    ) -> None:
        if policy is None:
            policy = ExecutionPolicy(
                allowed_cwd_roots=tuple(str(root) for root in (allowed_cwd_roots or (".",))),
                allowed_shell_commands=tuple(tuple(command) for command in (allowed_shell_commands or ())),
                timeout_seconds=int(default_timeout_seconds if default_timeout_seconds is not None else 30),
            )
        self.policy = policy
        self.allowed_cwd_roots = tuple(Path(root).resolve() for root in policy.allowed_cwd_roots)
        self.allowed_shell_commands = tuple(tuple(command) for command in policy.allowed_shell_commands)
        self.default_timeout_seconds = int(policy.timeout_seconds)

    def execute(self, step: WorkflowStep, *, cwd: Path | str, dry_run: bool = False) -> StepExecutionResult:
        cwd_path = self._guard_cwd(cwd)
        if step.requires_confirmation:
            return StepExecutionResult(
                step_id=step.step_id,
                status="blocked",
                execution_kind="approval_gate",
                reason="requires_confirmation",
            )
        if step.command == "note":
            return StepExecutionResult(step_id=step.step_id, status="completed", execution_kind="note", reason="recorded")
        if step.command == "shell":
            if self.policy.approval_required_for_shell and not step.requires_confirmation:
                return StepExecutionResult(
                    step_id=step.step_id,
                    status="blocked",
                    execution_kind="approval_gate",
                    reason="policy_requires_shell_approval",
                )
            return self._execute_shell(step, cwd_path, dry_run=dry_run)
        raise ExecutionDeniedError("unsupported step command")

    def _execute_shell(self, step: WorkflowStep, cwd: Path, *, dry_run: bool) -> StepExecutionResult:
        if not step.argv:
            raise ExecutionDeniedError("shell step argv is required")
        argv = tuple(step.argv)
        if not self._is_allowlisted(argv):
            raise ExecutionDeniedError("shell command is not allowlisted")
        if dry_run:
            return StepExecutionResult(step_id=step.step_id, status="completed", execution_kind="shell_dry_run", reason="dry_run")
        try:
            completed = subprocess.run(
                argv,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=self.default_timeout_seconds,
                shell=False,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return StepExecutionResult(
                step_id=step.step_id,
                status="failed",
                execution_kind="shell",
                returncode=None,
                stdout=redact_text(exc.stdout or ""),
                stderr=redact_text(exc.stderr or "timeout"),
                reason="timeout",
            )
        status = "completed" if completed.returncode == 0 else "failed"
        return StepExecutionResult(
            step_id=step.step_id,
            status=status,
            execution_kind="shell",
            returncode=completed.returncode,
            stdout=redact_text(completed.stdout),
            stderr=redact_text(completed.stderr),
            reason="process_exit",
        )

    def _guard_cwd(self, cwd: Path | str) -> Path:
        resolved = Path(cwd).resolve()
        for root in self.allowed_cwd_roots:
            if resolved == root or root in resolved.parents:
                return resolved
        raise ExecutionDeniedError("cwd is outside allowed roots")

    def _is_allowlisted(self, argv: Sequence[str]) -> bool:
        normalized = _normalize_argv(argv)
        for allowed in self.allowed_shell_commands:
            if normalized == _normalize_argv(allowed):
                return True
        return False


def _normalize_argv(argv: Sequence[str]) -> tuple[str, ...]:
    result = []
    for index, part in enumerate(argv):
        value = str(part)
        if index == 0:
            name = Path(value).name.lower()
            if name.startswith("python"):
                value = "python"
            else:
                value = name
        result.append(value)
    return tuple(result)

from __future__ import annotations

import sys

import pytest

from noeticbraid.tools.workflow_scheduler.cards import ExecutionPolicy, WorkflowStep
from noeticbraid.tools.workflow_scheduler.executor import ExecutionDeniedError, StepExecutor


def test_note_step_records_without_subprocess(tmp_path):
    executor = StepExecutor(allowed_cwd_roots=[tmp_path], allowed_shell_commands=[] , default_timeout_seconds=5)
    result = executor.execute(WorkflowStep(step_id="step_note", role="planner", command="note"), cwd=tmp_path)

    assert result.status == "completed"
    assert result.execution_kind == "note"
    assert result.returncode is None


def test_shell_step_requires_allowlist_and_cwd_guard(tmp_path):
    policy = ExecutionPolicy(
        approval_required_for_shell=False,
        allowed_shell_commands=(("python", "-m", "pytest"),),
        allowed_cwd_roots=(str(tmp_path),),
        timeout_seconds=5,
    )
    executor = StepExecutor(policy=policy)

    with pytest.raises(ExecutionDeniedError, match="not allowlisted"):
        executor.execute(WorkflowStep(step_id="step_bad", role="coder", command="shell", argv=("python", "-c", "print(1)")), cwd=tmp_path)

    outside = tmp_path.parent
    with pytest.raises(ExecutionDeniedError, match="cwd"):
        executor.execute(WorkflowStep(step_id="step_cwd", role="coder", command="shell", argv=("python", "-m", "pytest")), cwd=outside)


def test_shell_step_executes_allowlisted_command_and_redacts_output(tmp_path):
    script = tmp_path / "test_redaction_target.py"
    script.write_text("def test_token_output():\n    print('token=SECRET1234567890')\n", encoding="utf-8")
    argv = (sys.executable, "-m", "pytest", "-q", str(script))
    policy = ExecutionPolicy(
        approval_required_for_shell=False,
        allowed_shell_commands=(argv,),
        allowed_cwd_roots=(str(tmp_path),),
        timeout_seconds=10,
    )
    executor = StepExecutor(policy=policy)

    result = executor.execute(WorkflowStep(step_id="step_pytest", role="verifier", command="shell", argv=argv), cwd=tmp_path)

    assert result.status == "completed"
    assert result.execution_kind == "shell"
    assert result.returncode == 0
    assert "SECRET1234567890" not in result.stdout


def test_requires_confirmation_blocks_before_shell_execution(tmp_path):
    executor = StepExecutor(allowed_cwd_roots=[tmp_path], allowed_shell_commands=[("python", "-m", "pytest")], default_timeout_seconds=5)
    result = executor.execute(WorkflowStep(step_id="step_confirm", role="coder", command="shell", argv=(sys.executable, "-m", "pytest", "--version"), requires_confirmation=True), cwd=tmp_path)

    assert result.status == "blocked"
    assert result.execution_kind == "approval_gate"
    assert result.returncode is None


def test_executor_approval_required_for_shell_blocks_when_unconfirmed(tmp_path):
    policy = ExecutionPolicy(
        approval_required_for_shell=True,
        allowed_shell_commands=(("python", "-m", "pytest"),),
        allowed_cwd_roots=(str(tmp_path),),
        timeout_seconds=5,
    )
    executor = StepExecutor(policy=policy)

    result = executor.execute(
        WorkflowStep(step_id="step_policy_gate", role="coder", command="shell", argv=(sys.executable, "-m", "pytest")),
        cwd=tmp_path,
    )

    assert result.status == "blocked"
    assert result.execution_kind == "approval_gate"
    assert result.reason == "policy_requires_shell_approval"
    exact_policy = ExecutionPolicy(
        approval_required_for_shell=False,
        allowed_shell_commands=(("python", "-m", "pytest"),),
        allowed_cwd_roots=(str(tmp_path),),
        timeout_seconds=5,
    )
    exact_executor = StepExecutor(policy=exact_policy)

    with pytest.raises(ExecutionDeniedError, match="not allowlisted"):
        exact_executor.execute(
            WorkflowStep(
                step_id="step_prefix_escape",
                role="coder",
                command="shell",
                argv=(sys.executable, "-m", "pytest", "--rootdir=/etc"),
            ),
            cwd=tmp_path,
            dry_run=True,
        )

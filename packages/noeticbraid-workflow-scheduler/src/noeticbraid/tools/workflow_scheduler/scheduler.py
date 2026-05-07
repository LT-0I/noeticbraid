"""WorkflowScheduler orchestration engine."""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from .cards import ExecutionPolicy, SUPPORTED_STATES, WorkflowCard
from .errors import ExecutionDeniedError, WorkflowSchedulerError
from .executor import StepExecutor
from .ledger import RunLedgerWriter
from .notifier import OutboundNotifier
from .state_store import update_scheduler_module_state

RUN_STATUS_TRANSITIONS = {
    None: frozenset({"pending"}),
    "pending": frozenset({"running"}),
    "running": frozenset({"completed", "failed", "blocked"}),
    "blocked": frozenset(),
    "completed": frozenset(),
    "failed": frozenset(),
}


@dataclass(frozen=True)
class RunResult:
    run_id: str
    workflow_id: str
    status: str
    dry_run: bool
    events_written: int
    state_updated: bool


@dataclass(frozen=True)
class ScheduleDue:
    workflow_id: str
    rule_id: str
    due_key: str
    due_epoch: int


class WorkflowScheduler:
    def __init__(
        self,
        *,
        ledger_path: Path,
        state_path: Optional[Path] = None,
        notify_log_path: Optional[Path] = None,
        execution_policy: ExecutionPolicy | None = None,
        allowed_cwd_roots: Iterable[Path | str] = (".",),
        allowed_shell_commands: Iterable[tuple[str, ...]] = (),
        timeout_seconds: int = 30,
    ) -> None:
        self.ledger = RunLedgerWriter(Path(ledger_path))
        self.state_path = Path(state_path) if state_path is not None else None
        self.notifier = OutboundNotifier(
            event_log_path=Path(notify_log_path) if notify_log_path is not None else Path(ledger_path).with_suffix(".notify.jsonl")
        )
        policy = execution_policy or ExecutionPolicy(
            allowed_cwd_roots=tuple(str(root) for root in allowed_cwd_roots),
            allowed_shell_commands=tuple(tuple(command) for command in allowed_shell_commands),
            timeout_seconds=timeout_seconds,
        )
        self.executor = StepExecutor(policy=policy)

    def run_card(self, card: WorkflowCard, *, dry_run: bool = False, cwd: Path | str = ".", run_id: str | None = None) -> RunResult:
        if card.mode == "autonomous" and not dry_run:
            raise WorkflowSchedulerError("autonomous mode is dry-run only")
        if run_id is not None:
            cached = self.ledger.find_run(run_id)
            if cached is not None:
                return RunResult(
                    run_id=str(cached["run_id"]),
                    workflow_id=str(cached["workflow_id"]),
                    status=str(cached["status"]),
                    dry_run=bool(cached["dry_run"]),
                    events_written=0,
                    state_updated=False,
                )
        actual_run_id = run_id or _new_run_id()
        events_written = 0
        status: str | None = None
        status = transition_status(status, "pending")
        events_written += self.ledger.write(
            run_id=actual_run_id,
            workflow_id=card.workflow_id,
            event_type="run_pending",
            status=status,
            dry_run=dry_run,
            task_id=card.task_id,
            task_type=card.task_type,
            approval_level=card.approval_level,
        )
        status = transition_status(status, "running")
        events_written += self.ledger.write(
            run_id=actual_run_id,
            workflow_id=card.workflow_id,
            event_type="run_started",
            status=status,
            dry_run=dry_run,
            task_id=card.task_id,
            task_type=card.task_type,
        )
        final_event_written = False
        for step in card.steps:
            events_written += self.ledger.write(
                run_id=actual_run_id,
                workflow_id=card.workflow_id,
                event_type="step_started",
                status="running",
                step_id=step.step_id,
                role=step.role,
            )
            try:
                result = self.executor.execute(step, cwd=cwd, dry_run=dry_run)
            except ExecutionDeniedError as exc:
                events_written += self.ledger.write(
                    run_id=actual_run_id,
                    workflow_id=card.workflow_id,
                    event_type="security_violation",
                    status="failed",
                    step_id=step.step_id,
                    reason=str(exc),
                )
                status = transition_status(status, "failed")
                events_written += self.ledger.write(
                    run_id=actual_run_id,
                    workflow_id=card.workflow_id,
                    event_type="run_failed",
                    status=status,
                    reason=str(exc),
                )
                final_event_written = True
                break
            if result.status == "blocked":
                events_written += self.ledger.write(
                    run_id=actual_run_id,
                    workflow_id=card.workflow_id,
                    event_type="step_blocked",
                    status="blocked",
                    step_id=step.step_id,
                    reason=result.reason,
                )
                self.notifier.send(
                    f"Workflow {card.workflow_id} requires confirmation at {step.step_id}",
                    level="requires_confirmation",
                    channel=card.notification_policy.get("default_channel", "local"),
                    refs={"workflow_id": card.workflow_id, "run_id": actual_run_id, "step_id": step.step_id},
                )
                status = transition_status(status, "blocked")
                break
            if result.status == "failed":
                events_written += self.ledger.write(
                    run_id=actual_run_id,
                    workflow_id=card.workflow_id,
                    event_type="step_failed",
                    status="failed",
                    step_id=step.step_id,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    returncode=result.returncode,
                )
                status = transition_status(status, "failed")
                events_written += self.ledger.write(
                    run_id=actual_run_id,
                    workflow_id=card.workflow_id,
                    event_type="run_failed",
                    status=status,
                    reason=result.reason,
                )
                final_event_written = True
                break
            events_written += self.ledger.write(
                run_id=actual_run_id,
                workflow_id=card.workflow_id,
                event_type="step_completed",
                status="running",
                step_id=step.step_id,
                execution_kind=result.execution_kind,
                stdout=result.stdout,
                stderr=result.stderr,
                returncode=result.returncode,
            )
        else:
            status = transition_status(status, "completed")
        if not final_event_written:
            events_written += self.ledger.write(run_id=actual_run_id, workflow_id=card.workflow_id, event_type="run_finished", status=status)
        state_updated = False
        if self.state_path is not None and not dry_run:
            update_scheduler_module_state(self.state_path, run_id=actual_run_id, status=status)
            state_updated = True
        return RunResult(
            run_id=actual_run_id,
            workflow_id=card.workflow_id,
            status=status,
            dry_run=dry_run,
            events_written=events_written,
            state_updated=state_updated,
        )


def transition_status(current_status: str | None, next_status: str) -> str:
    if current_status not in RUN_STATUS_TRANSITIONS:
        raise WorkflowSchedulerError("unsupported current status")
    if next_status not in SUPPORTED_STATES:
        raise WorkflowSchedulerError("unsupported next status")
    if next_status not in RUN_STATUS_TRANSITIONS[current_status]:
        raise WorkflowSchedulerError(f"invalid status transition: {current_status!r} -> {next_status!r}")
    return next_status


def dry_run_schedule(card: WorkflowCard, *, now_epoch: int, previous_due_keys: set[str]) -> list[ScheduleDue]:
    due = []
    if card.mode != "autonomous":
        return due
    for rule in card.schedule_rules:
        if not rule.enabled:
            continue
        slot = now_epoch // rule.every_seconds
        due_key = f"{card.workflow_id}:{rule.rule_id}:{slot}"
        if due_key not in previous_due_keys:
            due.append(ScheduleDue(workflow_id=card.workflow_id, rule_id=rule.rule_id, due_key=due_key, due_epoch=slot * rule.every_seconds))
    return due


def _new_run_id() -> str:
    stamp = dt.datetime.now(tz=dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"run_{stamp}_{uuid.uuid4().hex[:8]}"

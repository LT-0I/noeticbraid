"""CLI for the SP-E workflow scheduler."""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
import sys
import time
from pathlib import Path

from .cards import load_card
from .errors import WorkflowSchedulerError
from .notifier import OutboundNotifier
from .scheduler import WorkflowScheduler, dry_run_schedule

EXAMPLE_CARD = {
    "card_id": "card_prompt_review",
    "task_id": "task_prompt_review",
    "task_type": "code_review",
    "approval_level": "light",
    "workflow_id": "workflow_prompt_review",
    "title": "Prompt Review",
    "mode": "reactive",
    "triggers": ["manual", "cli"],
    "execution_policy": {
        "dry_run_default": False,
        "approval_required_for_shell": True,
        "allowed_shell_commands": [["python", "-m", "pytest"]],
        "allowed_cwd_roots": ["."],
        "timeout_seconds": 30,
    },
    "steps": [
        {"step_id": "step_read", "role": "planner", "command": "note"},
        {"step_id": "step_review", "role": "reviewer", "command": "note", "requires_confirmation": True},
    ],
    "notification_policy": {"default_level": "normal", "default_channel": "local"},
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="workflow_scheduler", description="SP-E workflow scheduler and notifier")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate-card")
    validate.add_argument("--card", required=True, type=Path)
    validate.set_defaults(func=_cmd_validate)
    run = sub.add_parser("run")
    run.add_argument("--card", required=True, type=Path)
    run.add_argument("--state", type=Path)
    run.add_argument("--ledger", type=Path)
    run.add_argument("--notify-log", type=Path)
    run.add_argument("--cwd", type=Path, default=Path("."))
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--run-id")
    run.set_defaults(func=_cmd_run)
    notify = sub.add_parser("notify")
    notify.add_argument("--message", required=True)
    notify.add_argument("--level", required=True)
    notify.add_argument("--channel", default="local")
    notify.add_argument("--events", type=Path, default=Path("workflow_scheduler_notify.jsonl"))
    notify.set_defaults(func=_cmd_notify)
    schedule = sub.add_parser("dry-run-schedule")
    schedule.add_argument("--card", required=True, type=Path)
    schedule.add_argument("--now-epoch", type=int, default=None)
    schedule.set_defaults(func=_cmd_schedule)
    show = sub.add_parser("show-config-example")
    show.set_defaults(func=_cmd_show)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (WorkflowSchedulerError, ValueError, OSError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, sort_keys=True, separators=(",", ":")), file=sys.stderr)
        return 2


def _cmd_validate(args: argparse.Namespace) -> int:
    card = load_card(args.card)
    _print({"ok": True, "workflow_id": card.workflow_id, "mode": card.mode, "steps": len(card.steps)})
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    card = load_card(args.card)
    ledger = args.ledger if args.ledger is not None else args.card.with_suffix(".runs.jsonl")
    scheduler = WorkflowScheduler(
        ledger_path=ledger,
        state_path=args.state,
        notify_log_path=args.notify_log,
        execution_policy=replace(card.execution_policy, allowed_cwd_roots=(str(args.cwd),)),
    )
    result = scheduler.run_card(card, dry_run=bool(args.dry_run), cwd=args.cwd, run_id=args.run_id)
    _print(
        {
            "ok": result.status in {"completed", "blocked"},
            "run_id": result.run_id,
            "workflow_id": result.workflow_id,
            "status": result.status,
            "dry_run": result.dry_run,
            "events_written": result.events_written,
            "state_updated": result.state_updated,
        }
    )
    return 0 if result.status in {"completed", "blocked"} else 1


def _cmd_notify(args: argparse.Namespace) -> int:
    result = OutboundNotifier(event_log_path=args.events).send(args.message, level=args.level, channel=args.channel, refs={})
    if isinstance(result, dict):
        _print({"ok": True, **result})
    else:
        _print({"ok": True, "level": result.level, "channel": result.channel, "delivery": result.delivery, "reason": result.reason})
    return 0


def _cmd_schedule(args: argparse.Namespace) -> int:
    card = load_card(args.card)
    now = int(args.now_epoch if args.now_epoch is not None else time.time())
    due = dry_run_schedule(card, now_epoch=now, previous_due_keys=set())
    _print({"ok": True, "due": [item.__dict__ for item in due]})
    return 0


def _cmd_show(args: argparse.Namespace) -> int:
    print(json.dumps(EXAMPLE_CARD, indent=2, ensure_ascii=False))
    return 0


def _print(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))

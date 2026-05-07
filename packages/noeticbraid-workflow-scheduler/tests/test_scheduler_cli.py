from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from noeticbraid.tools.workflow_scheduler.cards import parse_card
from noeticbraid.tools.workflow_scheduler.scheduler import WorkflowScheduler, dry_run_schedule


def valid_card(requires_confirmation=False, **overrides):
    card = {
        "card_id": "card_prompt_review",
        "task_id": "task_prompt_review",
        "task_type": "code_review",
        "approval_level": "light",
        "workflow_id": "workflow_prompt_review",
        "title": "Prompt Review",
        "mode": "reactive",
        "triggers": ["manual", "cli"],
        "steps": [
            {"step_id": "step_read", "role": "planner", "command": "note"},
            {"step_id": "step_review", "role": "reviewer", "command": "note", "requires_confirmation": requires_confirmation},
        ],
        "notification_policy": {"default_level": "normal", "default_channel": "local"},
    }
    card.update(overrides)
    return card


def test_scheduler_reactive_run_writes_ledger_and_state(tmp_path):
    ledger = tmp_path / "runs.jsonl"
    notify = tmp_path / "notify.jsonl"
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"phase": "1.2", "modules": {}}), encoding="utf-8")
    scheduler = WorkflowScheduler(ledger_path=ledger, state_path=state, notify_log_path=notify, allowed_cwd_roots=[tmp_path])

    result = scheduler.run_card(parse_card(valid_card()), dry_run=False, cwd=tmp_path)

    assert result.status == "completed"
    assert result.state_updated is True
    records = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    assert records[0]["event_type"] == "run_pending"
    assert records[-1]["event_type"] == "run_finished"
    assert records[-1]["status"] == "completed"
    assert json.loads(state.read_text(encoding="utf-8"))["modules"]["workflow_scheduler"]["last_status"] == "completed"


def test_scheduler_blocks_on_confirmation_and_notifies(tmp_path):
    scheduler = WorkflowScheduler(ledger_path=tmp_path / "runs.jsonl", notify_log_path=tmp_path / "notify.jsonl", allowed_cwd_roots=[tmp_path])

    result = scheduler.run_card(parse_card(valid_card(requires_confirmation=True)), dry_run=True, cwd=tmp_path)

    assert result.status == "blocked"
    notify_text = (tmp_path / "notify.jsonl").read_text(encoding="utf-8")
    assert "requires_confirmation" in notify_text


def test_scheduler_run_id_is_idempotent(tmp_path):
    ledger = tmp_path / "runs.jsonl"
    scheduler = WorkflowScheduler(ledger_path=ledger, notify_log_path=tmp_path / "notify.jsonl", allowed_cwd_roots=[tmp_path])
    card = parse_card(valid_card())

    first = scheduler.run_card(card, dry_run=True, cwd=tmp_path, run_id="run_fixed")
    lines_after_first = ledger.read_text(encoding="utf-8").splitlines()
    second = scheduler.run_card(card, dry_run=True, cwd=tmp_path, run_id="run_fixed")

    assert first.run_id == second.run_id == "run_fixed"
    assert second.status == first.status
    assert second.events_written == 0
    assert ledger.read_text(encoding="utf-8").splitlines() == lines_after_first


def test_scheduler_emits_security_violation_and_run_failed_for_denied_shell(tmp_path):
    card = parse_card(
        valid_card(
            execution_policy={
                "approval_required_for_shell": False,
                "allowed_shell_commands": [["python", "-m", "pytest"]],
                "allowed_cwd_roots": [str(tmp_path)],
                "timeout_seconds": 5,
            },
            steps=[
                {
                    "step_id": "step_shell",
                    "role": "coder",
                    "command": "shell",
                    "argv": [sys.executable, "-m", "pytest", "--rootdir=/etc"],
                }
            ],
        )
    )
    scheduler = WorkflowScheduler(
        ledger_path=tmp_path / "runs.jsonl",
        notify_log_path=tmp_path / "notify.jsonl",
        execution_policy=card.execution_policy,
    )

    result = scheduler.run_card(card, dry_run=True, cwd=tmp_path)
    records = [json.loads(line) for line in (tmp_path / "runs.jsonl").read_text(encoding="utf-8").splitlines()]

    assert result.status == "failed"
    assert [record["event_type"] for record in records][-2:] == ["security_violation", "run_failed"]
    assert records[-2]["runrecord_event_type"] == "security_violation"
    assert records[-1]["runrecord_event_type"] == "task_failed"


def test_autonomous_schedule_dry_run_is_idempotent():
    card = parse_card({
        "card_id": "card_scheduled",
        "task_id": "task_scheduled",
        "task_type": "project_planning",
        "approval_level": "light",
        "workflow_id": "workflow_scheduled",
        "title": "Scheduled",
        "mode": "autonomous",
        "triggers": ["schedule"],
        "autonomous": {"enabled": True, "dry_run": True, "approval_level": "light"},
        "schedule_rules": [{"rule_id": "schedule_minute", "kind": "interval", "every_seconds": 60}],
        "steps": [{"step_id": "step_note", "role": "planner", "command": "note"}],
    })

    first = dry_run_schedule(card, now_epoch=120, previous_due_keys=set())
    second = dry_run_schedule(card, now_epoch=120, previous_due_keys={first[0].due_key})

    assert len(first) == 1
    assert first[0].rule_id == "schedule_minute"
    assert second == []


def run_cli(root: Path, *args: str):
    import os
    env = os.environ.copy()
    src = str(root / "src")
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = src + os.pathsep + existing if existing else src
    return subprocess.run([sys.executable, "-m", "noeticbraid.tools.workflow_scheduler", *args], cwd=root, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def test_cli_validate_run_notify_and_show_config(tmp_path):
    root = Path(__file__).resolve().parents[1]
    card_path = tmp_path / "card.json"
    card_path.write_text(json.dumps(valid_card()), encoding="utf-8")
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps({"phase": "1.2"}), encoding="utf-8")
    ledger_path = tmp_path / "runs.jsonl"

    validated = run_cli(root, "validate-card", "--card", str(card_path))
    assert validated.returncode == 0, validated.stderr
    assert json.loads(validated.stdout)["ok"] is True

    ran = run_cli(root, "run", "--card", str(card_path), "--state", str(state_path), "--ledger", str(ledger_path), "--dry-run")
    assert ran.returncode == 0, ran.stderr
    assert json.loads(ran.stdout)["status"] == "completed"

    notified = run_cli(root, "notify", "--message", "hello", "--level", "normal", "--events", str(tmp_path / "notify.jsonl"))
    assert notified.returncode == 0, notified.stderr
    assert json.loads(notified.stdout)["delivery"] == "local_record"

    shown = run_cli(root, "show-config-example")
    assert shown.returncode == 0, shown.stderr
    assert "workflow_id" in shown.stdout

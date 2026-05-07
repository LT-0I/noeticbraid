from __future__ import annotations

import json
from pathlib import Path

import pytest

from noeticbraid.tools.workflow_scheduler.cards import (
    SUPPORTED_MODES,
    SUPPORTED_TRIGGERS,
    WorkflowCardError,
    parse_card,
)


def valid_card(**overrides):
    card = {
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
            "timeout_seconds": 5,
        },
        "steps": [
            {"step_id": "step_read", "role": "planner", "command": "note"},
            {"step_id": "step_review", "role": "reviewer", "command": "note", "requires_confirmation": True},
        ],
        "notification_policy": {"default_level": "normal", "default_channel": "local"},
    }
    card.update(overrides)
    return card


def test_supported_modes_and_triggers_include_blueprint_values():
    assert SUPPORTED_MODES == ("reactive", "autonomous")
    assert SUPPORTED_TRIGGERS == ("manual", "cli", "task_file", "schedule")


def test_parse_reactive_card_with_execution_policy():
    parsed = parse_card(valid_card())

    assert parsed.workflow_id == "workflow_prompt_review"
    assert parsed.card_id == "card_prompt_review"
    assert parsed.task_id == "task_prompt_review"
    assert parsed.task_type == "code_review"
    assert parsed.approval_level == "light"
    assert parsed.mode == "reactive"
    assert parsed.triggers == ("manual", "cli")
    assert parsed.execution_policy.approval_required_for_shell is True
    assert parsed.execution_policy.allowed_shell_commands == (("python", "-m", "pytest"),)
    assert [step.step_id for step in parsed.steps] == ["step_read", "step_review"]
    assert parsed.steps[1].requires_confirmation is True


def test_parse_rejects_duplicate_steps_and_hidden_shell_fields():
    duplicate = valid_card(steps=[{"step_id": "step_same", "role": "planner", "command": "note"}, {"step_id": "step_same", "role": "reviewer", "command": "note"}])
    with pytest.raises(WorkflowCardError, match="duplicate step"):
        parse_card(duplicate)

    hidden_shell = valid_card(steps=[{"step_id": "step_bad", "role": "coder", "command": "note", "script": "echo secret"}])
    with pytest.raises(WorkflowCardError, match="shell execution fields"):
        parse_card(hidden_shell)


def test_autonomous_card_requires_schedule_and_dry_run():
    no_schedule = valid_card(mode="autonomous", triggers=["schedule"], autonomous={"enabled": True, "dry_run": True, "approval_level": "light"})
    with pytest.raises(WorkflowCardError, match="schedule_rules"):
        parse_card(no_schedule)

    not_dry_run = valid_card(
            mode="autonomous",
            triggers=["schedule"],
            autonomous={"enabled": True, "dry_run": False, "approval_level": "light"},
            schedule_rules=[{"rule_id": "schedule_daily", "kind": "interval", "every_seconds": 60}],
        )
    with pytest.raises(WorkflowCardError, match="dry-run"):
        parse_card(not_dry_run)

    parsed = parse_card(
        valid_card(
            mode="autonomous",
            triggers=["schedule"],
            autonomous={"enabled": True, "dry_run": True, "approval_level": "light"},
            schedule_rules=[{"rule_id": "schedule_daily", "kind": "interval", "every_seconds": 60}],
        )
    )
    assert parsed.mode == "autonomous"
    assert parsed.autonomous_enabled is True
    assert parsed.schedule_rules[0].every_seconds == 60


def test_autonomous_card_requires_light_or_strong_approval_level():
    forbidden = valid_card(
        mode="autonomous",
        triggers=["schedule"],
        autonomous={"enabled": True, "dry_run": True, "approval_level": "forbidden"},
        schedule_rules=[{"rule_id": "schedule_daily", "kind": "interval", "every_seconds": 60}],
    )
    with pytest.raises(WorkflowCardError, match="approval_level"):
        parse_card(forbidden)

    none = valid_card(
        mode="autonomous",
        triggers=["schedule"],
        autonomous={"enabled": True, "dry_run": True, "approval_level": "none"},
        schedule_rules=[{"rule_id": "schedule_daily", "kind": "interval", "every_seconds": 60}],
    )
    with pytest.raises(WorkflowCardError, match="approval_level"):
        parse_card(none)


def test_workflow_card_schema_is_strict_and_uses_frozen_task_enums():
    root = Path(__file__).resolve().parents[1]
    schema = json.loads((root / "src" / "noeticbraid" / "tools" / "workflow_scheduler" / "schemas" / "workflow_card.schema.json").read_text(encoding="utf-8"))

    assert schema["additionalProperties"] is False
    assert schema["properties"]["task_type"]["enum"] == ["project_planning", "research", "code_review"]
    assert schema["properties"]["approval_level"]["enum"] == ["none", "light", "strong", "forbidden"]
    assert {"card_id", "task_id", "task_type", "approval_level", "workflow_id", "mode", "triggers", "steps"} <= set(schema["required"])
    with pytest.raises(WorkflowCardError, match="task_type"):
        parse_card(valid_card(task_type="primary"))
    with pytest.raises(WorkflowCardError, match="approval_level"):
        parse_card(valid_card(approval_level="urgent"))


def test_challenge_note_type_falls_back_to_human_required_gate():
    parsed = parse_card(valid_card(steps=[{"step_id": "step_challenge", "role": "reviewer", "command": "note", "note_type": "challenge"}]))

    assert parsed.steps[0].note_type == "challenge"
    assert parsed.steps[0].requires_confirmation is True
    assert parsed.steps[0].gate_policy == "human_required"

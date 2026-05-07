"""Workflow card parser and module-local runtime schemas."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Tuple

from .errors import WorkflowCardError

SUPPORTED_STATES: Tuple[str, ...] = ("pending", "running", "blocked", "completed", "failed")
SUPPORTED_MODES: Tuple[str, ...] = ("reactive", "autonomous")
SUPPORTED_TRIGGERS: Tuple[str, ...] = ("manual", "cli", "task_file", "schedule")
SUPPORTED_STEP_COMMANDS: Tuple[str, ...] = ("note", "shell")
FROZEN_TASK_TYPES: Tuple[str, ...] = ("project_planning", "research", "code_review")
FROZEN_APPROVAL_LEVELS: Tuple[str, ...] = ("none", "light", "strong", "forbidden")
ALLOWED_ROLES: Tuple[str, ...] = (
    "orchestrator",
    "planner",
    "researcher",
    "producer",
    "writer",
    "coder",
    "reviewer",
    "adversary",
    "source_auditor",
    "verifier",
    "convergence_editor",
    "human_decision",
)
ALLOWED_GATE_POLICIES: Tuple[str, ...] = ("none", "dual_review", "multi_review", "human_required")
ALLOWED_NOTE_TYPES: Tuple[str, ...] = ("info", "decision", "challenge", "memory_candidate")

_STABLE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
_PREFIX_RE = {
    "card_id": re.compile(r"^card_[A-Za-z0-9_]+$"),
    "task_id": re.compile(r"^task_[A-Za-z0-9_]+$"),
    "workflow_id": re.compile(r"^workflow_[A-Za-z0-9_]+$"),
    "step_id": re.compile(r"^step_[A-Za-z0-9_]+$"),
    "schedule_id": re.compile(r"^schedule_[A-Za-z0-9_]+$"),
    "rule_id": re.compile(r"^schedule_[A-Za-z0-9_]+$"),
}
_FORBIDDEN_STEP_FIELDS = frozenset({"args", "cmd", "env", "executable", "powershell", "run", "script", "subprocess"})
_ALLOWED_ROOT_FIELDS = frozenset(
    {
        "card_id",
        "task_id",
        "task_type",
        "approval_level",
        "workflow_id",
        "title",
        "name",
        "mode",
        "triggers",
        "execution_policy",
        "steps",
        "notification_policy",
        "autonomous",
        "schedule_rules",
    }
)


@dataclass(frozen=True)
class ExecutionPolicy:
    dry_run_default: bool = False
    approval_required_for_shell: bool = True
    allowed_shell_commands: Tuple[Tuple[str, ...], ...] = ()
    allowed_cwd_roots: Tuple[str, ...] = (".",)
    timeout_seconds: int = 30


@dataclass(frozen=True)
class ScheduleRule:
    rule_id: str
    kind: str
    every_seconds: int
    enabled: bool = True


@dataclass(frozen=True)
class AutonomousConfig:
    enabled: bool = False
    dry_run: bool = True
    approval_level: str = "forbidden"
    schedule: str | None = None
    schedule_rules: Tuple[ScheduleRule, ...] = ()


@dataclass(frozen=True)
class WorkflowStep:
    step_id: str
    role: str
    command: str = "note"
    argv: Tuple[str, ...] = ()
    retry_once: bool = False
    requires_confirmation: bool = False
    gate_policy: str = "none"
    note_type: str = "info"

    @property
    def id(self) -> str:
        return self.step_id


@dataclass(frozen=True)
class WorkflowCard:
    card_id: str
    task_id: str
    task_type: str
    approval_level: str
    workflow_id: str
    title: str
    mode: str
    triggers: Tuple[str, ...]
    steps: Tuple[WorkflowStep, ...]
    notification_policy: Mapping[str, Any] = field(default_factory=dict)
    execution_policy: ExecutionPolicy = field(default_factory=ExecutionPolicy)
    schedule_rules: Tuple[ScheduleRule, ...] = ()
    autonomous: AutonomousConfig = field(default_factory=AutonomousConfig)
    autonomous_enabled: bool = False


def load_card(path: Path) -> WorkflowCard:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise WorkflowCardError("workflow card could not be read") from exc
    except json.JSONDecodeError as exc:
        raise WorkflowCardError("workflow card must be valid JSON") from exc
    return parse_card(payload)


def parse_card(payload: Mapping[str, Any]) -> WorkflowCard:
    if not isinstance(payload, Mapping):
        raise WorkflowCardError("workflow card root must be a JSON object")
    unknown = sorted(set(payload.keys()) - _ALLOWED_ROOT_FIELDS)
    if unknown:
        raise WorkflowCardError(f"unsupported workflow card fields: {', '.join(unknown)}")
    card_id = _required_prefixed_id(payload, "card_id")
    task_id = _required_prefixed_id(payload, "task_id")
    task_type = _required_enum(payload, "task_type", FROZEN_TASK_TYPES)
    approval_level = _required_enum(payload, "approval_level", FROZEN_APPROVAL_LEVELS)
    workflow_id = _required_prefixed_id(payload, "workflow_id")
    title = _optional_text(payload.get("title", payload.get("name")), workflow_id, "title")
    mode = payload.get("mode")
    if mode not in SUPPORTED_MODES:
        raise WorkflowCardError("workflow card mode must be reactive or autonomous")
    triggers = _validate_triggers(payload.get("triggers"))
    policy = _validate_execution_policy(payload.get("execution_policy") or {})
    steps = tuple(_validate_steps(payload.get("steps")))
    notification_policy = payload.get("notification_policy") or {"default_level": "silent_record", "default_channel": "local"}
    if not isinstance(notification_policy, Mapping):
        raise WorkflowCardError("notification_policy must be an object")
    schedule_rules = tuple(_validate_schedule_rules(payload.get("schedule_rules") or []))
    autonomous = _parse_autonomous(payload.get("autonomous") or {}, schedule_rules=schedule_rules)
    if mode == "autonomous":
        if not autonomous.enabled:
            raise WorkflowCardError("autonomous mode requires autonomous.enabled=true")
        if "schedule" not in triggers:
            raise WorkflowCardError("autonomous mode requires schedule trigger")
        if not schedule_rules:
            raise WorkflowCardError("autonomous mode requires schedule_rules")
        if not autonomous.dry_run:
            raise WorkflowCardError("autonomous execution is dry-run only in this package")
    return WorkflowCard(
        card_id=card_id,
        task_id=task_id,
        task_type=task_type,
        approval_level=approval_level,
        workflow_id=workflow_id,
        title=title,
        mode=str(mode),
        triggers=triggers,
        steps=steps,
        notification_policy=dict(notification_policy),
        execution_policy=policy,
        schedule_rules=schedule_rules,
        autonomous=autonomous,
        autonomous_enabled=autonomous.enabled,
    )


def _required_prefixed_id(payload: Mapping[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise WorkflowCardError(f"missing required stable id: {field_name}")
    value = value.strip()
    pattern = _PREFIX_RE.get(field_name)
    if pattern is not None and not pattern.fullmatch(value):
        raise WorkflowCardError(f"{field_name} must match required prefix")
    if not _STABLE_ID_RE.fullmatch(value):
        raise WorkflowCardError(f"{field_name} must be a stable id")
    return value


def _required_enum(payload: Mapping[str, Any], field_name: str, allowed: Tuple[str, ...]) -> str:
    value = payload.get(field_name)
    if value not in allowed:
        raise WorkflowCardError(f"{field_name} must be one of {', '.join(allowed)}")
    return str(value)


def _optional_text(value: Any, fallback: str, field_name: str) -> str:
    if value is None:
        return fallback
    if not isinstance(value, str) or not value.strip():
        raise WorkflowCardError(f"{field_name} must be a non-empty string")
    return value.strip()


def _validate_triggers(value: Any) -> Tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise WorkflowCardError("triggers must be a non-empty list")
    result: list[str] = []
    for item in value:
        if item not in SUPPORTED_TRIGGERS:
            raise WorkflowCardError("unsupported trigger")
        if item not in result:
            result.append(str(item))
    return tuple(result)


def _parse_autonomous(raw: Any, *, schedule_rules: Tuple[ScheduleRule, ...]) -> AutonomousConfig:
    if not raw:
        return AutonomousConfig(schedule_rules=schedule_rules)
    if not isinstance(raw, Mapping):
        raise WorkflowCardError("autonomous must be an object")
    enabled = bool(raw.get("enabled", False))
    approval = str(raw.get("approval_level", "forbidden"))
    if approval not in FROZEN_APPROVAL_LEVELS:
        raise WorkflowCardError(f"autonomous.approval_level must be frozen Task enum (got {approval!r})")
    if enabled and approval not in {"light", "strong"}:
        raise WorkflowCardError(f"autonomous mode requires approval_level in {{light, strong}} (got {approval!r})")
    dry_run = bool(raw.get("dry_run", True))
    schedule = raw.get("schedule")
    if schedule is not None and not isinstance(schedule, str):
        raise WorkflowCardError("autonomous.schedule must be a string when provided")
    return AutonomousConfig(
        enabled=enabled,
        dry_run=dry_run,
        approval_level=approval,
        schedule=schedule,
        schedule_rules=schedule_rules,
    )


def _validate_execution_policy(value: Mapping[str, Any]) -> ExecutionPolicy:
    if not isinstance(value, Mapping):
        raise WorkflowCardError("execution_policy must be an object")
    commands = value.get("allowed_shell_commands", [])
    if not isinstance(commands, list):
        raise WorkflowCardError("allowed_shell_commands must be a list")
    normalized_commands: list[Tuple[str, ...]] = []
    for command in commands:
        if not isinstance(command, list) or not command or not all(isinstance(part, str) and part for part in command):
            raise WorkflowCardError("allowed_shell_commands entries must be non-empty string lists")
        normalized_commands.append(tuple(command))
    roots = value.get("allowed_cwd_roots", ["."])
    if not isinstance(roots, list) or not roots or not all(isinstance(root, str) and root for root in roots):
        raise WorkflowCardError("allowed_cwd_roots must be a non-empty string list")
    timeout = int(value.get("timeout_seconds", 30))
    if timeout < 1 or timeout > 600:
        raise WorkflowCardError("timeout_seconds must be between 1 and 600")
    return ExecutionPolicy(
        dry_run_default=bool(value.get("dry_run_default", False)),
        approval_required_for_shell=bool(value.get("approval_required_for_shell", True)),
        allowed_shell_commands=tuple(normalized_commands),
        allowed_cwd_roots=tuple(roots),
        timeout_seconds=timeout,
    )


def _validate_schedule_rules(value: Any) -> list[ScheduleRule]:
    if not value:
        return []
    if not isinstance(value, list):
        raise WorkflowCardError("schedule_rules must be a list")
    result = []
    seen: set[str] = set()
    for raw in value:
        if not isinstance(raw, Mapping):
            raise WorkflowCardError("schedule rule must be an object")
        field = "schedule_id" if "schedule_id" in raw else "rule_id"
        rule_id = _required_prefixed_id(raw, field)
        if rule_id in seen:
            raise WorkflowCardError("duplicate schedule rule")
        seen.add(rule_id)
        if raw.get("kind") != "interval":
            raise WorkflowCardError("only interval schedule rules are supported")
        every = int(raw.get("every_seconds", 0))
        if every < 1 or every > 86400:
            raise WorkflowCardError("every_seconds must be between 1 and 86400")
        result.append(ScheduleRule(rule_id=rule_id, kind="interval", every_seconds=every, enabled=bool(raw.get("enabled", True))))
    return result


def _validate_steps(value: Any) -> list[WorkflowStep]:
    if not isinstance(value, list) or not value:
        raise WorkflowCardError("steps must be a non-empty list")
    result = []
    seen: set[str] = set()
    for index, raw in enumerate(value):
        if not isinstance(raw, Mapping):
            raise WorkflowCardError(f"step {index} must be an object")
        forbidden = sorted(_FORBIDDEN_STEP_FIELDS.intersection(raw.keys()))
        if forbidden:
            raise WorkflowCardError("step schema must not contain shell execution fields")
        step_id = raw.get("step_id", raw.get("id"))
        if not isinstance(step_id, str):
            raise WorkflowCardError("step_id is required")
        step_id = step_id.strip()
        if not _PREFIX_RE["step_id"].fullmatch(step_id):
            raise WorkflowCardError("step_id must match step_*")
        if step_id in seen:
            raise WorkflowCardError(f"duplicate step id: {step_id}")
        seen.add(step_id)
        role = raw.get("role")
        if role not in ALLOWED_ROLES:
            raise WorkflowCardError(f"step {step_id} role is unsupported")
        command = raw.get("command", "note")
        if command not in SUPPORTED_STEP_COMMANDS:
            raise WorkflowCardError("unsupported step command")
        argv_raw = raw.get("argv", [])
        if argv_raw is None:
            argv_raw = []
        if not isinstance(argv_raw, list) or not all(isinstance(part, str) and part for part in argv_raw):
            raise WorkflowCardError("argv must be a string list")
        retry_once = raw.get("retry_once", False)
        if not isinstance(retry_once, bool):
            raise WorkflowCardError("retry_once must be boolean")
        requires_confirmation = raw.get("requires_confirmation", False)
        if not isinstance(requires_confirmation, bool):
            raise WorkflowCardError("requires_confirmation must be boolean")
        gate_policy = raw.get("gate_policy", "none")
        if gate_policy not in ALLOWED_GATE_POLICIES:
            raise WorkflowCardError("unsupported gate_policy")
        note_type = raw.get("note_type", "info")
        if note_type not in ALLOWED_NOTE_TYPES:
            raise WorkflowCardError("unsupported note_type")
        if note_type == "challenge":
            requires_confirmation = True
            gate_policy = "human_required"
        result.append(
            WorkflowStep(
                step_id=step_id,
                role=str(role),
                command=str(command),
                argv=tuple(argv_raw),
                retry_once=retry_once,
                requires_confirmation=requires_confirmation,
                gate_policy=str(gate_policy),
                note_type=str(note_type),
            )
        )
    return result


parse_workflow_card = parse_card

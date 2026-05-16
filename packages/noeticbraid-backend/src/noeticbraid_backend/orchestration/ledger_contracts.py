# SPDX-License-Identifier: Apache-2.0
"""Team ledger contracts ported from oh-my-claudecode team contracts."""

from __future__ import annotations

import re
from typing import Literal

TEAM_NAME_SAFE_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,29}$")
WORKER_NAME_SAFE_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
TASK_ID_SAFE_RE = re.compile(r"^\d{1,20}$")

TeamTaskStatus = Literal["pending", "blocked", "in_progress", "completed", "failed"]
TeamDispatchRequestKind = Literal["inbox", "mailbox", "nudge"]
TeamDispatchRequestStatus = Literal["pending", "notified", "delivered", "failed"]
TeamDispatchTransportPreference = Literal[
    "hook_preferred_with_fallback",
    "transport_direct",
    "prompt_stdin",
]
TeamTaskApprovalStatus = Literal["pending", "approved", "rejected"]
TeamEventType = Literal[
    "task_completed",
    "task_failed",
    "worker_idle",
    "worker_stopped",
    "message_received",
    "shutdown_ack",
    "shutdown_gate",
    "shutdown_gate_forced",
    "approval_decision",
    "team_leader_nudge",
]

TEAM_TASK_STATUSES: tuple[TeamTaskStatus, ...] = (
    "pending",
    "blocked",
    "in_progress",
    "completed",
    "failed",
)
TEAM_TERMINAL_TASK_STATUSES: frozenset[TeamTaskStatus] = frozenset(
    {"completed", "failed"}
)
TEAM_TASK_STATUS_TRANSITIONS: dict[TeamTaskStatus, tuple[TeamTaskStatus, ...]] = {
    "pending": (),
    "blocked": (),
    "in_progress": ("completed", "failed"),
    "completed": (),
    "failed": (),
}
TEAM_EVENT_TYPES: tuple[TeamEventType, ...] = (
    "task_completed",
    "task_failed",
    "worker_idle",
    "worker_stopped",
    "message_received",
    "shutdown_ack",
    "shutdown_gate",
    "shutdown_gate_forced",
    "approval_decision",
    "team_leader_nudge",
)
TEAM_TASK_APPROVAL_STATUSES: tuple[TeamTaskApprovalStatus, ...] = (
    "pending",
    "approved",
    "rejected",
)
TEAM_DISPATCH_REQUEST_KINDS: tuple[TeamDispatchRequestKind, ...] = (
    "inbox",
    "mailbox",
    "nudge",
)
TEAM_DISPATCH_REQUEST_STATUSES: tuple[TeamDispatchRequestStatus, ...] = (
    "pending",
    "notified",
    "delivered",
    "failed",
)
TEAM_DISPATCH_TRANSPORT_PREFERENCES: tuple[TeamDispatchTransportPreference, ...] = (
    "hook_preferred_with_fallback",
    "transport_direct",
    "prompt_stdin",
)


def is_terminal_team_task_status(status: TeamTaskStatus) -> bool:
    """Return true for terminal statuses (`completed`, `failed`)."""

    return status in TEAM_TERMINAL_TASK_STATUSES


def can_transition_team_task_status(
    from_status: TeamTaskStatus,
    to_status: TeamTaskStatus,
) -> bool:
    """Return whether a team task status transition is allowed."""

    return to_status in TEAM_TASK_STATUS_TRANSITIONS.get(from_status, ())


def is_safe_team_name(value: str) -> bool:
    """Match upstream TEAM_NAME_SAFE_PATTERN."""

    return TEAM_NAME_SAFE_RE.fullmatch(value) is not None


def is_safe_worker_name(value: str) -> bool:
    """Match upstream WORKER_NAME_SAFE_PATTERN."""

    return WORKER_NAME_SAFE_RE.fullmatch(value) is not None


def is_safe_task_id(value: str) -> bool:
    """Match upstream TASK_ID_SAFE_PATTERN."""

    return TASK_ID_SAFE_RE.fullmatch(value) is not None


def is_dispatch_status(value: str) -> bool:
    """Return true for known dispatch request statuses."""

    return value in TEAM_DISPATCH_REQUEST_STATUSES


def is_dispatch_kind(value: str) -> bool:
    """Return true for known dispatch request kinds."""

    return value in TEAM_DISPATCH_REQUEST_KINDS


__all__ = [
    "TASK_ID_SAFE_RE",
    "TEAM_DISPATCH_REQUEST_KINDS",
    "TEAM_DISPATCH_REQUEST_STATUSES",
    "TEAM_DISPATCH_TRANSPORT_PREFERENCES",
    "TEAM_EVENT_TYPES",
    "TEAM_NAME_SAFE_RE",
    "TEAM_TASK_APPROVAL_STATUSES",
    "TEAM_TASK_STATUSES",
    "TEAM_TASK_STATUS_TRANSITIONS",
    "TEAM_TERMINAL_TASK_STATUSES",
    "WORKER_NAME_SAFE_RE",
    "TeamDispatchRequestKind",
    "TeamDispatchRequestStatus",
    "TeamDispatchTransportPreference",
    "TeamEventType",
    "TeamTaskApprovalStatus",
    "TeamTaskStatus",
    "can_transition_team_task_status",
    "is_dispatch_kind",
    "is_dispatch_status",
    "is_safe_task_id",
    "is_safe_team_name",
    "is_safe_worker_name",
    "is_terminal_team_task_status",
]

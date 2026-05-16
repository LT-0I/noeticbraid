# SPDX-License-Identifier: Apache-2.0
# ruff: noqa: E402
"""C2 ledger replay reconstructs final task state and rejects corrupt order."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parent.parent
SRC_ROOT = PACKAGE_ROOT / "src"
CORE_SRC_ROOT = REPO_ROOT / "packages" / "noeticbraid-core" / "src"
for path in (CORE_SRC_ROOT, SRC_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import pytest

from noeticbraid_backend.platform.ledger.events import LedgerEvent, LedgerEventType, dispatch_event, event_to_json_line
from noeticbraid_backend.platform.ledger.writer import (
    IllegalLedgerTransition,
    MalformedLedger,
    append_event,
    ledger_path_for,
    replay,
)
from noeticbraid_backend.platform.tasks.models import TaskState, account_ref_for


def test_replay_reconstructs_delivered_state_from_synthetic_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(tmp_path / "platform-data"))
    account = "beta_user_05"
    task_id = "task_replay_ok"
    transitions = [
        TaskState.CREATED,
        TaskState.PLANNING,
        TaskState.DISPATCHING,
        TaskState.PRODUCING,
        TaskState.CROSS_VALIDATING,
        TaskState.DELIVERED,
    ]

    previous: TaskState | None = None
    for state in transitions:
        append_event(account, dispatch_event(task_id, from_state=previous, to_state=state))
        previous = state

    assert replay(task_id, account=account) is TaskState.DELIVERED
    assert replay(task_id) is TaskState.DELIVERED


def test_replay_rejects_out_of_order_seq(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(tmp_path / "platform-data"))
    account = "beta_user_01"
    task_id = "task_bad_order"
    path = ledger_path_for(account, task_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        LedgerEvent(
            ts="2026-05-16T00:00:01+00:00",
            task_id=task_id,
            account_id_ref=account_ref_for(account),
            seq=2,
            type=LedgerEventType.DISPATCH,
            payload={"to_state": "created"},
        ),
        LedgerEvent(
            ts="2026-05-16T00:00:02+00:00",
            task_id=task_id,
            account_id_ref=account_ref_for(account),
            seq=1,
            type=LedgerEventType.DISPATCH,
            payload={"from_state": "created", "to_state": "planning"},
        ),
    ]
    path.write_text("\n".join(event_to_json_line(row) for row in rows) + "\n", encoding="utf-8")

    with pytest.raises(MalformedLedger):
        replay(task_id, account=account)


def test_replay_rejects_illegal_state_jump(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(tmp_path / "platform-data"))
    account = "beta_user_02"
    task_id = "task_bad_jump"
    path = ledger_path_for(account, task_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "ts": "2026-05-16T00:00:01+00:00",
            "task_id": task_id,
            "account_id_ref": account_ref_for(account),
            "seq": 1,
            "type": "dispatch",
            "payload": {"to_state": "created"},
        },
        {
            "ts": "2026-05-16T00:00:02+00:00",
            "task_id": task_id,
            "account_id_ref": account_ref_for(account),
            "seq": 2,
            "type": "dispatch",
            "payload": {"from_state": "created", "to_state": "delivered"},
        },
    ]
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")

    with pytest.raises(IllegalLedgerTransition):
        replay(task_id, account=account)

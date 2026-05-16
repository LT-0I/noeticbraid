# SPDX-License-Identifier: Apache-2.0
# ruff: noqa: E402
"""C2 task store persists task metadata and lifecycle evidence privately."""

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

from noeticbraid_backend.platform.ledger.writer import ledger_path_for, replay
from noeticbraid_backend.platform.tasks.models import TaskState, account_ref_for
from noeticbraid_backend.platform.tasks.store import (
    IllegalTaskTransition,
    create_task,
    list_tasks,
    load_task,
    task_path_for,
    update_task,
    update_task_state,
)


def test_task_store_crud_and_private_task_json(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data_root = tmp_path / "platform-data"
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(data_root))
    account = "beta_user_01"

    task = create_task(
        account,
        task_id="task_alpha",
        title="Summarize safely",
        modality_targets=["text"],
        created_ts="2026-05-16T00:00:00+00:00",
    )

    assert task.state is TaskState.CREATED
    assert task.account_id_ref == account_ref_for(account)
    assert load_task(account, "task_alpha") == task
    assert list_tasks(account) == (task,)

    stored = json.loads(task_path_for(account, "task_alpha").read_text(encoding="utf-8"))
    assert stored["account_id_ref"] == account_ref_for(account)
    assert account not in json.dumps(stored, sort_keys=True)

    updated = update_task(account, "task_alpha", title="New title", modality_targets=["text", "image"])
    assert updated.title == "New title"
    assert updated.modality_targets == ["text", "image"]


def test_task_store_validates_transitions_and_ledgers_illegal_errors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(tmp_path / "platform-data"))
    account = "beta_user_02"
    create_task(account, task_id="task_lifecycle", title="Lifecycle", modality_targets=["text"])

    assert replay("task_lifecycle", account=account) is TaskState.CREATED
    assert update_task_state(account, "task_lifecycle", TaskState.PLANNING).state is TaskState.PLANNING
    assert update_task_state(account, "task_lifecycle", TaskState.DISPATCHING).state is TaskState.DISPATCHING

    with pytest.raises(IllegalTaskTransition):
        update_task_state(account, "task_lifecycle", TaskState.DELIVERED)

    rows = [json.loads(line) for line in ledger_path_for(account, "task_lifecycle").read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["type"] == "error"
    assert rows[-1]["payload"]["to_state"] == "error"
    assert load_task(account, "task_lifecycle").state is TaskState.DISPATCHING
    assert replay("task_lifecycle", account=account) is TaskState.ERROR


def test_task_ids_reuse_hub_shape(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(tmp_path / "platform-data"))

    with pytest.raises(ValueError):
        create_task("beta_user_03", task_id="bad-task", title="Bad", modality_targets=[])

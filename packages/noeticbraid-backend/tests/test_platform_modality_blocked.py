# SPDX-License-Identifier: Apache-2.0
# ruff: noqa: E402
"""C6 unreachable modality handling must block without fake artifacts."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parent.parent
SRC_ROOT = PACKAGE_ROOT / "src"
CORE_SRC_ROOT = REPO_ROOT / "packages" / "noeticbraid-core" / "src"
for path in (CORE_SRC_ROOT, SRC_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import pytest

from noeticbraid_backend.platform.ledger.writer import ledger_path_for
from noeticbraid_backend.platform.orchestration import hub_adapter
from noeticbraid_backend.platform.orchestration.dispatcher import Dispatcher, Event
from noeticbraid_backend.platform.tasks.models import TaskState
from noeticbraid_backend.platform.tasks.store import create_task, load_task
from noeticbraid_backend.platform.workspace_paths import resolve_user_path


def _collect(dispatcher: Dispatcher, task) -> list[Event]:
    async def run() -> list[Event]:
        return [event async for event in dispatcher.run(task)]

    return asyncio.run(run())


def _ledger_rows(account: str, task_id: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in ledger_path_for(account, task_id).read_text(encoding="utf-8").splitlines()]


@pytest.mark.parametrize("modality", ["image", "video", "music", "spreadsheet"])
def test_unmapped_or_unreachable_modality_blocks_and_writes_zero_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    modality: str,
) -> None:
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(tmp_path / "platform-data"))
    account = "beta_user_03"
    task_id = f"task_blocked_{modality}"
    task = create_task(account, task_id=task_id, title="Blocked", modality_targets=[modality])
    monkeypatch.setattr(hub_adapter, "dispatch", lambda *_args, **_kwargs: pytest.fail("dispatch must not run"))

    events = _collect(Dispatcher(account=account, user_text="make it"), task)

    blocked_frames = [event for event in events if event.type == "blocked"]
    assert len(blocked_frames) == 1
    assert blocked_frames[0].payload["modality"] == modality
    assert not any(event.type == "artifact" for event in events)
    assert load_task(account, task_id).state is TaskState.BLOCKED

    artifacts_dir = resolve_user_path(account, f"tasks/{task_id}/artifacts")
    assert not artifacts_dir.exists() or list(artifacts_dir.iterdir()) == []
    rows = _ledger_rows(account, task_id)
    assert any(row["type"] == "dispatch" and row["payload"].get("to_state") == "blocked" for row in rows)
    assert not any(row["type"] == "artifact_produced" for row in rows)

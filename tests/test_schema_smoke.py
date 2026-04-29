"""Top-level smoke test for Stage 1 candidate schema imports and round trip."""

from __future__ import annotations

import sys
from pathlib import Path

CORE_SRC = Path(__file__).resolve().parents[1] / "packages" / "noeticbraid-core" / "src"
if str(CORE_SRC) not in sys.path:
    sys.path.insert(0, str(CORE_SRC))


def test_imports():
    from noeticbraid_core.schemas import (  # noqa: F401
        ApprovalRequest,
        DigestionItem,
        RunRecord,
        SideNote,
        SourceRecord,
        Task,
    )


def test_task_minimal_round_trip():
    from noeticbraid_core.schemas import Task

    task = Task(
        task_id="task_smoke",
        task_type="research",
        risk_level="low",
        approval_level="none",
        user_request="smoke test",
        source_channel="local",
    )
    assert task.is_terminal() is False
    assert Task.model_validate_json(task.model_dump_json()) == task

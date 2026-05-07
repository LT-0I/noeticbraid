"""Scoped atomic state updates for SP-E."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping

from .cards import SUPPORTED_STATES
from .errors import StateStoreError

MODULE_NAME = "workflow_scheduler"
MODULE_STEP = "implemented"


def load_state(path: Path) -> dict[str, Any]:
    try:
        state = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise StateStoreError("state file could not be read") from exc
    except json.JSONDecodeError as exc:
        raise StateStoreError("state file must be valid JSON") from exc
    if not isinstance(state, dict):
        raise StateStoreError("state file root must be an object")
    return state


def update_scheduler_module_state(path: Path, *, run_id: str, status: str) -> dict[str, Any]:
    if status not in SUPPORTED_STATES:
        raise StateStoreError("unsupported scheduler status")
    if not isinstance(run_id, str) or not run_id:
        raise StateStoreError("run_id is required")
    state = load_state(path)
    modules_raw = state.get("modules")
    if modules_raw is None:
        modules: dict[str, Any] = {}
    elif isinstance(modules_raw, dict):
        modules = dict(modules_raw)
    else:
        raise StateStoreError("state.modules must be an object")
    modules[MODULE_NAME] = {"step": MODULE_STEP, "last_run_id": run_id, "last_status": status}
    state["modules"] = modules
    _write_json_atomic(Path(path), state)
    return state


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path = Path(path)
    tmp_name = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=str(path.parent),
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            tmp_name = handle.name
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except Exception as exc:
        if tmp_name:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
        raise StateStoreError("state file could not be written atomically") from exc

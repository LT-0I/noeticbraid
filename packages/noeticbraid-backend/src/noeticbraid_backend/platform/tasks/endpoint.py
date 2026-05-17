# SPDX-License-Identifier: Apache-2.0
"""Authenticated platform task read endpoints."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status

from noeticbraid_backend.platform.artifacts.ledger import _artifact_events, _ledger_rows
from noeticbraid_backend.platform.auth import require_platform_bearer
from noeticbraid_backend.platform.tasks import store as task_store
from noeticbraid_backend.platform.tasks.models import Task, account_ref_for


def register_platform_task_routes(platform_app: FastAPI) -> None:
    """Register platform task read routes on the mounted sub-app."""

    @platform_app.get("/tasks", summary="List platform tasks")
    async def platform_list_tasks(request: Request) -> dict[str, list[dict[str, Any]]]:
        account = require_platform_bearer(request.headers.get("authorization"))
        try:
            tasks = [_serialize_task(task) for task in _owned_tasks(account)]
        except Exception as exc:
            raise _not_found() from exc
        return {"tasks": tasks}

    @platform_app.get("/tasks/{task_id}", summary="Read a platform task")
    async def platform_read_task(request: Request, task_id: str) -> dict[str, Any]:
        account = require_platform_bearer(request.headers.get("authorization"))
        try:
            task = task_store.load_task(account, task_id)
            if task.account_id_ref != account_ref_for(account):
                raise ValueError("task/account binding mismatch")
            ledger = [_serialize_ledger_row(row) for row in _ledger_rows(account, task.task_id)]
            artifacts = [_serialize_artifact(task.task_id, payload) for payload in _artifact_events(account, task.task_id)]
        except Exception as exc:
            raise _not_found() from exc
        return {"task": _serialize_task(task), "ledger": ledger, "artifacts": artifacts}


def _owned_tasks(account: str) -> tuple[Task, ...]:
    expected_ref = account_ref_for(account)
    tasks: list[Task] = []
    for task in _list_tasks_tolerant(account):
        try:
            if task.account_id_ref != expected_ref:
                continue
            tasks.append(task)
        except Exception:
            continue
    return tuple(tasks)


def _list_tasks_tolerant(account: str) -> tuple[Task, ...]:
    try:
        return tuple(task_store.list_tasks(account))
    except task_store.MalformedTask:
        return _list_tasks_individually(account)


def _list_tasks_individually(account: str) -> tuple[Task, ...]:
    root = task_store.resolve_user_path(account, "tasks")
    if not root.exists():
        return ()
    tasks: list[Task] = []
    for task_json_path in sorted(root.glob(f"*/{task_store.TASK_FILENAME}")):
        try:
            tasks.append(task_store.load_task(account, task_json_path.parent.name))
        except Exception:
            continue
    return tuple(tasks)


def _serialize_task(task: Task) -> dict[str, Any]:
    return {
        "task_id": task.task_id,
        "title": task.title,
        "state": task.state.value,
        "created_ts": task.created_ts,
        "updated_ts": task.updated_ts,
        "modality_targets": list(task.modality_targets),
    }


def _serialize_ledger_row(row: dict[str, Any]) -> dict[str, Any]:
    payload = row.get("payload")
    state = payload.get("to_state") if isinstance(payload, dict) and "to_state" in payload else None
    return {
        "event_type": row.get("type"),
        "state": state,
        "created_at": row.get("ts"),
    }


def _serialize_artifact(task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    rel_path = str(payload["rel_path"])
    return {
        "modality": str(payload["modality"]),
        "rel_path": rel_path,
        "sha256": str(payload["sha256"]),
        "bytes": int(payload["bytes"]),
        "download_url": f"/platform/tasks/{task_id}/artifacts/{Path(rel_path).stem}",
    }


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")


__all__ = ["register_platform_task_routes"]

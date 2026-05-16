# SPDX-License-Identifier: Apache-2.0
# ruff: noqa: E402
"""Focused C3 WebSocket endpoint hardening tests."""

from __future__ import annotations

import asyncio
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
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from noeticbraid_backend.app import create_app
from noeticbraid_backend.auth.token_store import TokenStore
from noeticbraid_backend.platform.orchestration.dispatcher import Event
from noeticbraid_backend.platform.tasks.models import Task
from noeticbraid_backend.platform.tasks.store import create_task
from noeticbraid_backend.platform.ws import endpoint as ws_endpoint
from noeticbraid_backend.settings import Settings


def _client_for_task(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    account: str,
    task_id: str,
) -> tuple[TestClient, str]:
    data_root = tmp_path / "platform-data"
    monkeypatch.setenv("NOETICBRAID_PLATFORM_ENABLED", "1")
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(data_root))
    token = TokenStore(data_root).create_token(account)
    create_task(account, task_id=task_id, title="WS hardening", modality_targets=["text"])
    app = create_app(Settings(state_dir=tmp_path / "state"))
    return TestClient(app), token


def test_ws_uses_fresh_unset_cancel_event_for_each_user_message(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(ws_endpoint, "MIN_MESSAGE_INTERVAL_SECONDS", 0.0)
    seen: list[asyncio.Event] = []

    class RecordingDispatcher:
        def __init__(
            self,
            *,
            account: str,
            user_text: str,
            cancel_event: asyncio.Event | None = None,
        ) -> None:
            assert account == "beta_user_01"
            assert user_text in {"first", "second"}
            assert cancel_event is not None
            assert not cancel_event.is_set()
            seen.append(cancel_event)

        async def run(self, task: Task):
            yield Event("progress", task.task_id, {"message": "delivered", "step": 1, "total": 1})

    monkeypatch.setattr(ws_endpoint, "Dispatcher", RecordingDispatcher)
    client, token = _client_for_task(
        monkeypatch,
        tmp_path,
        account="beta_user_01",
        task_id="task_ws_cancel_fresh",
    )

    with client.websocket_connect("/platform/ws/tasks/task_ws_cancel_fresh") as websocket:
        websocket.send_json({"type": "auth", "token": token})
        for text in ("first", "second"):
            websocket.send_json({"type": "user_message", "task_id": "task_ws_cancel_fresh", "text": text})
            assert websocket.receive_json() == {
                "type": "progress",
                "task_id": "task_ws_cancel_fresh",
                "message": "delivered",
                "step": 1,
                "total": 1,
            }

    assert len(seen) == 2
    assert seen[0] is not seen[1]
    assert [event.is_set() for event in seen] == [False, False]


def test_ws_closes_1008_after_max_messages_per_connection(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(ws_endpoint, "MIN_MESSAGE_INTERVAL_SECONDS", 0.0)

    class FastDispatcher:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        async def run(self, task: Task):
            yield Event("progress", task.task_id, {"message": "delivered", "step": 1, "total": 1})

    monkeypatch.setattr(ws_endpoint, "Dispatcher", FastDispatcher)
    client, token = _client_for_task(
        monkeypatch,
        tmp_path,
        account="beta_user_02",
        task_id="task_ws_message_bound",
    )

    with client.websocket_connect("/platform/ws/tasks/task_ws_message_bound") as websocket:
        websocket.send_json({"type": "auth", "token": token})
        for index in range(ws_endpoint.MAX_MESSAGES_PER_CONNECTION):
            websocket.send_json(
                {
                    "type": "user_message",
                    "task_id": "task_ws_message_bound",
                    "text": f"message {index}",
                }
            )
            assert websocket.receive_json()["type"] == "progress"

        websocket.send_json(
            {
                "type": "user_message",
                "task_id": "task_ws_message_bound",
                "text": "one too many",
            }
        )
        blocked = websocket.receive_json()
        assert blocked == {
            "type": "blocked",
            "task_id": "task_ws_message_bound",
            "modality": "task",
            "reason": f"connection message limit exceeded ({ws_endpoint.MAX_MESSAGES_PER_CONNECTION})",
        }
        with pytest.raises(WebSocketDisconnect) as exc_info:
            websocket.receive_json()

    assert exc_info.value.code == 1008

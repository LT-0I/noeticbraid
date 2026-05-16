# SPDX-License-Identifier: Apache-2.0
"""Mounted platform WebSocket endpoint for task chat."""

from __future__ import annotations

import asyncio
import time

from fastapi import FastAPI, HTTPException, WebSocket
from starlette.websockets import WebSocketDisconnect

from noeticbraid_backend.platform.auth import require_platform_bearer
from noeticbraid_backend.platform.orchestration.dispatcher import Dispatcher
from noeticbraid_backend.platform.tasks.models import account_ref_for, validate_task_id
from noeticbraid_backend.platform.tasks.store import TaskNotFound, load_task
from noeticbraid_backend.platform.ws.protocol import (
    AuthClientFrame,
    ProtocolError,
    UserMessageClientFrame,
    parse_client_frame,
    validate_server_frame,
)

MAX_MESSAGES_PER_CONNECTION = 64
MIN_MESSAGE_INTERVAL_SECONDS = 0.5


def register_platform_ws_routes(platform_app: FastAPI) -> None:
    """Register mounted-sub-app WebSocket routes."""

    @platform_app.websocket("/ws/tasks/{task_id}")
    async def platform_task_ws(websocket: WebSocket, task_id: str) -> None:
        await _handle_task_ws(websocket, task_id)


async def _handle_task_ws(websocket: WebSocket, task_id: str) -> None:
    try:
        task_key = validate_task_id(task_id)
    except ValueError:
        await websocket.close(code=1008)
        return

    if websocket.query_params or websocket.headers.get("sec-websocket-protocol"):
        await websocket.close(code=1008)
        return

    await websocket.accept()
    cancel_event: asyncio.Event | None = None
    message_count = 0
    last_message_at: float | None = None
    try:
        first = await _receive_frame(websocket)
        if not isinstance(first, AuthClientFrame):
            await websocket.close(code=1008)
            return
        try:
            account = require_platform_bearer(f"Bearer {first.token}")
        except HTTPException:
            await websocket.close(code=1008)
            return
        try:
            task = load_task(account, task_key)
        except (TaskNotFound, ValueError):
            await websocket.close(code=1008)
            return
        if task.account_id_ref != account_ref_for(account):
            await websocket.close(code=1008)
            return

        while True:
            frame = await _receive_frame(websocket)
            if not isinstance(frame, UserMessageClientFrame):
                await websocket.close(code=1008)
                return
            if frame.task_id != task_key:
                await websocket.send_json(
                    validate_server_frame(
                        {
                            "type": "error",
                            "task_id": task_key,
                            "code": "task_mismatch",
                            "reason": "message task does not match connection task",
                        }
                    )
                )
                await websocket.close(code=1008)
                return
            if message_count >= MAX_MESSAGES_PER_CONNECTION:
                await _blocked_policy_close(
                    websocket,
                    task_key,
                    reason=f"connection message limit exceeded ({MAX_MESSAGES_PER_CONNECTION})",
                )
                return
            now = time.monotonic()
            if last_message_at is not None and now - last_message_at < MIN_MESSAGE_INTERVAL_SECONDS:
                await _blocked_policy_close(
                    websocket,
                    task_key,
                    reason=f"message rate limit exceeded ({MIN_MESSAGE_INTERVAL_SECONDS:.1f}s minimum interval)",
                )
                return
            message_count += 1
            last_message_at = now

            cancel_event = asyncio.Event()
            dispatcher = Dispatcher(account=account, user_text=frame.text, cancel_event=cancel_event)
            async for event in dispatcher.run(load_task(account, task_key)):
                await websocket.send_json(validate_server_frame(event.to_frame()))
            cancel_event = None
    except WebSocketDisconnect:
        if cancel_event is not None:
            cancel_event.set()
    except ProtocolError as exc:
        await websocket.close(code=exc.close_code)
    finally:
        if cancel_event is not None:
            cancel_event.set()


async def _receive_frame(websocket: WebSocket) -> AuthClientFrame | UserMessageClientFrame:
    raw = await websocket.receive_text()
    return parse_client_frame(raw)


async def _blocked_policy_close(websocket: WebSocket, task_id: str, *, reason: str) -> None:
    await websocket.send_json(
        validate_server_frame(
            {
                "type": "blocked",
                "task_id": task_id,
                "modality": "task",
                "reason": reason,
            }
        )
    )
    await websocket.close(code=1008, reason=reason)


__all__ = ["register_platform_ws_routes"]

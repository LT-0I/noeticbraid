# SPDX-License-Identifier: Apache-2.0
# ruff: noqa: E402
"""C3 WebSocket streaming and ledger redaction boundary tests."""

from __future__ import annotations

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
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from noeticbraid_backend.app import create_app
from noeticbraid_backend.auth.token_store import TokenStore
from noeticbraid_backend.platform.ledger.writer import ledger_path_for
from noeticbraid_backend.platform.orchestration import hub_adapter
from noeticbraid_backend.platform.tasks.store import create_task
from noeticbraid_backend.settings import Settings


def test_ws_ai_delta_and_ledger_are_redacted(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "platform-data"
    monkeypatch.setenv("NOETICBRAID_PLATFORM_ENABLED", "1")
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(data_root))
    account = "beta_user_05"
    token = TokenStore(data_root).create_token(account)
    create_task(account, task_id="task_ws_redact", title="Redact", modality_targets=["text"])
    secret = "sk-test_abcdefghijklmnop"

    def fake_dispatch(_op: str, _params: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
        return {
            "outcome": "ok",
            "status": "ok",
            "payload": {"ok": True, "status": "ok", "response_text": f"synthetic secret {secret}"},
        }

    monkeypatch.setattr(hub_adapter, "dispatch", fake_dispatch)
    app = create_app(Settings(state_dir=tmp_path / "state"))
    client = TestClient(app)

    frames: list[dict[str, Any]] = []
    with client.websocket_connect("/platform/ws/tasks/task_ws_redact") as websocket:
        websocket.send_json({"type": "auth", "token": token})
        websocket.send_json({"type": "user_message", "task_id": "task_ws_redact", "text": "return a secret"})
        for _ in range(20):
            frame = websocket.receive_json()
            frames.append(frame)
            if frame.get("type") == "progress" and frame.get("message") == "delivered":
                break

    rendered_frames = json.dumps(frames, sort_keys=True)
    rendered_ledger = ledger_path_for(account, "task_ws_redact").read_text(encoding="utf-8")
    assert secret not in rendered_frames
    assert secret not in rendered_ledger
    assert token not in rendered_frames
    assert token not in rendered_ledger
    ai_frames = [frame for frame in frames if frame["type"] == "ai_delta"]
    assert ai_frames[0]["payload"]["response_text"] == "synthetic secret [redacted]"
    ledger_frames = [frame for frame in frames if frame["type"] == "ledger" and frame["event"]["type"] == "ai_call"]
    assert ledger_frames[0]["event"]["payload"]["redacted_payload"]["response_text"] == "synthetic secret [redacted]"


def test_ws_rejects_query_token_auth_and_keeps_token_out_of_ledger(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "platform-data"
    monkeypatch.setenv("NOETICBRAID_PLATFORM_ENABLED", "1")
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(data_root))
    account = "beta_user_04"
    token = TokenStore(data_root).create_token(account)
    create_task(account, task_id="task_ws_query", title="Reject query", modality_targets=["text"])
    app = create_app(Settings(state_dir=tmp_path / "state"))
    client = TestClient(app)

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/platform/ws/tasks/task_ws_query?token={token}"):
            pass

    rendered_ledger = ledger_path_for(account, "task_ws_query").read_text(encoding="utf-8")
    assert token not in rendered_ledger

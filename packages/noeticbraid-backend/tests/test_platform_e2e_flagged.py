# SPDX-License-Identifier: Apache-2.0
# ruff: noqa: E402
"""C6 flag-on platform E2E and D12 trusted-context wiring tests."""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parent.parent
SRC_ROOT = PACKAGE_ROOT / "src"
CORE_SRC_ROOT = REPO_ROOT / "packages" / "noeticbraid-core" / "src"
for path in (CORE_SRC_ROOT, SRC_ROOT, REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import pytest
from fastapi.testclient import TestClient

from noeticbraid_backend.app import create_app
from noeticbraid_backend.auth.token_store import TokenStore
from noeticbraid_backend.platform.ledger.writer import ledger_path_for, replay
from noeticbraid_backend.platform.orchestration import hub_adapter
from noeticbraid_backend.platform.orchestration.dispatcher import Dispatcher, PlanStep
from noeticbraid_backend.platform.tasks.models import TaskState
from noeticbraid_backend.platform.tasks.store import create_task, load_task
from noeticbraid_backend.platform.workspace_paths import resolve_user_path
from noeticbraid_backend.settings import Settings

_GATE_PATH = REPO_ROOT / "scripts" / "check_phase1_2_contract_gate.py"
_SPEC = importlib.util.spec_from_file_location("check_phase1_2_contract_gate", _GATE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
contract_gate = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = contract_gate
_SPEC.loader.exec_module(contract_gate)
FROZEN_SIDECAR_SHA256 = "96ce4bac5e3c9f1c976e21bc68d32ff2ba02c5ef9fe16bb8189eb3fbfbf839b7"


def _ledger_rows(account: str, task_id: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in ledger_path_for(account, task_id).read_text(encoding="utf-8").splitlines()]


def _receive_until_terminal(websocket) -> list[dict[str, Any]]:
    frames: list[dict[str, Any]] = []
    for _ in range(100):
        frame = websocket.receive_json()
        frames.append(frame)
        if frame.get("type") == "blocked":
            return frames
        if frame.get("type") == "progress" and frame.get("message") == "delivered":
            return frames
    raise AssertionError("terminal platform frame not received")


def _requested_modality(params: dict[str, Any]) -> str:
    prompt = str(params.get("prompt") or "")
    marker = "Requested modality: "
    assert marker in prompt
    return prompt.split(marker, 1)[1].split("\n", 1)[0].strip()


def test_flagged_platform_e2e_delivers_mapped_artifacts_blocks_unmapped_and_contract_gate_passes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "platform-data"
    monkeypatch.setenv("NOETICBRAID_PLATFORM_ENABLED", "1")
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(data_root))
    monkeypatch.setattr("noeticbraid_backend.platform.ws.endpoint.MIN_MESSAGE_INTERVAL_SECONDS", 0.0)
    account = "beta_user_04"
    token = TokenStore(data_root).create_token(account)
    delivered_task = create_task(
        account,
        task_id="task_e2e_deliver",
        title="Deliver mapped modalities",
        modality_targets=["text", "document", "slides", "poster"],
    )
    blocked_task = create_task(
        account,
        task_id="task_e2e_blocked",
        title="Block unmapped modality",
        modality_targets=["image"],
    )
    calls: list[tuple[str, dict[str, Any], dict[str, str | None]]] = []

    def fake_dispatch(op: str, params: dict[str, Any], *, account: str | None = None, task_id: str | None = None) -> dict[str, Any]:
        assert account == "beta_user_04"
        assert task_id == delivered_task.task_id
        modality = _requested_modality(params)
        rel_path = f"tasks/{task_id}/artifacts/{modality}-hub.md"
        content = f"{modality} artifact\n".encode("utf-8")
        artifact_path = resolve_user_path(account, rel_path)
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_bytes(content)
        calls.append((op, params, {"account": account, "task_id": task_id}))
        return {
            "outcome": "ok",
            "status": "ok",
            "payload": {
                "ok": True,
                "status": "ok",
                "path": rel_path,
                "sha256": hashlib.sha256(content).hexdigest(),
                "size_bytes": len(content),
            },
        }

    monkeypatch.setattr(hub_adapter, "dispatch", fake_dispatch)
    client = TestClient(create_app(Settings(state_dir=tmp_path / "state")))

    with client.websocket_connect(f"/platform/ws/tasks/{delivered_task.task_id}") as websocket:
        websocket.send_json({"type": "auth", "token": token})
        websocket.send_json({"type": "user_message", "task_id": delivered_task.task_id, "text": "deliver all mapped"})
        delivered_frames = _receive_until_terminal(websocket)

    assert calls and len(calls) == 4
    assert load_task(account, delivered_task.task_id).state is TaskState.DELIVERED
    assert replay(delivered_task.task_id, account=account) is TaskState.DELIVERED
    delivered_rows = _ledger_rows(account, delivered_task.task_id)
    delivered_ledger_frames = [frame["event"] for frame in delivered_frames if frame.get("type") == "ledger"]
    assert delivered_ledger_frames == delivered_rows[1:]
    artifact_rows = [row for row in delivered_rows if row["type"] == "artifact_produced"]
    assert [row["payload"]["modality"] for row in artifact_rows] == ["text", "document", "slides", "poster"]
    for row in artifact_rows:
        assert resolve_user_path(account, row["payload"]["rel_path"]).is_file()

    with client.websocket_connect(f"/platform/ws/tasks/{blocked_task.task_id}") as websocket:
        websocket.send_json({"type": "auth", "token": token})
        websocket.send_json({"type": "user_message", "task_id": blocked_task.task_id, "text": "make an image"})
        blocked_frames = _receive_until_terminal(websocket)

    assert blocked_frames[-1]["type"] == "blocked"
    assert blocked_frames[-1]["modality"] == "image"
    assert load_task(account, blocked_task.task_id).state is TaskState.BLOCKED
    assert replay(blocked_task.task_id, account=account) is TaskState.BLOCKED
    assert not resolve_user_path(account, f"tasks/{blocked_task.task_id}/artifacts").exists()

    report = contract_gate.run_checks(REPO_ROOT)
    assert report.sidecar_sha256 == FROZEN_SIDECAR_SHA256
    assert report.contract_sha256 == FROZEN_SIDECAR_SHA256


@pytest.mark.parametrize(
    ("op", "modality", "extension"),
    [
        ("webai_chatgpt_generate_image", "image", "png"),
        ("webai_gemini_generate_video", "video", "mp4"),
    ],
)
def test_d12_trusted_context_wiring_allows_governed_image_video_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    op: str,
    modality: str,
    extension: str,
) -> None:
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(tmp_path / "platform-data"))
    account = "beta_user_05"
    task_id = f"task_d12_{modality}_context"
    task = create_task(account, task_id=task_id, title="D12", modality_targets=[modality])
    calls: list[dict[str, Any]] = []

    def fake_dispatch_web_ai(
        operation: str,
        params: dict[str, Any],
        *,
        account: str | None = None,
        task_id: str | None = None,
    ) -> dict[str, Any]:
        calls.append({"operation": operation, "params": dict(params), "account": account, "task_id": task_id})
        if account is None or task_id is None:
            return {"status": "not_implemented", "reason": "artifact path governance violation"}
        basename = f"{modality}-hub.{extension}"
        rel_path = f"tasks/{task_id}/artifacts/{basename}"
        content = f"{modality} governed bytes\n".encode("utf-8")
        artifact_path = resolve_user_path(account, rel_path)
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_bytes(content)
        return {
            "ok": True,
            "status": "ok",
            "path": rel_path,
            "sha256": hashlib.sha256(content).hexdigest(),
            "size_bytes": len(content),
        }

    monkeypatch.setattr(hub_adapter._automation, "dispatch_web_ai", fake_dispatch_web_ai)

    without_context = hub_adapter.dispatch(op, {"profile": "p", "prompt": "make"})
    assert without_context["outcome"] == "blocked"
    assert without_context["status"] == "not_implemented"
    assert without_context["reason"] == "artifact path governance violation"

    step = PlanStep(
        modality=modality,
        op=op,
        vendor="hub",
        params_template={"profile": "p", "prompt": "make", "reuse_conversation": False},
        prompt_text="make",
        artifact_extension=extension,
    )
    dispatcher = Dispatcher(account=account, user_text="make")
    with_context = asyncio.run(dispatcher._dispatch_step(step, task_id=task_id))
    assert with_context["outcome"] == "ok"
    produced = dispatcher._write_artifact(task, step, with_context["payload"], index=1)

    basename = f"{modality}-hub.{extension}"
    assert calls[-1]["account"] == account
    assert calls[-1]["task_id"] == task_id
    assert produced.type.value == "artifact_produced"
    assert produced.payload["modality"] == modality
    assert produced.payload["rel_path"] == f"tasks/{task_id}/artifacts/{basename}"
    assert resolve_user_path(account, produced.payload["rel_path"]).is_file()

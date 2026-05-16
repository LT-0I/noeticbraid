# SPDX-License-Identifier: Apache-2.0
# ruff: noqa: E402
"""C3 platform dispatcher sequencing, ledger parity, cancel, and bound tests."""

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
from noeticbraid_backend.platform.orchestration.modality_map import ModalityRoute, resolve_modality
from noeticbraid_backend.platform.tasks.models import TaskState
from noeticbraid_backend.platform.tasks.store import create_task, load_task


def _collect(dispatcher: Dispatcher, task) -> list[Event]:
    async def run() -> list[Event]:
        return [event async for event in dispatcher.run(task)]

    return asyncio.run(run())


def _ledger_rows(account: str, task_id: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in ledger_path_for(account, task_id).read_text(encoding="utf-8").splitlines()]


def test_dispatcher_sequences_hub_call_artifact_and_ledger_parity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(tmp_path / "platform-data"))
    account = "beta_user_01"
    task = create_task(account, task_id="task_dispatch", title="Draft safely", modality_targets=["text"])
    calls: list[tuple[str, dict[str, Any], dict[str, Any]]] = []

    def fake_dispatch(op: str, params: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        calls.append((op, params, kwargs))
        return {"outcome": "ok", "status": "ok", "payload": {"ok": True, "response_text": "safe draft"}}

    monkeypatch.setattr(hub_adapter, "dispatch", fake_dispatch)

    events = _collect(Dispatcher(account=account, user_text="write a safe draft"), task)

    assert calls and calls[0][0] == "webai_chatgpt_send_prompt"
    assert calls[0][1]["profile"] == "chatgpt"
    assert calls[0][2] == {"account": account, "task_id": "task_dispatch"}
    assert [event.type for event in events].count("ai_delta") == 1
    assert [event.type for event in events].count("artifact") == 1
    assert events[-1].payload["message"] == "delivered"
    assert load_task(account, "task_dispatch").state is TaskState.DELIVERED

    rows = _ledger_rows(account, "task_dispatch")
    sent_ledger_frames = [event for event in events if event.type == "ledger"]
    assert len(rows[1:]) == len(sent_ledger_frames)
    assert [row["seq"] for row in rows] == list(range(1, len(rows) + 1))
    assert any(row["type"] == "ai_call" for row in rows)
    assert any(row["type"] == "artifact_produced" for row in rows)


def test_dispatcher_builds_exact_params_per_route_param_kind(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(tmp_path / "platform-data"))
    account = "beta_user_07"
    dispatcher = Dispatcher(account=account, user_text="make the requested artifact")

    text_task = create_task(account, task_id="task_text_params", title="Text params", modality_targets=["text"])
    text_route = resolve_modality("text")
    assert isinstance(text_route, ModalityRoute)
    text_step = dispatcher._step_from_route(text_task, text_route, context="")
    assert text_step.params_template == {
        "profile": "chatgpt",
        "prompt": text_step.prompt_text,
        "reuse_conversation": False,
    }

    image_task = create_task(account, task_id="task_image_params", title="Image params", modality_targets=["image"])
    image_route = resolve_modality("image")
    assert isinstance(image_route, ModalityRoute)
    image_step = dispatcher._step_from_route(image_task, image_route, context="")
    assert image_step.params_template == {"profile": "chatgpt", "prompt": image_step.prompt_text}


def test_dispatcher_cancel_token_blocks_before_dispatch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(tmp_path / "platform-data"))
    account = "beta_user_02"
    task = create_task(account, task_id="task_cancel", title="Cancel", modality_targets=["text"])
    cancel = asyncio.Event()
    cancel.set()

    monkeypatch.setattr(hub_adapter, "dispatch", lambda *_args, **_kwargs: pytest.fail("dispatch must not run"))

    events = _collect(Dispatcher(account=account, user_text="cancel", cancel_event=cancel), task)

    assert [event.type for event in events] == ["ledger", "blocked"]
    assert events[-1].payload["reason"] == "task dispatch cancelled"
    assert load_task(account, "task_cancel").state is TaskState.BLOCKED


def test_dispatcher_max_step_bound_blocks_without_hub_call(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(tmp_path / "platform-data"))
    account = "beta_user_03"
    task = create_task(
        account,
        task_id="task_bound",
        title="Too many",
        modality_targets=["text", "document"],
    )
    monkeypatch.setattr(hub_adapter, "dispatch", lambda *_args, **_kwargs: pytest.fail("dispatch must not run"))

    events = _collect(Dispatcher(account=account, user_text="two outputs", max_steps=1), task)

    assert events[-1].type == "blocked"
    assert events[-1].payload["reason"] == "plan exceeds max step count 1"
    assert load_task(account, "task_bound").state is TaskState.BLOCKED


def test_dispatcher_music_modality_blocks_without_fake_artifact(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(tmp_path / "platform-data"))
    account = "beta_user_04"
    task = create_task(account, task_id="task_music", title="Music", modality_targets=["music"])
    monkeypatch.setattr(hub_adapter, "dispatch", lambda *_args, **_kwargs: pytest.fail("dispatch must not run"))

    events = _collect(Dispatcher(account=account, user_text="make music"), task)

    assert events[-1].type == "blocked"
    assert events[-1].payload["modality"] == "music"
    assert "posture-甲" in events[-1].payload["reason"]
    assert "no operator --confirmed" in events[-1].payload["reason"]
    assert not any(event.type == "artifact" for event in events)

# SPDX-License-Identifier: Apache-2.0
# ruff: noqa: E402
"""C3 platform dispatcher sequencing, ledger parity, cancel, and bound tests."""

from __future__ import annotations

import asyncio
import hashlib
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

from noeticbraid_backend.omc_workspace import web_ai_hub_automation as automation
from noeticbraid_backend.omc_workspace import web_ai_hub_compat as compat
from noeticbraid_backend.platform.ledger.writer import ledger_path_for
from noeticbraid_backend.platform.orchestration import dispatcher as dispatcher_module
from noeticbraid_backend.platform.orchestration import hub_adapter
from noeticbraid_backend.platform.orchestration.dispatcher import Dispatcher, Event
from noeticbraid_backend.platform.orchestration.modality_map import ModalityRoute, resolve_modality
from noeticbraid_backend.platform.tasks.models import TaskState
from noeticbraid_backend.platform.tasks.store import create_task, load_task
from noeticbraid_backend.platform.workspace_paths import resolve_user_path


def _collect(dispatcher: Dispatcher, task) -> list[Event]:
    async def run() -> list[Event]:
        return [event async for event in dispatcher.run(task)]

    return asyncio.run(run())


def _ledger_rows(account: str, task_id: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in ledger_path_for(account, task_id).read_text(encoding="utf-8").splitlines()]


class _FakeCdpResponse:
    status = 200

    def read(self) -> bytes:
        return b'{"Browser":"Chrome"}'

    def close(self) -> None:
        return None


def _write_file(path: Path, content: bytes | str = b"x\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, str):
        path.write_text(content, encoding="utf-8")
    else:
        path.write_bytes(content)
    return path


def _make_hub(root: Path) -> Path:
    hub = root / "hub"
    _write_file(hub / "dist" / "src" / "cli.js", "console.log('cli');\n")
    for dep in compat.ENUMERATED_OFF_DIST_DEPS:
        _write_file(hub / "node_modules" / dep / "package.json", f'{{"name":"{dep}"}}\n')
    return hub


def _pin_hub(monkeypatch: pytest.MonkeyPatch, hub: Path) -> None:
    digest = compat.compute_exec_digest(hub)
    assert isinstance(digest, str)
    assert digest not in {None, "HUB_NOT_BUILT"}
    monkeypatch.setattr(compat, "PINNED_HUB_EXEC_DIGEST", digest)


def _enable_real_hub_envelope_test_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    hub = _make_hub(tmp_path)
    _pin_hub(monkeypatch, hub)
    monkeypatch.setenv(compat.AUTOMATION_ENV, "1")
    monkeypatch.setenv(compat.HUB_PATH_ENV, str(hub))
    monkeypatch.setenv(compat.CDP_HOST_ENV, "127.0.0.1")
    monkeypatch.setenv(compat.CDP_PORT_ENV, "9222")
    monkeypatch.setattr(automation.urllib.request, "urlopen", lambda _url, *, timeout: _FakeCdpResponse())
    return hub


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

    video_task = create_task(account, task_id="task_video_params", title="Video params", modality_targets=["video"])
    video_route = resolve_modality("video")
    assert isinstance(video_route, ModalityRoute)
    assert video_route.param_kind == "generate_async"
    video_step = dispatcher._step_from_route(video_task, video_route, context="")
    assert video_step.params_template == {"profile": "gemini-9225", "prompt": video_step.prompt_text}
    assert video_step.param_kind == "generate_async"


def test_dispatcher_video_async_poll_delivers_nested_real_result(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(tmp_path / "platform-data"))
    _enable_real_hub_envelope_test_env(monkeypatch, tmp_path)
    monkeypatch.setattr(dispatcher_module, "ASYNC_POLL_INTERVAL_SECONDS", 0.0)
    account = "beta_user_video_01"
    task_id = "task_video_async"
    hub_task_id = "task_hub_video_async"
    task = create_task(account, task_id=task_id, title="Video", modality_targets=["video"])
    calls: list[list[str]] = []
    status_calls = 0

    def fake_run(args, **kwargs):
        nonlocal status_calls
        args_list = list(args)
        calls.append(args_list)
        if args_list == ["mcp:tools", "--json"]:
            return {
                "data": [
                    {"name": "webai_gemini_generate_video", "description": "", "inputSchema": {}},
                    {"name": "webai_task_status", "description": "", "inputSchema": {}},
                ]
            }
        if args_list[0] == "webai:gemini:generate-video":
            assert kwargs["timeout"] == compat.automation_timeout_for("webai_gemini_generate_video")
            assert Path(args_list[args_list.index("--download-dir") + 1]) == resolve_user_path(
                account,
                f"tasks/{task_id}/artifacts",
            )
            return {
                "task_id": hub_task_id,
                "status": "running",
                "profile": "gemini-9225",
                "lease_id": "lease_video_01",
                "started_at": "2026-05-16T00:00:00Z",
            }
        if args_list[0] == "webai:task-status":
            assert kwargs["timeout"] == compat.automation_timeout_for("webai_task_status")
            assert args_list == ["webai:task-status", "--task-id", hub_task_id, "--output-json"]
            status_calls += 1
            if status_calls == 1:
                return {"status": "running", "progress_label": "rendering token=secret /home/l1u"}
            content = b"real video bytes\n"
            artifact = _write_file(resolve_user_path(account, f"tasks/{task_id}/artifacts/video-hub.mp4"), content)
            return {
                "status": "done",
                "progress_label": "downloaded",
                "result": {
                    "path": str(artifact),
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "size_bytes": len(content),
                    "download_filename": "/tmp/video-hub.mp4",
                },
            }
        raise AssertionError(f"unexpected hub command: {args_list!r}")

    monkeypatch.setattr(automation, "run_hub_command", fake_run)

    events = _collect(Dispatcher(account=account, user_text="make a video"), task)

    ai_delta = [event.payload for event in events if event.type == "ai_delta"][-1]
    assert ai_delta["status"] == "ok"
    assert ai_delta["path"] == f"tasks/{task_id}/artifacts/video-hub.mp4"
    assert ai_delta["download_filename"] == "video-hub.mp4"
    assert ai_delta["size_bytes"] == len(b"real video bytes\n")
    assert "result" not in ai_delta
    assert str(tmp_path) not in repr(ai_delta)
    assert "/home" not in repr(ai_delta)
    assert not any(event.type == "blocked" for event in events)
    assert [event.type for event in events].count("artifact") == 1
    assert events[-1].payload["message"] == "delivered"
    assert load_task(account, task_id).state is TaskState.DELIVERED
    assert status_calls == 2
    dispatch_commands = [call[0] for call in calls if call != ["mcp:tools", "--json"]]
    assert dispatch_commands == ["webai:gemini:generate-video", "webai:task-status", "webai:task-status"]


def test_dispatcher_video_failed_status_blocks_with_redacted_error_code(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(tmp_path / "platform-data"))
    _enable_real_hub_envelope_test_env(monkeypatch, tmp_path)
    monkeypatch.setattr(dispatcher_module, "ASYNC_POLL_INTERVAL_SECONDS", 0.0)
    account = "beta_user_video_02"
    task = create_task(account, task_id="task_video_failed", title="Video", modality_targets=["video"])
    hub_task_id = "task_hub_failed"

    def fake_run(args, **kwargs):
        args_list = list(args)
        if args_list == ["mcp:tools", "--json"]:
            return {
                "data": [
                    {"name": "webai_gemini_generate_video", "description": "", "inputSchema": {}},
                    {"name": "webai_task_status", "description": "", "inputSchema": {}},
                ]
            }
        if args_list[0] == "webai:gemini:generate-video":
            return {"task_id": hub_task_id, "status": "running", "profile": "gemini-9225"}
        if args_list[0] == "webai:task-status":
            return {
                "status": "failed",
                "errorCode": "COMMAND_TIMEOUT",
                "message": "failed at /home/l1u token=secret",
            }
        raise AssertionError(f"unexpected hub command: {args_list!r}")

    monkeypatch.setattr(automation, "run_hub_command", fake_run)

    events = _collect(Dispatcher(account=account, user_text="make a video"), task)

    assert events[-1].type == "blocked"
    assert events[-1].payload == {
        "modality": "video",
        "reason": "video generation failed: COMMAND_TIMEOUT",
    }
    rendered = repr(events)
    assert "/home" not in rendered
    assert "secret" not in rendered
    assert not any(event.type == "artifact" for event in events)
    assert load_task(account, task.task_id).state is TaskState.BLOCKED


def test_dispatcher_video_cancel_mid_poll_blocks_within_poll_loop(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(tmp_path / "platform-data"))
    _enable_real_hub_envelope_test_env(monkeypatch, tmp_path)
    monkeypatch.setattr(dispatcher_module, "ASYNC_POLL_INTERVAL_SECONDS", 0.0)
    account = "beta_user_video_03"
    task = create_task(account, task_id="task_video_cancel_poll", title="Video", modality_targets=["video"])
    cancel = asyncio.Event()
    hub_task_id = "task_hub_cancel"

    def fake_run(args, **kwargs):
        args_list = list(args)
        if args_list == ["mcp:tools", "--json"]:
            return {
                "data": [
                    {"name": "webai_gemini_generate_video", "description": "", "inputSchema": {}},
                    {"name": "webai_task_status", "description": "", "inputSchema": {}},
                ]
            }
        if args_list[0] == "webai:gemini:generate-video":
            return {"task_id": hub_task_id, "status": "running", "profile": "gemini-9225"}
        if args_list[0] == "webai:task-status":
            cancel.set()
            return {"status": "running", "progress_label": "still running"}
        raise AssertionError(f"unexpected hub command: {args_list!r}")

    monkeypatch.setattr(automation, "run_hub_command", fake_run)

    events = _collect(Dispatcher(account=account, user_text="make a video", cancel_event=cancel), task)

    assert events[-1].type == "blocked"
    assert events[-1].payload["reason"] == "task dispatch cancelled"
    assert not any(event.type == "artifact" for event in events)


def test_dispatcher_video_poll_budget_blocks_without_terminal_status(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(tmp_path / "platform-data"))
    _enable_real_hub_envelope_test_env(monkeypatch, tmp_path)
    monkeypatch.setattr(dispatcher_module, "ASYNC_POLL_INTERVAL_SECONDS", 0.0)
    monkeypatch.setattr(dispatcher_module, "ASYNC_POLL_BUDGET_SECONDS", 0.001)
    account = "beta_user_video_04"
    task = create_task(account, task_id="task_video_budget", title="Video", modality_targets=["video"])
    hub_task_id = "task_hub_budget"

    def fake_run(args, **kwargs):
        args_list = list(args)
        if args_list == ["mcp:tools", "--json"]:
            return {
                "data": [
                    {"name": "webai_gemini_generate_video", "description": "", "inputSchema": {}},
                    {"name": "webai_task_status", "description": "", "inputSchema": {}},
                ]
            }
        if args_list[0] == "webai:gemini:generate-video":
            return {"task_id": hub_task_id, "status": "running", "profile": "gemini-9225"}
        if args_list[0] == "webai:task-status":
            return {"status": "running", "progress_label": "queued"}
        raise AssertionError(f"unexpected hub command: {args_list!r}")

    monkeypatch.setattr(automation, "run_hub_command", fake_run)

    events = _collect(Dispatcher(account=account, user_text="make a video"), task)

    assert events[-1].type == "blocked"
    assert events[-1].payload["reason"] == "video generation exceeded platform poll budget"
    assert not any(event.type == "artifact" for event in events)


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

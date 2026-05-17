# SPDX-License-Identifier: Apache-2.0
# ruff: noqa: E402
"""C8 modality route and blocked handling tests."""

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
from noeticbraid_backend.platform.orchestration.modality_map import ModalityBlocked, ModalityRoute, resolve_modality
from noeticbraid_backend.platform.tasks.models import TaskState
from noeticbraid_backend.platform.tasks.store import create_task, load_task
from noeticbraid_backend.platform.workspace_paths import resolve_user_path


def _collect(dispatcher: Dispatcher, task) -> list[Event]:
    async def run() -> list[Event]:
        return [event async for event in dispatcher.run(task)]

    return asyncio.run(run())


def _ledger_rows(account: str, task_id: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in ledger_path_for(account, task_id).read_text(encoding="utf-8").splitlines()]


def test_resolve_image_video_to_d12_generate_routes() -> None:
    image = resolve_modality("image")
    video = resolve_modality("video")

    assert isinstance(image, ModalityRoute)
    assert image.op == "webai_chatgpt_generate_image"
    assert image.vendor == "chatgpt"
    assert image.profile == "chatgpt"
    assert image.artifact_extension == "png"
    assert image.param_kind == "generate"
    assert "image" in image.prompt_preamble.lower()

    assert isinstance(video, ModalityRoute)
    assert video.op == "webai_gemini_generate_video"
    assert video.vendor == "gemini"
    assert video.profile == "gemini-9225"
    assert video.artifact_extension == "mp4"
    assert video.param_kind == "generate_async"
    assert "video" in video.prompt_preamble.lower()


@pytest.mark.parametrize("modality", ["text", "document", "slides", "poster"])
def test_resolve_textual_modalities_keep_textual_route(modality: str) -> None:
    route = resolve_modality(modality)

    assert isinstance(route, ModalityRoute)
    assert route.op == "webai_chatgpt_send_prompt"
    assert route.vendor == "chatgpt"
    assert route.profile == "chatgpt"
    assert route.artifact_extension == "md"
    assert route.param_kind == "textual"


def test_resolve_music_blocks_with_posture_alpha_reason() -> None:
    blocked = resolve_modality("music")

    assert isinstance(blocked, ModalityBlocked)
    assert blocked.modality == "music"
    assert "posture-甲" in blocked.reason
    assert "no operator --confirmed" in blocked.reason


@pytest.mark.parametrize("modality", ["music", "spreadsheet"])
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

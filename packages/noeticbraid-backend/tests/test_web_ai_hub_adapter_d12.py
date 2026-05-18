# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Any, Callable

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
for path in (
    REPO_ROOT / "packages" / "noeticbraid-core" / "src",
    REPO_ROOT / "packages" / "noeticbraid-backend" / "src",
):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from noeticbraid_backend.omc_workspace import web_ai_hub_automation as automation  # noqa: E402
from noeticbraid_backend.omc_workspace import web_ai_hub_compat as compat  # noqa: E402
from noeticbraid_backend.platform.orchestration import hub_adapter  # noqa: E402


CHATGPT_IMAGE_OP = "webai_chatgpt_generate_image"
GEMINI_IMAGE_OP = "webai_gemini_generate_image"
GEMINI_VIDEO_OP = "webai_gemini_generate_video"
MUSIC_OP = "webai_gemini_music_generate"
ACCOUNT = "beta_user_d12"
TASK_ID = "task_d12_artifact"


class _FakeCdpResponse:
    def __init__(self, *, status: int = 200, body: bytes = b'{"Browser":"Chrome"}') -> None:
        self.status = status
        self._body = body

    def read(self) -> bytes:
        return self._body

    def close(self) -> None:
        return None


def _write_file(path: Path, text: str = "x\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _make_hub(root: Path, *, label: str = "hub") -> Path:
    hub = root / label
    _write_file(hub / "dist" / "src" / "cli.js", "console.log('cli');\n")
    _write_file(hub / "dist" / "z.txt", "z\n")
    for dep in compat.ENUMERATED_OFF_DIST_DEPS:
        _write_file(hub / "node_modules" / dep / "package.json", f'{{"name":"{dep}"}}\n')
        _write_file(hub / "node_modules" / dep / "index.js", f"module.exports = '{dep}';\n")
    return hub


def _env(hub: Path | None = None, **overrides: str) -> dict[str, str]:
    environ = {compat.AUTOMATION_ENV: "1"}
    if hub is not None:
        environ[compat.HUB_PATH_ENV] = str(hub)
    environ.update(overrides)
    return environ


def _pin_digest(monkeypatch: pytest.MonkeyPatch, hub: Path) -> str:
    digest = compat.compute_exec_digest(hub)
    assert digest not in {None, "HUB_NOT_BUILT"}
    assert isinstance(digest, str)
    monkeypatch.setattr(compat, "PINNED_HUB_EXEC_DIGEST", digest)
    return digest


def _tools_payload(*names: str) -> dict[str, Any]:
    return {"data": [{"name": name, "description": "", "inputSchema": {}} for name in names]}


def _allow_cdp(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(url, *, timeout):
        assert url == "http://127.0.0.1:9222/json/version"
        assert timeout == compat.CDP_PREFLIGHT_TIMEOUT_SECONDS
        return _FakeCdpResponse(status=200)

    monkeypatch.setattr(automation.urllib.request, "urlopen", fake_urlopen)


DispatchFactory = Callable[[list[str], dict[str, Any]], Any]


def _install_dispatch_spy(
    monkeypatch: pytest.MonkeyPatch,
    *,
    tool_names: tuple[str, ...],
    dispatch_response: Any | DispatchFactory | None = None,
) -> list[tuple[list[str], dict[str, Any]]]:
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def fake_run(args, **kwargs):
        args_list = list(args)
        calls.append((args_list, kwargs))
        if args_list == ["mcp:tools", "--json"]:
            return _tools_payload(*tool_names)
        if callable(dispatch_response):
            return dispatch_response(args_list, kwargs)
        if dispatch_response is None:
            return {"ok": True, "status": "ok"}
        if isinstance(dispatch_response, BaseException):
            raise dispatch_response
        return dispatch_response

    monkeypatch.setattr(automation, "run_hub_command", fake_run)
    return calls


def _dispatch_calls(calls: list[tuple[list[str], dict[str, Any]]]) -> list[tuple[list[str], dict[str, Any]]]:
    return [call for call in calls if call[0] != ["mcp:tools", "--json"]]


def _platform_data_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    data_root = tmp_path / "platform-data"
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(data_root))
    return data_root


def _governed_dir(data_root: Path, *, account: str = ACCOUNT, task_id: str = TASK_ID) -> Path:
    return data_root / "users" / account / "tasks" / task_id / "artifacts"


def _ready_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    op: str,
    params: dict[str, Any],
    *,
    response: Any | DispatchFactory | None = None,
    account: str | None = ACCOUNT,
    task_id: str | None = TASK_ID,
) -> tuple[dict[str, Any], list[tuple[list[str], dict[str, Any]]], Path, Path]:
    data_root = _platform_data_root(tmp_path, monkeypatch)
    hub = _make_hub(tmp_path)
    _pin_digest(monkeypatch, hub)
    calls = _install_dispatch_spy(monkeypatch, tool_names=(op,), dispatch_response=response)
    _allow_cdp(monkeypatch)
    result = automation.dispatch_web_ai(
        op,
        params,
        environ=_env(
            hub,
            **{
                compat.CDP_HOST_ENV: "127.0.0.1",
                compat.CDP_PORT_ENV: "9222",
                "WAH_BROWSER_EXECUTABLE": "/usr/bin/chrome",
                "WAH_AUTO_CONFIRM": "1",
                "confirmed": "1",
            },
        ),
        account=account,
        task_id=task_id,
    )
    return result, calls, hub, data_root


def test_d12_constants_pageful_mapping_and_hard_exclusion_precedence() -> None:
    assert compat.PINNED_HUB_EXEC_DIGEST == "44da637f22dfbc578494bde43657267b42bf92585f44add06c82f8cd77ed9410"
    assert compat.ARTIFACT_FILE_MAX_BYTES == 268_435_456
    assert compat.automation_timeout_for(CHATGPT_IMAGE_OP) == compat.GENERATE_AUTOMATION_TIMEOUT_SECONDS == 300
    assert compat.automation_timeout_for(GEMINI_IMAGE_OP) == 300
    assert compat.automation_timeout_for(GEMINI_VIDEO_OP) == compat.AUTOMATION_TIMEOUT_SECONDS == 200
    assert compat.automation_timeout_for("webai_task_status") == 200
    assert compat.automation_timeout_for(None) == 200
    assert compat.DISPATCHABLE == compat.DISPATCHABLE_D10_02 | compat.DISPATCHABLE_D10_03 | compat.DISPATCHABLE_D12
    assert compat.DISPATCHABLE_D12 == frozenset({CHATGPT_IMAGE_OP, GEMINI_IMAGE_OP, GEMINI_VIDEO_OP, MUSIC_OP})

    assert compat.OP_TO_CLI_COMMAND[CHATGPT_IMAGE_OP] == "webai:chatgpt:generate-image"
    assert compat.OP_TO_CLI_COMMAND[GEMINI_IMAGE_OP] == "webai:gemini:generate-image"
    assert compat.OP_TO_CLI_COMMAND[GEMINI_VIDEO_OP] == "webai:gemini:generate-video"
    assert compat.OP_TO_CLI_COMMAND[MUSIC_OP] == "webai:gemini:music:generate"

    for op in compat.DISPATCHABLE_D12:
        assert compat.is_pageful(op) is True
        assert compat.is_hard_excluded(op) is False

    assert compat.is_hard_excluded("webai_gemini_music_download_track") is True
    assert compat.is_hard_excluded("webai_gemini_music_task_status") is True
    assert compat.is_hard_excluded("webai_chatgpt_generate_file") is True
    assert compat.is_hard_excluded("webai_gemini_canvas_to_docs") is True
    assert compat.is_hard_excluded("webai_claude_design_render") is True


@pytest.mark.parametrize(
    ("op", "command"),
    [
        (CHATGPT_IMAGE_OP, "webai:chatgpt:generate-image"),
        (GEMINI_IMAGE_OP, "webai:gemini:generate-image"),
        (GEMINI_VIDEO_OP, "webai:gemini:generate-video"),
    ],
)
def test_d12_image_video_validate_forces_governed_download_dir(op: str, command: str, tmp_path: Path) -> None:
    governed = str(tmp_path / "governed" / "tasks" / TASK_ID / "artifacts")

    argv, err = compat.validate_request(op, {"profile": "p", "prompt": "make an artifact"}, download_dir=governed)

    assert err is None
    assert argv == [
        command,
        "--profile",
        "p",
        "--prompt",
        "make an artifact",
        "--download-dir",
        governed,
        "--output-json",
    ]
    assert "--confirmed" not in argv
    assert "WAH_AUTO_CONFIRM" not in argv


@pytest.mark.parametrize("bad_key", ["download_dir", "download-dir", "WAH_AUTO_CONFIRM", "--x", "confirmed", "task_id"])
def test_d12_image_video_validate_rejects_caller_download_dir_and_injection_keys(
    bad_key: str,
    tmp_path: Path,
) -> None:
    argv, err = compat.validate_request(
        CHATGPT_IMAGE_OP,
        {"profile": "p", "prompt": "draw", bad_key: "bad"},
        download_dir=str(tmp_path / "governed"),
    )

    assert argv is None
    assert err == "request rejected: unsupported parameter"


@pytest.mark.parametrize("prompt", ["--prompt=x", "x\x00", "x\x1f"])
def test_d12_image_video_validate_reuses_prompt_control_guards(prompt: str, tmp_path: Path) -> None:
    argv, err = compat.validate_request(
        GEMINI_VIDEO_OP,
        {"profile": "p", "prompt": prompt},
        download_dir=str(tmp_path / "governed"),
    )

    assert argv is None
    assert err == "request rejected: invalid prompt"


@pytest.mark.parametrize(
    ("op", "command", "filename"),
    [
        (CHATGPT_IMAGE_OP, "webai:chatgpt:generate-image", "chatgpt-image.png"),
        (GEMINI_IMAGE_OP, "webai:gemini:generate-image", "gemini-image.png"),
        (GEMINI_VIDEO_OP, "webai:gemini:generate-video", "gemini-video.mp4"),
    ],
)
def test_d12_dispatch_image_video_reconfines_path_and_redacts_to_task_relative_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    op: str,
    command: str,
    filename: str,
) -> None:
    def response(args: list[str], _kwargs: dict[str, Any]) -> dict[str, Any]:
        download_dir = Path(args[args.index("--download-dir") + 1])
        artifact = _write_file(download_dir / filename, "artifact bytes\n")
        return {
            "ok": True,
            "status": "ok",
            "path": str(artifact),
            "download_filename": f"/tmp/{filename}",
            "sha256": "a" * 64,
            "size_bytes": artifact.stat().st_size,
            "dimensions": None,
            "conversation_url": "https://gemini.google.com/app/no-secret?token=drop#fragment",
        }

    result, calls, hub, data_root = _ready_dispatch(
        tmp_path,
        monkeypatch,
        op,
        {"profile": "p", "prompt": "make an artifact"},
        response=response,
    )

    governed = _governed_dir(data_root)
    assert result == {
        "ok": True,
        "status": "ok",
        "path": f"tasks/{TASK_ID}/artifacts/{filename}",
        "download_filename": filename,
        "sha256": "a" * 64,
        "size_bytes": len("artifact bytes\n"),
        "conversation_url": "https://gemini.google.com/app/no-secret",
    }
    dispatch = _dispatch_calls(calls)
    assert len(dispatch) == 1
    argv, kwargs = dispatch[0]
    assert argv == [
        command,
        "--profile",
        "p",
        "--prompt",
        "make an artifact",
        "--download-dir",
        str(governed),
        "--output-json",
    ]
    assert kwargs["hub_path"] == hub
    assert kwargs["timeout"] == compat.automation_timeout_for(op)
    assert kwargs["env"]["WAH_CDP_HOST"] == "127.0.0.1"
    assert kwargs["env"]["WAH_CDP_PORT"] == "9222"
    assert "WAH_BROWSER_EXECUTABLE" not in kwargs["env"]
    assert "WAH_AUTO_CONFIRM" not in kwargs["env"]
    assert "confirmed" not in kwargs["env"]


@pytest.mark.parametrize("bad_task_id", ["../escape", "/absolute", "task_bad\x00", "bad-task", "task_"])
def test_d12_download_dir_governance_rejects_invalid_task_ids_before_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    bad_task_id: str,
) -> None:
    result, calls, _hub, _data_root = _ready_dispatch(
        tmp_path,
        monkeypatch,
        CHATGPT_IMAGE_OP,
        {"profile": "p", "prompt": "draw"},
        task_id=bad_task_id,
    )

    assert result == {"status": "not_implemented", "reason": "artifact path governance violation"}
    assert _dispatch_calls(calls) == []


def test_d12_download_dir_governance_rejects_symlink_escape_before_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_root = _platform_data_root(tmp_path, monkeypatch)
    user_root = data_root / "users" / ACCOUNT
    outside = tmp_path / "outside-user-root"
    outside.mkdir()
    (user_root / "tasks").mkdir(parents=True)
    (user_root / "tasks" / TASK_ID).symlink_to(outside, target_is_directory=True)

    hub = _make_hub(tmp_path)
    _pin_digest(monkeypatch, hub)
    calls = _install_dispatch_spy(monkeypatch, tool_names=(CHATGPT_IMAGE_OP,))
    _allow_cdp(monkeypatch)
    result = automation.dispatch_web_ai(
        CHATGPT_IMAGE_OP,
        {"profile": "p", "prompt": "draw"},
        environ=_env(hub, **{compat.CDP_HOST_ENV: "127.0.0.1", compat.CDP_PORT_ENV: "9222"}),
        account=ACCOUNT,
        task_id=TASK_ID,
    )

    assert result == {"status": "not_implemented", "reason": "artifact path governance violation"}
    assert _dispatch_calls(calls) == []


@pytest.mark.parametrize(
    "case",
    ["outside_root", "symlink_escape", "parent_escape", "sibling_user", "non_regular", "oversize"],
)
def test_d12_return_path_escape_matrix_fails_closed_without_host_path_leak(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    data_root = _platform_data_root(tmp_path, monkeypatch)
    governed = _governed_dir(data_root)
    outside = tmp_path / "outside"
    sibling = data_root / "users" / "other_user" / "tasks" / TASK_ID / "artifacts"

    def response(args: list[str], _kwargs: dict[str, Any]) -> dict[str, Any]:
        assert Path(args[args.index("--download-dir") + 1]) == governed
        governed.mkdir(parents=True, exist_ok=True)
        outside.mkdir(parents=True, exist_ok=True)
        if case == "outside_root":
            bad = _write_file(outside / "escape.png", "x")
        elif case == "symlink_escape":
            target = _write_file(outside / "target.png", "x")
            bad = governed / "link.png"
            bad.symlink_to(target)
        elif case == "parent_escape":
            bad = governed / ".." / "parent.png"
            _write_file(governed.parent / "parent.png", "x")
        elif case == "sibling_user":
            bad = _write_file(sibling / "sibling.png", "x")
        elif case == "non_regular":
            bad = governed / "directory"
            bad.mkdir()
        else:
            bad = governed / "huge.mp4"
            bad.parent.mkdir(parents=True, exist_ok=True)
            with bad.open("wb") as handle:
                handle.truncate(compat.ARTIFACT_FILE_MAX_BYTES + 1)
        return {"ok": True, "status": "ok", "path": str(bad), "message": f"leak {bad}"}

    hub = _make_hub(tmp_path)
    _pin_digest(monkeypatch, hub)
    calls = _install_dispatch_spy(monkeypatch, tool_names=(GEMINI_VIDEO_OP,), dispatch_response=response)
    _allow_cdp(monkeypatch)
    result = automation.dispatch_web_ai(
        GEMINI_VIDEO_OP,
        {"profile": "p", "prompt": "video"},
        environ=_env(hub, **{compat.CDP_HOST_ENV: "127.0.0.1", compat.CDP_PORT_ENV: "9222"}),
        account=ACCOUNT,
        task_id=TASK_ID,
    )

    assert result == {"status": "not_implemented", "reason": "artifact path governance violation"}
    rendered = repr(result)
    assert str(tmp_path) not in rendered
    assert str(data_root) not in rendered
    assert len(_dispatch_calls(calls)) == 1


def test_d12_redaction_handlers_for_artifact_shapes_and_conversation_urls(tmp_path: Path) -> None:
    artifact = _write_file(tmp_path / "safe-artifact.png", "x")

    result = automation.redact_hub_response(
        {
            "ok": True,
            "path": "$HOME /etc/passwd eyJabc.def.ghi",
            "download_filename": "/tmp/sessionid=abc123.png",
            "sha256": "b" * 64,
            "size_bytes": 1,
            "dimensions": {"width": 1024},
            "conversation_url": "https://gemini.google.com/app/clean?token=drop#fragment",
        },
        task_id=TASK_ID,
        validated_artifact_path=artifact,
    )

    assert result == {
        "ok": True,
        "path": f"tasks/{TASK_ID}/artifacts/safe-artifact.png",
        "download_filename": "sessionid=[redacted]",
        "sha256": "b" * 64,
        "size_bytes": 1,
        "conversation_url": "https://gemini.google.com/app/clean",
        "status": "ok",
    }
    assert "/etc/passwd" not in repr(result)
    assert "$HOME" not in repr(result)
    assert "eyJabc" not in repr(result)

    for bad_sha in ("a" * 63, "a" * 65, "g" * 64):
        bad = automation.redact_hub_response({"ok": True, "sha256": bad_sha})
        assert "sha256" not in bad

    for bad_url in (
        "https://claude.ai/new",
        "https://evil.com/app/clean",
        "https://gemini.google.com/share/abcdef1234567890",
    ):
        bad = automation.redact_hub_response({"ok": True, "conversation_url": bad_url})
        assert "conversation_url" not in bad

    assert "size_bytes" not in automation.redact_hub_response({"ok": True, "size_bytes": True})
    assert "size_bytes" not in automation.redact_hub_response(
        {"ok": True, "size_bytes": compat.ARTIFACT_FILE_MAX_BYTES + 1}
    )


def test_d12_music_generate_never_synthesizes_confirmed_and_returns_structured_blocked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    argv, err = compat.validate_request(
        MUSIC_OP,
        {"profile": "gemini", "prompt": "compose", "confirmed": True},
    )
    assert argv is None
    assert err == "request rejected: unsupported parameter"

    argv, err = compat.validate_request(MUSIC_OP, {"profile": "gemini", "prompt": "compose"})
    assert err is None
    assert argv == ["webai:gemini:music:generate", "--profile", "gemini", "--prompt", "compose", "--output-json"]
    assert "--confirmed" not in argv
    assert "--download-dir" not in argv

    result, calls, _hub, _data_root = _ready_dispatch(
        tmp_path,
        monkeypatch,
        MUSIC_OP,
        {"profile": "gemini", "prompt": "sensitive music"},
        response={
            "ok": False,
            "status": "BLOCKED",
            "error_code": "SENSITIVE_CONTENT_GUARD",
            "action": "manual_user_confirmation_required",
            "message": "confirmed required token=secret /home/l1u",
        },
        account=None,
        task_id=None,
    )

    assert result["status"] == "BLOCKED"
    assert result["error_code"] == "SENSITIVE_CONTENT_GUARD"
    assert result["action"] == "manual_user_confirmation_required"
    assert "secret" not in result["message"]
    assert "/home/l1u" not in result["message"]
    dispatch = _dispatch_calls(calls)
    assert len(dispatch) == 1
    argv, kwargs = dispatch[0]
    assert argv == [
        "webai:gemini:music:generate",
        "--profile",
        "gemini",
        "--prompt",
        "sensitive music",
        "--output-json",
    ]
    assert "--confirmed" not in argv
    assert "--download-dir" not in argv
    assert "WAH_AUTO_CONFIRM" not in kwargs["env"]
    assert "confirmed" not in kwargs["env"]


@pytest.mark.parametrize("op", ["webai_gemini_music_download_track", "webai_gemini_music_task_status"])
def test_d12_music_async_paths_stay_non_dispatchable_and_hard_excluded(op: str) -> None:
    assert op not in compat.DISPATCHABLE
    assert compat.is_hard_excluded(op) is True
    argv, err = compat.validate_request(op, {})
    assert argv is None
    assert err == "request rejected: operation not dispatchable"


@pytest.mark.parametrize(
    "op",
    ["webai_chatgpt_generate_file", "webai_gemini_canvas_to_docs", "webai_claude_design_render"],
)
def test_d12_over_admission_regression_still_rejects_adjacent_generation_surfaces(op: str) -> None:
    assert op not in compat.DISPATCHABLE
    assert compat.is_hard_excluded(op) is True
    argv, err = compat.validate_request(op, {"profile": "p", "prompt": "x"})
    assert argv is None
    assert err == "request rejected: operation not dispatchable"


def _enable_d14_async_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *, pageful: bool) -> Path:
    _platform_data_root(tmp_path, monkeypatch)
    hub = _make_hub(tmp_path, label="hub-d14")
    _pin_digest(monkeypatch, hub)
    monkeypatch.setenv(compat.AUTOMATION_ENV, "1")
    monkeypatch.setenv(compat.HUB_PATH_ENV, str(hub))
    if pageful:
        monkeypatch.setenv(compat.CDP_HOST_ENV, "127.0.0.1")
        monkeypatch.setenv(compat.CDP_PORT_ENV, "9222")
        _allow_cdp(monkeypatch)
    return hub


def test_d14_hub_adapter_redactor_alias_stays_identical() -> None:
    assert "result" not in compat.RESPONSE_KEY_ALLOWLIST
    assert hub_adapter.redact_hub_response is automation.redact_hub_response


def test_d14_async_start_running_and_profile_busy_use_real_start_envelopes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _enable_d14_async_env(monkeypatch, tmp_path, pageful=True)
    hub_task_id = "task_hub_d14"

    def running_response(args: list[str], kwargs: dict[str, Any]) -> dict[str, Any]:
        assert args[0] == "webai:gemini:generate-video"
        assert kwargs["timeout"] == compat.automation_timeout_for(GEMINI_VIDEO_OP)
        return {
            "task_id": hub_task_id,
            "status": "running",
            "profile": "gemini-9225",
            "lease_id": "lease_d14",
            "started_at": "2026-05-16T00:00:00Z",
        }

    calls = _install_dispatch_spy(monkeypatch, tool_names=(GEMINI_VIDEO_OP,), dispatch_response=running_response)

    result = hub_adapter.dispatch_async_start(
        GEMINI_VIDEO_OP,
        {"profile": "gemini-9225", "prompt": "make a video"},
        account=ACCOUNT,
        task_id=TASK_ID,
    )

    assert result == {
        "outcome": "running",
        "status": "running",
        "task_id": hub_task_id,
        "payload": {"task_id": hub_task_id, "status": "running"},
    }
    assert len(_dispatch_calls(calls)) == 1

    def busy_response(args: list[str], _kwargs: dict[str, Any]) -> dict[str, Any]:
        assert args[0] == "webai:gemini:generate-video"
        return {
            "status": "failed",
            "errorCode": "PROFILE_LEASE_BUSY",
            "message": "profile busy at /home/l1u token=secret",
        }

    busy_calls = _install_dispatch_spy(monkeypatch, tool_names=(GEMINI_VIDEO_OP,), dispatch_response=busy_response)
    busy = hub_adapter.dispatch_async_start(
        GEMINI_VIDEO_OP,
        {"profile": "gemini-9225", "prompt": "make a video"},
        account=ACCOUNT,
        task_id=TASK_ID,
    )

    assert busy["outcome"] == "blocked"
    assert busy["payload"]["status"] == "failed"
    assert busy["payload"]["errorCode"] == "PROFILE_LEASE_BUSY"
    assert len(_dispatch_calls(busy_calls)) == 1
    rendered = repr(busy)
    assert "/home" not in rendered
    assert "secret" not in rendered


def test_d14_async_status_done_reconfines_nested_result_before_redaction(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    data_root = _platform_data_root(tmp_path, monkeypatch)
    _enable_d14_async_env(monkeypatch, tmp_path, pageful=False)
    hub_task_id = "task_hub_d14"
    content = b"video bytes\n"
    artifact = _governed_dir(data_root) / "video.mp4"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_bytes(content)

    def done_response(args: list[str], kwargs: dict[str, Any]) -> dict[str, Any]:
        assert args == ["webai:task-status", "--task-id", hub_task_id, "--output-json"]
        assert kwargs["timeout"] == compat.automation_timeout_for("webai_task_status")
        return {
            "status": "done",
            "progress_label": "downloaded",
            "result": {
                "path": str(artifact),
                "sha256": hashlib.sha256(content).hexdigest(),
                "size_bytes": len(content),
                "download_filename": "/tmp/video.mp4",
            },
        }

    _install_dispatch_spy(monkeypatch, tool_names=("webai_task_status",), dispatch_response=done_response)

    result = hub_adapter.dispatch_async_status(
        "webai_task_status",
        {"task_id": hub_task_id},
        account=ACCOUNT,
        task_id=TASK_ID,
    )

    assert result == {
        "outcome": "ok",
        "status": "ok",
        "payload": {
            "status": "ok",
            "path": f"tasks/{TASK_ID}/artifacts/video.mp4",
            "sha256": hashlib.sha256(content).hexdigest(),
            "size_bytes": len(content),
            "download_filename": "video.mp4",
        },
    }
    assert "result" not in result["payload"]
    assert str(tmp_path) not in repr(result)


@pytest.mark.parametrize("case", ["etc_passwd", "sibling_task", "parent_escape", "symlink_escape"])
def test_d14_async_status_outside_nested_result_path_blocks_without_path_leak(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    case: str,
) -> None:
    data_root = _platform_data_root(tmp_path, monkeypatch)
    _enable_d14_async_env(monkeypatch, tmp_path, pageful=False)
    hub_task_id = "task_hub_d14"
    governed = _governed_dir(data_root)
    governed.mkdir(parents=True, exist_ok=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    if case == "etc_passwd":
        bad_path = Path("/etc/passwd")
    elif case == "sibling_task":
        bad_path = _write_file(data_root / "users" / ACCOUNT / "tasks" / "task_d14_sibling" / "artifacts" / "video.mp4", "x")
    elif case == "parent_escape":
        bad_path = governed / ".." / "escape.mp4"
        _write_file(governed.parent / "escape.mp4", "x")
    else:
        target = _write_file(outside / "target.mp4", "x")
        bad_path = governed / "link.mp4"
        bad_path.symlink_to(target)

    def done_response(args: list[str], _kwargs: dict[str, Any]) -> dict[str, Any]:
        assert args == ["webai:task-status", "--task-id", hub_task_id, "--output-json"]
        return {
            "status": "done",
            "result": {
                "path": str(bad_path),
                "sha256": "a" * 64,
                "size_bytes": 1,
                "download_filename": "video.mp4",
            },
        }

    _install_dispatch_spy(monkeypatch, tool_names=("webai_task_status",), dispatch_response=done_response)

    result = hub_adapter.dispatch_async_status(
        "webai_task_status",
        {"task_id": hub_task_id},
        account=ACCOUNT,
        task_id=TASK_ID,
    )

    assert result["outcome"] == "blocked"
    assert result["status"] == "not_implemented"
    assert result["reason"] == "artifact path governance violation"
    assert "path" not in result["payload"]
    rendered = repr(result)
    assert str(tmp_path) not in rendered
    assert "/home" not in rendered
    assert "$HOME" not in rendered


@pytest.mark.parametrize("error_code", ["COMMAND_TIMEOUT", "MODEL_ERROR"])
def test_d14_async_status_failed_blocks_with_redacted_error_code(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    error_code: str,
) -> None:
    _enable_d14_async_env(monkeypatch, tmp_path, pageful=False)
    hub_task_id = "task_hub_d14"

    def failed_response(args: list[str], _kwargs: dict[str, Any]) -> dict[str, Any]:
        assert args == ["webai:task-status", "--task-id", hub_task_id, "--output-json"]
        return {
            "status": "failed",
            "errorCode": error_code,
            "message": "failed at /home/l1u token=secret",
        }

    _install_dispatch_spy(monkeypatch, tool_names=("webai_task_status",), dispatch_response=failed_response)

    result = hub_adapter.dispatch_async_status(
        "webai_task_status",
        {"task_id": hub_task_id},
        account=ACCOUNT,
        task_id=TASK_ID,
    )

    assert result["outcome"] == "blocked"
    assert result["status"] == "failed"
    assert result["reason"] == f"video generation failed: {error_code}"
    assert result["payload"]["errorCode"] == error_code
    rendered = repr(result)
    assert "/home" not in rendered
    assert "secret" not in rendered

# SPDX-License-Identifier: Apache-2.0
# ruff: noqa: E402
"""C3 hub adapter fail-closed normalization tests."""

from __future__ import annotations

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
from noeticbraid_backend.platform.orchestration import hub_adapter


def _real_chatgpt_success_envelope(**overrides: Any) -> dict[str, Any]:
    envelope: dict[str, Any] = {
        "response_text": "live hub content",
        "elapsed_ms": 1200,
        "wait_ms": 1100,
        "completion_detected": True,
        "errorCode": None,
        "model_used": "Thinking",
        "reuse_conversation": False,
        "conversation_id": "Conversation_d13",
        "chat_url": "https://chatgpt.com/c/live-run",
    }
    envelope.update(overrides)
    return envelope


def _dispatch_raw(monkeypatch: pytest.MonkeyPatch, raw: dict[str, Any], op: str = "webai_chatgpt_send_prompt") -> dict[str, Any]:
    monkeypatch.setattr(hub_adapter._automation, "dispatch_web_ai", lambda _op, _params, **_kwargs: raw)
    return hub_adapter.dispatch(op, {"profile": "chatgpt", "prompt": "hi"})


def test_hub_adapter_ok_response_is_redacted_and_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "sk-test_abcdefghijklmnop"

    def fake_dispatch(op: str, params: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
        assert op == "webai_chatgpt_send_prompt"
        assert params["profile"] == "chatgpt"
        return _real_chatgpt_success_envelope(response_text=f"model returned {secret}")

    monkeypatch.setattr(hub_adapter._automation, "dispatch_web_ai", fake_dispatch)

    result = hub_adapter.dispatch("webai_chatgpt_send_prompt", {"profile": "chatgpt", "prompt": "hi"})

    assert result["outcome"] == "ok"
    assert result["status"] == "ok"
    assert result["payload"]["response_text"] == "model returned [redacted]"
    assert secret not in str(result)


@pytest.mark.parametrize(
    ("raw", "status"),
    [
        ({"status": "not_implemented", "reason": "disabled"}, "not_implemented"),
        ({"status": "HUB_NOT_BUILT"}, "HUB_NOT_BUILT"),
        ({"status": "approval_required", "reason": "manual approval required"}, "approval_required"),
        ({"status": "error", "reason": "failed"}, "error"),
        ({"status": "BLOCKED", "message": "blocked"}, "BLOCKED"),
    ],
)
def test_hub_adapter_structured_refusals_are_blocked(
    monkeypatch: pytest.MonkeyPatch,
    raw: dict[str, Any],
    status: str,
) -> None:
    monkeypatch.setattr(hub_adapter._automation, "dispatch_web_ai", lambda _op, _params, **_kwargs: raw)

    result = hub_adapter.dispatch("webai_chatgpt_send_prompt", {"profile": "chatgpt", "prompt": "hi"})

    assert result["outcome"] == "blocked"
    assert result["status"] == status
    assert result["payload"]["status"] == status


def test_d13_real_chatgpt_success_envelope_normalizes_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = _real_chatgpt_success_envelope()

    redacted = automation.redact_hub_response(raw)
    assert redacted["status"] == "ok"
    assert redacted["completion_detected"] is True
    assert redacted["response_text"] == "live hub content"
    assert "errorCode" not in redacted

    result = _dispatch_raw(monkeypatch, raw)
    assert result["outcome"] == "ok"
    assert result["status"] == "ok"
    assert result["payload"] == redacted


@pytest.mark.parametrize(
    ("overrides", "error_key", "error_value"),
    [
        ({"completion_detected": False}, None, None),
        ({"completion_detected": None}, None, None),
        ({"completion_detected": 1}, None, None),
        ({"errorCode": "RATE_LIMITED"}, "errorCode", "RATE_LIMITED"),
        ({"errorCode": ""}, "errorCode", ""),
        ({"errorCode": 0}, "errorCode", "0"),
    ],
)
def test_d13_chatgpt_success_negative_twins_block(
    monkeypatch: pytest.MonkeyPatch,
    overrides: dict[str, Any],
    error_key: str | None,
    error_value: str | None,
) -> None:
    raw = _real_chatgpt_success_envelope(**overrides)
    if "completion_detected" in overrides and overrides["completion_detected"] is None:
        raw.pop("completion_detected")

    redacted = automation.redact_hub_response(raw)
    assert redacted["status"] == "error"
    if error_key is not None:
        assert redacted[error_key] == error_value

    result = _dispatch_raw(monkeypatch, raw)
    assert result["outcome"] == "blocked"
    assert result["status"] == "error"


def test_d13_forged_ok_without_completion_is_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = {"ok": True, "response_text": "forged shortcut"}

    redacted = automation.redact_hub_response(raw)
    assert redacted == {"ok": True, "response_text": "forged shortcut", "status": "error"}

    result = _dispatch_raw(monkeypatch, raw)
    assert result["outcome"] == "blocked"
    assert result["status"] == "error"


def test_d13_explicit_status_precedence_blocks_even_with_completion(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = _real_chatgpt_success_envelope(status="approval_required")

    redacted = automation.redact_hub_response(raw)
    assert redacted["status"] == "approval_required"
    assert "errorCode" not in redacted

    result = _dispatch_raw(monkeypatch, raw)
    assert result["outcome"] == "blocked"
    assert result["status"] == "approval_required"


def test_d13_generate_success_requires_validated_artifact_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account = "d13_user"
    task_id = "task_d13_artifact"
    data_root = tmp_path / "platform-data"
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(data_root))
    artifact = data_root / "users" / account / "tasks" / task_id / "artifacts" / "image.png"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("image", encoding="utf-8")

    raw = {"path": str(artifact), "download_filename": "image.png"}
    redacted = automation.redact_hub_response(raw, task_id=task_id, validated_artifact_path=artifact)
    assert redacted == {
        "path": f"tasks/{task_id}/artifacts/image.png",
        "download_filename": "image.png",
        "status": "ok",
    }

    monkeypatch.setattr(hub_adapter._automation, "dispatch_web_ai", lambda _op, _params, **_kwargs: raw)
    result = hub_adapter.dispatch(
        "webai_chatgpt_generate_image",
        {"profile": "chatgpt", "prompt": "draw"},
        account=account,
        task_id=task_id,
    )
    assert result["outcome"] == "ok"
    assert result["status"] == "ok"
    assert result["payload"] == redacted

    failed_raw = {"path": str(tmp_path / "outside.png"), "download_filename": "outside.png"}
    failed_redacted = automation.redact_hub_response(failed_raw, task_id=task_id, validated_artifact_path=None)
    assert failed_redacted == {"download_filename": "outside.png", "status": "error"}

    monkeypatch.setattr(hub_adapter._automation, "dispatch_web_ai", lambda _op, _params, **_kwargs: failed_raw)
    failed = hub_adapter.dispatch(
        "webai_chatgpt_generate_image",
        {"profile": "chatgpt", "prompt": "draw"},
        account=account,
        task_id=task_id,
    )
    assert failed["outcome"] == "blocked"
    assert failed["status"] == "error"


def test_d13_music_blocked_status_remains_honest_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = {
        "status": "BLOCKED",
        "error_code": "SENSITIVE_CONTENT_GUARD",
        "message": "manual confirmation required",
    }

    result = _dispatch_raw(monkeypatch, raw, op="webai_gemini_music_generate")

    assert result["outcome"] == "blocked"
    assert result["status"] == "BLOCKED"
    assert result["payload"]["error_code"] == "SENSITIVE_CONTENT_GUARD"

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

from noeticbraid_backend.platform.orchestration import hub_adapter


def test_hub_adapter_ok_response_is_redacted_and_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "sk-test_abcdefghijklmnop"

    def fake_dispatch(op: str, params: dict[str, Any]) -> dict[str, Any]:
        assert op == "webai_chatgpt_send_prompt"
        assert params["profile"] == "chatgpt"
        return {"ok": True, "response_text": f"model returned {secret}"}

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
    ],
)
def test_hub_adapter_structured_refusals_are_blocked(
    monkeypatch: pytest.MonkeyPatch,
    raw: dict[str, Any],
    status: str,
) -> None:
    monkeypatch.setattr(hub_adapter._automation, "dispatch_web_ai", lambda _op, _params: raw)

    result = hub_adapter.dispatch("webai_chatgpt_send_prompt", {"profile": "chatgpt", "prompt": "hi"})

    assert result["outcome"] == "blocked"
    assert result["status"] == status
    assert result["payload"]["status"] == status

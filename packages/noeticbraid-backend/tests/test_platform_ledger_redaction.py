# SPDX-License-Identifier: Apache-2.0
# ruff: noqa: E402
"""C2 ledger AI-call events persist only post-redaction hub payloads."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parent.parent
SRC_ROOT = PACKAGE_ROOT / "src"
CORE_SRC_ROOT = REPO_ROOT / "packages" / "noeticbraid-core" / "src"
for path in (CORE_SRC_ROOT, SRC_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import pytest

from noeticbraid_backend.platform.ledger.events import ai_call_event, dispatch_event
from noeticbraid_backend.platform.ledger.writer import append_event, ledger_path_for
from noeticbraid_backend.platform.tasks.models import TaskState


def test_ai_call_ledger_event_strips_secret_shaped_hub_text(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(tmp_path / "platform-data"))
    account = "beta_user_03"
    task_id = "task_redaction"
    secret = "sk-test_abcdefghijklmnop"

    append_event(account, dispatch_event(task_id, to_state=TaskState.CREATED))
    append_event(
        account,
        ai_call_event(
            task_id,
            op="webai_chatgpt_send_prompt",
            vendor="chatgpt",
            gate_status="ready",
            redacted_payload={"ok": True, "response_text": f"model returned {secret} in text"},
            prompt_text="Do not persist this prompt verbatim.",
            to_state=TaskState.PLANNING,
        ),
    )

    rendered = ledger_path_for(account, task_id).read_text(encoding="utf-8")
    assert secret not in rendered
    rows = [json.loads(line) for line in rendered.splitlines()]
    payload = rows[-1]["payload"]
    assert payload["redacted_payload"]["response_text"] == "model returned [redacted] in text"
    assert "Do not persist this prompt verbatim." not in rendered
    assert "prompt_sha256" in payload
    assert "prompt_len" in payload

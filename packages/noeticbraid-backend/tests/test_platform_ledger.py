# SPDX-License-Identifier: Apache-2.0
# ruff: noqa: E402
"""C2 ledger writer appends parse-valid JSONL and updates the central index."""

from __future__ import annotations

import hashlib
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
from noeticbraid_backend.platform.ledger.writer import append_event, index_path_for, ledger_path_for
from noeticbraid_backend.platform.tasks.models import TaskState, account_ref_for


def test_append_event_assigns_seq_and_refreshes_index(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "platform-data"
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(data_root))
    account = "beta_user_01"

    first = append_event(account, dispatch_event("task_indexed", to_state=TaskState.CREATED))
    second = append_event(
        account,
        dispatch_event("task_indexed", from_state=TaskState.CREATED, to_state=TaskState.PLANNING),
    )

    assert first.seq == 1
    assert second.seq == 2
    rows = [json.loads(line) for line in ledger_path_for(account, "task_indexed").read_text(encoding="utf-8").splitlines()]
    assert [row["seq"] for row in rows] == [1, 2]
    assert rows[0]["account_id_ref"] == account_ref_for(account)
    assert account not in json.dumps(rows, sort_keys=True)

    index_path = data_root / "index" / "tasks_index.jsonl"
    assert index_path_for(account) == index_path
    index_rows = [json.loads(line) for line in index_path.read_text(encoding="utf-8").splitlines()]
    assert index_rows == [
        {
            "account_id_ref": account_ref_for(account),
            "seq": 2,
            "state": "planning",
            "task_id": "task_indexed",
            "type": "dispatch",
            "updated_ts": second.ts,
        }
    ]


def test_ai_call_payload_hashes_prompt_and_redacts_payload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(tmp_path / "platform-data"))
    prompt = "Please summarize the private research notes."

    append_event("beta_user_04", dispatch_event("task_ai", to_state=TaskState.CREATED))
    event = append_event(
        "beta_user_04",
        ai_call_event(
            "task_ai",
            op="webai_chatgpt_send_prompt",
            vendor="chatgpt",
            gate_status="ready",
            redacted_payload={"ok": True, "response_text": f"echo: {prompt}", "prompt": prompt},
            prompt_text=prompt,
            to_state=TaskState.PLANNING,
        ),
    )

    payload = event.payload
    assert payload["prompt_sha256"] == hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    assert payload["prompt_len"] == len(prompt)
    rendered = json.dumps(payload, sort_keys=True)
    assert prompt not in rendered
    assert "prompt" not in payload["redacted_payload"]
    assert payload["redacted_payload"]["response_text"] == "echo: [prompt]"

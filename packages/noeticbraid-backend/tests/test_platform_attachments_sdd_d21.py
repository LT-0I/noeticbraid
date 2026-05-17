# SPDX-License-Identifier: Apache-2.0
# ruff: noqa: E402
"""SDD-D21 backend-only task attachment upload contract tests."""

from __future__ import annotations

import asyncio
import hashlib
import json
import stat
import subprocess
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
from fastapi import HTTPException
from fastapi.testclient import TestClient

from noeticbraid_backend.app import create_app
from noeticbraid_backend.auth.token_store import TokenStore
from noeticbraid_backend.omc_workspace import web_ai_hub_compat as compat
from noeticbraid_backend.platform.attachments import endpoint as attachment_endpoint
from noeticbraid_backend.platform.attachments import store as attachment_store
from noeticbraid_backend.platform.conversation import model
from noeticbraid_backend.platform.elicitation.local_ai import LOCAL_AI_ARGS_ENV, LOCAL_AI_BIN_ENV
from noeticbraid_backend.platform.tasks.store import create_task
from noeticbraid_backend.platform.workspace_paths import resolve_user_path
from noeticbraid_backend.settings import Settings

ACCOUNT = "d21_user_01"
OTHER_ACCOUNT = "d21_user_02"
PUBLIC_ATTACHMENT_KEYS = {"attachment_id", "display_name", "content_type", "bytes", "uploaded_ts"}
FORBIDDEN_PUBLIC_TOKENS = {
    "sha256",
    "rel_path",
    "provenance",
    "ledger",
    "dispatch",
    "critique",
    "internal_reason",
    "internal-reason",
    "orchestration",
    "rounds",
    "directive",
    "reviewer",
    "verdict",
    "evidence_node_ids",
    "workflow",
    "selector",
    "conversation_url",
    "chat_url",
}
FROZEN_PATHS = (
    "packages/noeticbraid-backend/src/noeticbraid_backend/app.py",
    "packages/noeticbraid-backend/src/noeticbraid_backend/platform/auth.py",
    "packages/noeticbraid-backend/src/noeticbraid_backend/api/routes/auth.py",
    "packages/noeticbraid-backend/src/noeticbraid_backend/platform/conversation/model.py",
    "packages/noeticbraid-backend/src/noeticbraid_backend/platform/orchestration",
    "packages/noeticbraid-backend/src/noeticbraid_backend/omc_workspace",
    "packages/noeticbraid-backend/src/noeticbraid_backend/platform/mount.py",
    "packages/noeticbraid-backend/src/noeticbraid_backend/platform/workspace_paths.py",
    "packages/noeticbraid-backend/src/noeticbraid_backend/platform/artifacts",
    "packages/noeticbraid-backend/src/noeticbraid_backend/platform/deliverable",
    "scripts/check_phase1_2_contract_gate.py",
    "pyproject.toml",
)


def _client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[TestClient, Path]:
    data_root = tmp_path / "platform-data"
    monkeypatch.setenv("NOETICBRAID_PLATFORM_ENABLED", "1")
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(data_root))
    app = create_app(Settings(state_dir=tmp_path / "state"))
    return TestClient(app), data_root


def _token(data_root: Path, account: str = ACCOUNT) -> str:
    return TokenStore(data_root).create_token(account)


def _headers(token: str) -> dict[str, str]:
    return {"authorization": f"Bearer {token}"}


def _create_task(client: TestClient, token: str, title: str = "D21 task") -> str:
    response = client.post("/platform/tasks", headers=_headers(token), json={"title": title})
    assert response.status_code == 200, response.text
    return str(response.json()["task"]["task_id"])


def _upload(
    client: TestClient,
    token: str,
    task_id: str,
    *,
    filename: str = "notes.txt",
    body: bytes = b"hello attachment\n",
    mime: str = "text/plain",
):
    return client.post(
        f"/platform/tasks/{task_id}/attachments",
        headers=_headers(token),
        files={"attachment": (filename, body, mime)},
    )


def _raw_upload(client: TestClient, token: str, task_id: str, *, filename: str, body: bytes = b"x"):
    boundary = "d21-boundary"
    multipart = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="attachment"; filename="{filename}"\r\n'
        "Content-Type: text/plain\r\n\r\n"
    ).encode("utf-8", errors="surrogateescape") + body + f"\r\n--{boundary}--\r\n".encode()
    return client.post(
        f"/platform/tasks/{task_id}/attachments",
        headers={**_headers(token), "content-type": f"multipart/form-data; boundary={boundary}"},
        content=multipart,
    )


def _assert_public_clean(value: Any) -> None:
    rendered = json.dumps(value, ensure_ascii=False, sort_keys=True).lower()
    for token in FORBIDDEN_PUBLIC_TOKENS:
        assert token not in rendered


def _write_elicitation_capture_stub(tmp_path: Path, capture_path: Path) -> Path:
    script = tmp_path / "capture_local_ai.py"
    script.write_text(
        "import json, pathlib, sys\n"
        f"pathlib.Path({str(capture_path)!r}).write_text(sys.stdin.read(), encoding='utf-8')\n"
        "print(json.dumps({'requirements': [{'id': 'req_1', 'text': 'draft', 'modality': 'document'}], 'questions': [], 'ready_to_confirm': True}))\n",
        encoding="utf-8",
    )
    script.chmod(0o700)
    return script


def _configure_stub(monkeypatch: pytest.MonkeyPatch, script: Path) -> None:
    monkeypatch.setenv(LOCAL_AI_BIN_ENV, sys.executable)
    monkeypatch.setenv(LOCAL_AI_ARGS_ENV, json.dumps([str(script)]))


def test_attachment_upload_list_fetch_delete_happy_path_private_index_0600(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, data_root = _client(monkeypatch, tmp_path)
    token = _token(data_root)
    task_id = _create_task(client, token)

    response = _upload(client, token, task_id, filename="notes.txt", body=b"hello attachment\n", mime="text/plain")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert set(payload) == {"attachment"}
    attachment = payload["attachment"]
    assert set(attachment) == PUBLIC_ATTACHMENT_KEYS
    assert attachment["display_name"] == "notes.txt"
    assert attachment["content_type"] == "text/plain"
    assert attachment["bytes"] == len(b"hello attachment\n")
    assert "sha256" not in response.text
    _assert_public_clean(payload)

    attachment_id = attachment["attachment_id"]
    blob_path = resolve_user_path(ACCOUNT, f"tasks/{task_id}/attachments/{attachment_id}.txt")
    index_path = resolve_user_path(ACCOUNT, f"tasks/{task_id}/attachments/_index.json")
    assert blob_path.read_bytes() == b"hello attachment\n"
    assert stat.S_IMODE(blob_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(blob_path.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(index_path.stat().st_mode) == 0o600
    index = json.loads(index_path.read_text(encoding="utf-8"))
    assert index["schema_version"] == 1
    assert index["attachments"][0]["sha256"] == hashlib.sha256(b"hello attachment\n").hexdigest()

    listed = client.get(f"/platform/tasks/{task_id}/attachments", headers=_headers(token))
    assert listed.status_code == 200, listed.text
    assert listed.json() == {"attachments": [attachment]}
    _assert_public_clean(listed.json())

    fetched = client.get(f"/platform/tasks/{task_id}/attachments/{attachment_id}", headers=_headers(token))
    assert fetched.status_code == 200, fetched.text
    assert fetched.content == b"hello attachment\n"
    assert fetched.headers["content-type"].startswith("text/plain")
    assert "attachment" in fetched.headers["content-disposition"]
    assert "notes.txt" in fetched.headers["content-disposition"]

    deleted = client.delete(f"/platform/tasks/{task_id}/attachments/{attachment_id}", headers=_headers(token))
    assert deleted.status_code == 200, deleted.text
    assert deleted.json() == {"deleted": True}
    assert not blob_path.exists()
    assert client.delete(f"/platform/tasks/{task_id}/attachments/{attachment_id}", headers=_headers(token)).status_code == 404


@pytest.mark.parametrize("filename", ["../escape.txt", "bad\x00name.txt", "..%2fescape.txt"])
def test_attachment_path_traversal_filenames_are_rejected_without_escape(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    filename: str,
) -> None:
    client, data_root = _client(monkeypatch, tmp_path)
    token = _token(data_root)
    task_id = _create_task(client, token)

    response = _raw_upload(client, token, task_id, filename=filename)

    assert 400 <= response.status_code < 500
    assert str(tmp_path) not in response.text
    assert not (tmp_path / "escape.txt").exists()
    attachments_dir = data_root / "users" / ACCOUNT / "tasks" / task_id / "attachments"
    assert not attachments_dir.exists() or list(attachments_dir.glob("*")) == []


def test_attachment_size_cap_rejects_32mib_plus_one_precheck_and_postread(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    assert attachment_store.MAX_UPLOAD_BYTES == compat.UPLOAD_FILE_MAX_BYTES == 33_554_432
    client, data_root = _client(monkeypatch, tmp_path)
    token = _token(data_root)
    task_id = _create_task(client, token)
    oversized = b"x" * (compat.UPLOAD_FILE_MAX_BYTES + 1)

    response = _upload(client, token, task_id, filename="large.txt", body=oversized, mime="text/plain")

    assert response.status_code == 413
    assert response.json() == {"detail": "upload_too_large"}

    class NoLengthRequest:
        headers = {"content-type": "multipart/form-data; boundary=d21"}

        async def body(self) -> bytes:
            return oversized

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(attachment_endpoint._read_attachment_part(NoLengthRequest()))
    assert exc_info.value.status_code == 413
    assert exc_info.value.detail == "upload_too_large"


def test_attachment_content_type_extension_allowlist_and_mismatch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, data_root = _client(monkeypatch, tmp_path)
    token = _token(data_root)
    task_id = _create_task(client, token)

    mismatch = _upload(client, token, task_id, filename="not_text.png", body=b"hello", mime="text/plain")
    assert mismatch.status_code == 415
    assert mismatch.json() == {"detail": "unsupported_attachment_type"}

    allowed = _upload(client, token, task_id, filename="notes.md", body=b"# ok\n", mime="text/markdown")
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["attachment"]["content_type"] == "text/markdown"


def test_attachment_twenty_first_upload_returns_attachment_limit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, data_root = _client(monkeypatch, tmp_path)
    token = _token(data_root)
    task_id = _create_task(client, token)

    for index in range(attachment_store.MAX_ATTACHMENTS_PER_TASK):
        response = _upload(client, token, task_id, filename=f"note{index}.txt", body=f"{index}\n".encode())
        assert response.status_code == 200, response.text

    limited = _upload(client, token, task_id, filename="note20.txt", body=b"20\n")

    assert limited.status_code == 400
    assert limited.json() == {"detail": "attachment_limit"}


def test_attachment_cross_account_fetch_delete_send_are_opaque_404(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, data_root = _client(monkeypatch, tmp_path)
    token_one = _token(data_root, ACCOUNT)
    token_two = _token(data_root, OTHER_ACCOUNT)
    task_id = "task_d21_private"
    create_task(OTHER_ACCOUNT, task_id=task_id, title="Private", modality_targets=["document"])
    own_upload = _upload(client, token_two, task_id, filename="secret.txt", body=b"secret\n")
    assert own_upload.status_code == 200, own_upload.text
    attachment_id = own_upload.json()["attachment"]["attachment_id"]

    def forbidden_dispatch(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise AssertionError("cross-account send must not reach hub dispatch")

    monkeypatch.setattr(attachment_endpoint.hub_adapter, "dispatch", forbidden_dispatch)

    fetch = client.get(f"/platform/tasks/{task_id}/attachments/{attachment_id}", headers=_headers(token_one))
    delete = client.delete(f"/platform/tasks/{task_id}/attachments/{attachment_id}", headers=_headers(token_one))
    send = client.post(f"/platform/tasks/{task_id}/attachments/{attachment_id}/send-to-hub", headers=_headers(token_one))

    assert fetch.status_code == 404
    assert delete.status_code == 404
    assert send.status_code == 404
    assert b"secret" not in fetch.content + delete.content + send.content


def test_local_ai_ingest_truncates_text_aggregate_and_marks_binary_pending(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, data_root = _client(monkeypatch, tmp_path)
    token = _token(data_root)
    task_id = _create_task(client, token)
    capture_path = tmp_path / "stdin.json"
    _configure_stub(monkeypatch, _write_elicitation_capture_stub(tmp_path, capture_path))
    text_body = ("A" * 9000).encode("utf-8")
    for index in range(3):
        response = _upload(client, token, task_id, filename=f"text{index}.txt", body=text_body, mime="text/plain")
        assert response.status_code == 200, response.text
    binary = _upload(client, token, task_id, filename="image.png", body=b"\x89PNG\r\n", mime="image/png")
    assert binary.status_code == 200, binary.text

    elicit = client.post(
        f"/platform/tasks/{task_id}/elicit",
        headers=_headers(token),
        json={"raw_requirement": "Use my attachments."},
    )

    assert elicit.status_code == 200, elicit.text
    payload = json.loads(capture_path.read_text(encoding="utf-8"))
    attachments = payload["attachments"]
    text_items = [item for item in attachments if item["content_type"] == "text/plain"]
    binary_items = [item for item in attachments if item["content_type"] == "image/png"]
    assert len(text_items) == 3
    assert all(item["local_analysis"] == "text_extracted" for item in text_items)
    assert all(len(item["extracted_text"]) <= 8 * 1024 for item in text_items)
    assert sum(len(item["extracted_text"]) for item in text_items) <= 24 * 1024
    assert binary_items == [
        {
            "attachment_id": binary.json()["attachment"]["attachment_id"],
            "display_name": "image.png",
            "content_type": "image/png",
            "bytes": len(b"\x89PNG\r\n"),
            "local_analysis": "pending_local_unavailable",
        }
    ]


def test_hub_gate_off_returns_unavailable_without_blob_read_or_network(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("NOETICBRAID_PLATFORM_HUB_EXEC", raising=False)
    monkeypatch.delenv(compat.AUTOMATION_ENV, raising=False)
    client, data_root = _client(monkeypatch, tmp_path)
    token = _token(data_root)
    task_id = _create_task(client, token)
    upload = _upload(client, token, task_id, filename="notes.txt", body=b"hub input\n")
    assert upload.status_code == 200, upload.text
    attachment_id = upload.json()["attachment"]["attachment_id"]

    def forbidden_blob_read(*_args: Any, **_kwargs: Any) -> bytes:
        raise AssertionError("send-to-hub must not read the blob before gated dispatch")

    def forbidden_network(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise AssertionError("gate-off send-to-hub must not launch hub commands")

    monkeypatch.setattr(attachment_store, "_read_blob_bounded", forbidden_blob_read)
    monkeypatch.setattr(attachment_endpoint.hub_adapter._automation, "run_hub_command", forbidden_network)

    response = client.post(f"/platform/tasks/{task_id}/attachments/{attachment_id}/send-to-hub", headers=_headers(token))

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "unavailable"
    assert "reason" in response.json()
    _assert_public_clean(response.json())


def test_hub_gate_on_mock_dispatch_uses_resolve_user_path_files_count_cap_and_no_leak(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, data_root = _client(monkeypatch, tmp_path)
    token = _token(data_root)
    task_id = _create_task(client, token)
    uploads = []
    for index in range(4):
        response = _upload(client, token, task_id, filename=f"hub{index}.txt", body=f"hub {index}\n".encode())
        assert response.status_code == 200, response.text
        uploads.append(response.json()["attachment"])
    first_id = uploads[0]["attachment_id"]
    recorded: list[tuple[str, dict[str, Any], dict[str, Any]]] = []

    def ok_dispatch(op: str, params: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        recorded.append((op, dict(params), dict(kwargs)))
        return {
            "outcome": "ok",
            "status": "ok",
            "payload": {
                "status": "ok",
                "response_text": "Hub says this file matters.",
                "conversation_url": "https://chatgpt.com/c/secret",
                "sha256": "f" * 64,
                "path": "/tmp/leak",
            },
        }

    monkeypatch.setattr(attachment_endpoint.hub_adapter, "dispatch", ok_dispatch)

    success = client.post(
        f"/platform/tasks/{task_id}/attachments/{first_id}/send-to-hub",
        headers=_headers(token),
        json={"profile": "chatgpt", "prompt": "Analyze it."},
    )

    assert success.status_code == 200, success.text
    assert success.json() == {"status": "ok", "available": True}
    assert recorded[0][0] == "webai_chatgpt_upload_and_query"
    expected_path = resolve_user_path(ACCOUNT, f"tasks/{task_id}/attachments/{first_id}.txt")
    assert recorded[0][1] == {
        "profile": "chatgpt",
        "query": "Analyze it.",
        "files": [str(expected_path)],
        "reuse_conversation": False,
    }
    assert recorded[0][2] == {"account": ACCOUNT, "task_id": task_id}
    conversation = model.serialize_visible_conversation(ACCOUNT, task_id)
    assert conversation[-1]["text"] == "Hub says this file matters."
    assert str(expected_path).startswith(str(resolve_user_path(ACCOUNT, ".")))
    _assert_public_clean(success.json())

    too_many = client.post(
        f"/platform/tasks/{task_id}/attachments/{first_id}/send-to-hub",
        headers=_headers(token),
        json={"attachment_ids": [item["attachment_id"] for item in uploads]},
    )
    assert too_many.status_code == 400
    assert too_many.json() == {"detail": "hub_attachment_count"}

    def blocked_dispatch(_op: str, _params: dict[str, Any], **_kwargs: Any) -> dict[str, Any]:
        return {
            "outcome": "blocked",
            "status": "error",
            "reason": f"blocked sha256 at {expected_path} conversation_url dispatch",
            "payload": {"sha256": "f" * 64, "conversation_url": "https://chatgpt.com/c/secret"},
        }

    monkeypatch.setattr(attachment_endpoint.hub_adapter, "dispatch", blocked_dispatch)
    blocked = client.post(f"/platform/tasks/{task_id}/attachments/{first_id}/send-to-hub", headers=_headers(token))
    assert blocked.status_code == 200, blocked.text
    assert blocked.json()["status"] == "unavailable"
    assert "reason" in blocked.json()
    _assert_public_clean(blocked.json())


def test_upload_list_send_responses_are_two_zone_clean(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, data_root = _client(monkeypatch, tmp_path)
    token = _token(data_root)
    task_id = _create_task(client, token)
    upload = _upload(client, token, task_id, filename="clean.txt", body=b"clean\n")
    assert upload.status_code == 200, upload.text
    attachment_id = upload.json()["attachment"]["attachment_id"]
    monkeypatch.setattr(
        attachment_endpoint.hub_adapter,
        "dispatch",
        lambda *_args, **_kwargs: {"outcome": "ok", "status": "ok", "payload": {"response_text": "clean analysis"}},
    )
    listed = client.get(f"/platform/tasks/{task_id}/attachments", headers=_headers(token))
    sent = client.post(f"/platform/tasks/{task_id}/attachments/{attachment_id}/send-to-hub", headers=_headers(token))

    assert sent.status_code == 200, sent.text
    for payload in (upload.json(), listed.json(), sent.json()):
        _assert_public_clean(payload)


def test_upload_does_not_mutate_requirements_or_view_bytes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, data_root = _client(monkeypatch, tmp_path)
    token = _token(data_root)
    task_id = _create_task(client, token)
    requirements_path = model.requirements_path_for(ACCOUNT, task_id)
    before_requirements = requirements_path.read_bytes()
    before_view = client.get(f"/platform/tasks/{task_id}/view", headers=_headers(token)).content

    upload = _upload(client, token, task_id, filename="input.txt", body=b"input\n")

    assert upload.status_code == 200, upload.text
    assert requirements_path.read_bytes() == before_requirements
    assert client.get(f"/platform/tasks/{task_id}/view", headers=_headers(token)).content == before_view


def test_sdd_d21_frozen_files_match_git_head() -> None:
    paths = subprocess.run(
        ["git", "ls-files", "--", *FROZEN_PATHS],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.splitlines()
    assert paths
    for rel_path in paths:
        current = (REPO_ROOT / rel_path).read_bytes()
        head = subprocess.run(
            ["git", "show", f"HEAD:{rel_path}"],
            cwd=REPO_ROOT,
            capture_output=True,
            check=True,
        ).stdout
        assert hashlib.sha256(current).hexdigest() == hashlib.sha256(head).hexdigest(), rel_path

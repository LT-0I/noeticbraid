# SPDX-License-Identifier: Apache-2.0
# ruff: noqa: E402
"""SDD-D16 platform console read-wiring endpoint tests."""

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
from fastapi.testclient import TestClient

from noeticbraid_backend.app import create_app
from noeticbraid_backend.auth.token_store import TokenStore
from noeticbraid_backend.platform.artifacts.store import persist
from noeticbraid_backend.platform.auth import require_platform_bearer
from noeticbraid_backend.platform.ledger.events import ai_call_event
from noeticbraid_backend.platform.ledger.writer import append_event
from noeticbraid_backend.platform.settings import PLATFORM_DEV_SESSION_ACCOUNT_ENV
from noeticbraid_backend.platform.tasks.models import Task, TaskState, account_ref_for
from noeticbraid_backend.platform.tasks.store import create_task, task_path_for
from noeticbraid_backend.settings import Settings

TASK_KEYS = {"task_id", "title", "state", "created_ts", "updated_ts", "modality_targets"}
LEDGER_KEYS = {"event_type", "state", "created_at"}
ARTIFACT_KEYS = {"modality", "rel_path", "sha256", "bytes", "download_url"}


def _client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[TestClient, Path]:
    data_root = tmp_path / "platform-data"
    monkeypatch.setenv("NOETICBRAID_PLATFORM_ENABLED", "1")
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(data_root))
    app = create_app(Settings(state_dir=tmp_path / "state"))
    return TestClient(app), data_root


def _token(data_root: Path, account: str) -> str:
    return TokenStore(data_root).create_token(account)


def _headers(token: str) -> dict[str, str]:
    return {"authorization": f"Bearer {token}"}


def test_platform_tasks_list_returns_owned_tasks_with_six_key_contract(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    account = "beta_user_01"
    client, data_root = _client(monkeypatch, tmp_path)
    token = _token(data_root, account)
    task = create_task(
        account,
        task_id="task_d16_list",
        title="Visible task",
        modality_targets=["document"],
        created_ts="2026-05-16T00:00:00+00:00",
    )
    foreign = Task(
        task_id="task_d16_foreign_ref",
        account_id_ref=account_ref_for("beta_user_02"),
        title="Foreign ref",
        state=TaskState.CREATED,
        created_ts="2026-05-16T00:00:00+00:00",
        updated_ts="2026-05-16T00:00:00+00:00",
        modality_targets=["document"],
    )
    foreign_path = task_path_for(account, foreign.task_id)
    foreign_path.parent.mkdir(parents=True, exist_ok=True)
    foreign_path.write_text(json.dumps(foreign.to_json_dict()), encoding="utf-8")

    response = client.get("/platform/tasks", headers=_headers(token))

    assert response.status_code == 200
    tasks = response.json()["tasks"]
    assert tasks == [
        {
            "task_id": task.task_id,
            "title": task.title,
            "state": task.state.value,
            "created_ts": task.created_ts,
            "updated_ts": task.updated_ts,
            "modality_targets": task.modality_targets,
        }
    ]
    assert all(set(item) == TASK_KEYS for item in tasks)
    assert "account_id_ref" not in response.text
    # SDD-D18 adds POST /platform/tasks as an additive conversational create route.
    create_response = client.post("/platform/tasks", headers=_headers(token), json={"title": "No fake"})
    assert create_response.status_code == 200
    assert set(create_response.json()["task"]) == TASK_KEYS


def test_platform_task_detail_projects_ledger_and_artifacts_without_raw_payload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    account = "beta_user_01"
    task_id = "task_d16_detail"
    client, data_root = _client(monkeypatch, tmp_path)
    token = _token(data_root, account)
    task = create_task(
        account,
        task_id=task_id,
        title="Detail task",
        modality_targets=["document"],
        created_ts="2026-05-16T01:00:00+00:00",
    )
    append_event(
        account,
        ai_call_event(
            task_id,
            op="webai_chatgpt_send_prompt",
            vendor="chatgpt",
            gate_status="ready",
            redacted_payload={"ok": True, "response_text": "redacted model text"},
            prompt_text="Prompt material must not be projected.",
            to_state=TaskState.BLOCKED,
        ),
    )
    artifact = persist(account, task_id, "document", b"# phase-d artifact\n")

    response = client.get(f"/platform/tasks/{task_id}", headers=_headers(token))

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"task", "ledger", "artifacts"}
    assert payload["task"] == {
        "task_id": task.task_id,
        "title": task.title,
        "state": task.state.value,
        "created_ts": task.created_ts,
        "updated_ts": task.updated_ts,
        "modality_targets": task.modality_targets,
    }
    assert set(payload["task"]) == TASK_KEYS
    assert payload["ledger"]
    assert all(set(item) == LEDGER_KEYS for item in payload["ledger"])
    rendered = json.dumps(payload, sort_keys=True)
    for forbidden in ("payload", "response_text", "prompt_sha256", "prompt_len"):
        assert forbidden not in rendered
    assert payload["artifacts"] == [
        {
            "modality": artifact.modality,
            "rel_path": artifact.rel_path,
            "sha256": artifact.sha256,
            "bytes": artifact.bytes,
            "download_url": f"/platform/tasks/{task_id}/artifacts/{artifact.artifact_id}",
        }
    ]
    assert all(set(item) == ARTIFACT_KEYS for item in payload["artifacts"])


def test_platform_task_reads_are_account_isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client, data_root = _client(monkeypatch, tmp_path)
    account_a = "beta_user_01"
    account_b = "beta_user_02"
    task_id = "task_d16_isolated"
    create_task(account_a, task_id=task_id, title="Private task", modality_targets=["document"])
    token_b = _token(data_root, account_b)

    list_response = client.get("/platform/tasks", headers=_headers(token_b))
    detail_response = client.get(f"/platform/tasks/{task_id}", headers=_headers(token_b))

    assert list_response.status_code == 200
    assert list_response.json() == {"tasks": []}
    assert detail_response.status_code == 404
    assert detail_response.json() == {"detail": "not_found"}


def test_platform_auth_session_is_opaque_until_env_account_is_valid(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    account = "beta_user_01"
    client, _data_root = _client(monkeypatch, tmp_path)
    create_task(account, task_id="task_d16_session", title="Session task", modality_targets=["document"])

    monkeypatch.delenv(PLATFORM_DEV_SESSION_ACCOUNT_ENV, raising=False)
    unset_response = client.post("/platform/auth/session")
    assert unset_response.status_code == 404
    assert unset_response.json() == {"detail": "not_found"}

    monkeypatch.setenv(PLATFORM_DEV_SESSION_ACCOUNT_ENV, "  ")
    empty_response = client.post("/platform/auth/session")
    assert empty_response.status_code == 404
    assert empty_response.json() == {"detail": "not_found"}

    monkeypatch.setenv(PLATFORM_DEV_SESSION_ACCOUNT_ENV, "bad/account")
    invalid_response = client.post("/platform/auth/session")
    assert invalid_response.status_code == 404
    assert invalid_response.json() == {"detail": "not_found"}

    monkeypatch.setenv(PLATFORM_DEV_SESSION_ACCOUNT_ENV, f" {account} ")
    issued_response = client.post("/platform/auth/session")
    assert issued_response.status_code == 200
    assert issued_response.json() == {"accepted": True, "mode": "platform_session_issued"}
    assert issued_response.headers["Cache-Control"] == "no-store"
    assert issued_response.headers["Pragma"] == "no-cache"
    assert issued_response.headers["Vary"] == "Authorization"
    token = issued_response.headers["X-NoeticBraid-Bearer"]
    assert require_platform_bearer(f"Bearer {token}") == account

    list_response = client.get("/platform/tasks", headers=_headers(token))
    assert list_response.status_code == 200
    assert [item["task_id"] for item in list_response.json()["tasks"]] == ["task_d16_session"]


def test_platform_tasks_list_tolerates_malformed_task_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    account = "beta_user_01"
    client, data_root = _client(monkeypatch, tmp_path)
    token = _token(data_root, account)
    good = create_task(account, task_id="task_d16_good", title="Good task", modality_targets=["document"])
    bad_path = task_path_for(account, "task_d16_bad")
    bad_path.parent.mkdir(parents=True, exist_ok=True)
    bad_path.write_text("{", encoding="utf-8")

    response = client.get("/platform/tasks", headers=_headers(token))

    assert response.status_code == 200
    assert response.json()["tasks"] == [
        {
            "task_id": good.task_id,
            "title": good.title,
            "state": good.state.value,
            "created_ts": good.created_ts,
            "updated_ts": good.updated_ts,
            "modality_targets": good.modality_targets,
        }
    ]

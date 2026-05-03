# SPDX-License-Identifier: Apache-2.0
"""Stage 2.3 Console read-API backend integration tests."""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parent.parent
SRC_ROOT = PACKAGE_ROOT / "src"
CORE_SRC_ROOT = REPO_ROOT / "packages" / "noeticbraid-core" / "src"
for path in (CORE_SRC_ROOT, SRC_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from fastapi.testclient import TestClient

from noeticbraid_backend.app import create_app
from noeticbraid_backend.approval.queue_store import ApprovalQueueStore
from noeticbraid_backend.auth.token_store import TokenStore
from noeticbraid_backend.settings import Settings
from noeticbraid_core.ledger import RunLedger
from noeticbraid_core.schemas import ApprovalRequest, RunRecord

EXPECTED_HEALTH = {"status": "ok", "contract_version": "1.2.0", "authoritative": True}
FORBIDDEN_PUBLIC_MARKERS = (
    "account_id",
    "token_id",
    "token_hash",
    "raw token",
    "bearer ",
    "dpapi",
    "credential",
    "private/",
    "browser profile",
    "profile_path",
    "profile_dir",
    "startup secret",
)


def _settings_for_state(state_dir: Path) -> Settings:
    return Settings(state_dir=state_dir, dpapi_blob_path=None)


def _client_for_state(state_dir: Path) -> TestClient:
    return TestClient(create_app(_settings_for_state(state_dir)))


def _approval(
    approval_id: str,
    *,
    approval_level: str = "strong",
    requested_action: str = "summarize_project_note",
    reason: str = "requires user decision",
    diff_ref: str | None = None,
    status: str = "pending",
) -> ApprovalRequest:
    return ApprovalRequest(
        approval_id=approval_id,
        task_id="task_console_read_api",
        run_id="run_console_read_api",
        approval_level=approval_level,
        requested_at=datetime(2026, 5, 2, 12, 0, 0, tzinfo=timezone.utc),
        requested_action=requested_action,
        reason=reason,
        diff_ref=diff_ref,
        status=status,
    )


def _run(run_id: str = "run_console_read_api") -> RunRecord:
    return RunRecord(
        run_id=run_id,
        task_id="task_console_read_api",
        event_type="task_created",
        created_at=datetime(2026, 5, 2, 12, 0, 0, tzinfo=timezone.utc),
        actor="system",
        model_refs=[],
        source_refs=[],
        artifact_refs=[],
        routing_advice=None,
        status="recorded",
    )


def _seed_ledger(tmp_path: Path, *records: RunRecord) -> RunLedger:
    ledger = RunLedger(root=tmp_path)
    for record in records:
        ledger.append(record)
    return ledger


def _sqlite_schema_names(path: Path) -> tuple[str, ...]:
    with sqlite3.connect(path) as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'index') ORDER BY name").fetchall()
    return tuple(str(row[0]) for row in rows)


def _assert_no_forbidden_public_material(payload: object) -> None:
    rendered = json.dumps(payload, sort_keys=True).lower()
    for marker in FORBIDDEN_PUBLIC_MARKERS:
        assert marker not in rendered


def test_health_returns_ok_without_creating_missing_state_dir(tmp_path: Path) -> None:
    state_dir = tmp_path / "missing-state"

    response = _client_for_state(state_dir).get("/api/health")

    assert response.status_code == 200
    assert response.json() == EXPECTED_HEALTH
    assert list(response.json().keys()) == ["status", "contract_version", "authoritative"]
    assert not state_dir.exists()


def test_health_tolerates_empty_sqlite_and_corrupt_approval_queue_without_schema_mutation(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    token_store_path = state_dir / "auth" / "tokens.sqlite"
    token_store_path.parent.mkdir(parents=True)
    sqlite3.connect(token_store_path).close()
    approval_queue_path = state_dir / "approval" / "queue.jsonl"
    approval_queue_path.parent.mkdir(parents=True)
    approval_queue_path.write_text("{not valid json\n", encoding="utf-8")
    before_schema = _sqlite_schema_names(token_store_path)

    response = _client_for_state(state_dir).get("/api/health")

    assert response.status_code == 200
    assert response.json() == EXPECTED_HEALTH
    assert _sqlite_schema_names(token_store_path) == before_schema


def test_health_returns_ok_with_seeded_ledger_token_store_and_approval_queue(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    TokenStore(state_dir).create_token("account_local")
    ApprovalQueueStore(state_dir).append(_approval("approval_health_seeded"))
    _seed_ledger(tmp_path, _run("run_health_seeded"))

    response = _client_for_state(state_dir).get("/api/health")

    assert response.status_code == 200
    assert response.json() == EXPECTED_HEALTH


def test_dashboard_empty_state_keeps_phase1_1_fixture_shape(tmp_path: Path) -> None:
    response = _client_for_state(tmp_path / "state").get("/api/dashboard/empty")

    assert response.status_code == 200
    assert response.json() == {"tasks": [], "approvals": [], "accounts": []}
    assert list(response.json().keys()) == ["tasks", "approvals", "accounts"]


def test_dashboard_returns_safe_pending_approvals_and_keeps_accounts_empty(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    store = ApprovalQueueStore(state_dir)
    store.append(_approval("approval_dashboard_public"))
    store.append(_approval("approval_dashboard_resolved", status="approved"))

    response = _client_for_state(state_dir).get("/api/dashboard/empty")

    assert response.status_code == 200
    body = response.json()
    assert list(body.keys()) == ["tasks", "approvals", "accounts"]
    assert body["tasks"] == []
    assert body["accounts"] == []
    assert [approval["approval_id"] for approval in body["approvals"]] == ["approval_dashboard_public"]
    ApprovalRequest.model_validate(body["approvals"][0])
    _assert_no_forbidden_public_material(body)


def test_dashboard_omits_sensitive_approval_rows_from_public_summary(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    store = ApprovalQueueStore(state_dir)
    store.append(_approval("approval_dashboard_public"))
    store.append(
        _approval(
            "approval_dashboard_sensitive",
            requested_action="rotate_credential",
            reason="contains credential path private/profile-details",
        )
    )

    response = _client_for_state(state_dir).get("/api/dashboard/empty")

    assert response.status_code == 200
    body = response.json()
    assert [approval["approval_id"] for approval in body["approvals"]] == ["approval_dashboard_public"]
    _assert_no_forbidden_public_material(body)


def test_dashboard_omits_reason_values_with_forbidden_key_literals(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    store = ApprovalQueueStore(state_dir)
    store.append(_approval("approval_dashboard_public"))
    store.append(_approval("approval_dashboard_account_marker", reason='contains account_id="account_local"'))
    store.append(_approval("approval_dashboard_token_marker", reason='contains token_id="tok_abc123"'))
    store.append(_approval("approval_dashboard_raw_token_marker", reason="contains raw_token material"))
    store.append(_approval("approval_dashboard_dpapi_marker", reason="contains dpapi_blob material"))

    response = _client_for_state(state_dir).get("/api/dashboard/empty")

    assert response.status_code == 200
    body = response.json()
    assert [approval["approval_id"] for approval in body["approvals"]] == ["approval_dashboard_public"]
    _assert_no_forbidden_public_material(body)


def test_dashboard_omits_forbidden_or_path_shaped_diff_refs(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    store = ApprovalQueueStore(state_dir)
    store.append(_approval("approval_dashboard_git_sha", diff_ref="0123456789abcdef0123456789abcdef01234567"))
    store.append(_approval("approval_dashboard_diff_token", diff_ref='token_id="tok_abc123"'))
    store.append(
        _approval(
            "approval_dashboard_diff_path",
            diff_ref=r"C:\Users\alice\AppData\Local\NoeticBraid\profile_dir\diff.patch",
        )
    )

    response = _client_for_state(state_dir).get("/api/dashboard/empty")

    assert response.status_code == 200
    body = response.json()
    assert [approval["approval_id"] for approval in body["approvals"]] == ["approval_dashboard_git_sha"]
    ApprovalRequest.model_validate(body["approvals"][0])
    _assert_no_forbidden_public_material(body)


def test_workspace_threads_default_empty_and_do_not_synthesize_from_ledger_runs(tmp_path: Path) -> None:
    _seed_ledger(tmp_path, _run("run_workspace_seeded"))

    response = _client_for_state(tmp_path / "state").get("/api/workspace/threads")

    assert response.status_code == 200
    assert response.json() == {"threads": []}
    assert list(response.json().keys()) == ["threads"]


def test_existing_stage2_read_routes_preserve_contract_wrappers(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    ApprovalQueueStore(state_dir).append(_approval("approval_read_compatibility"))
    _seed_ledger(tmp_path, _run("run_read_compatibility"))
    bearer = TokenStore(state_dir).create_token("account_local")
    client = _client_for_state(state_dir)

    ledger_response = client.get("/api/ledger/runs")
    approval_response = client.get("/api/approval/queue")
    account_response = client.get("/api/account/pool", headers={"Authorization": f"Bearer {bearer}"})

    assert ledger_response.status_code == 200
    assert list(ledger_response.json().keys()) == ["runs"]
    assert [record["run_id"] for record in ledger_response.json()["runs"]] == ["run_read_compatibility"]
    RunRecord.model_validate(ledger_response.json()["runs"][0])

    assert approval_response.status_code == 200
    assert list(approval_response.json().keys()) == ["approvals"]
    assert [record["approval_id"] for record in approval_response.json()["approvals"]] == [
        "approval_read_compatibility"
    ]
    ApprovalRequest.model_validate(approval_response.json()["approvals"][0])

    assert account_response.status_code == 200
    assert account_response.json() == {"profiles": []}
    _assert_no_forbidden_public_material(account_response.json())

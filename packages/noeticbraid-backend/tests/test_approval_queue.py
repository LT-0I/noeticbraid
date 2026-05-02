# SPDX-License-Identifier: Apache-2.0
"""Approval queue storage and route tests."""

from __future__ import annotations

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
from noeticbraid_backend.settings import Settings
from noeticbraid_core.schemas import ApprovalRequest


def _settings(tmp_path: Path) -> Settings:
    return Settings(state_dir=tmp_path / "state", dpapi_blob_path=None)


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(_settings(tmp_path)))


def _approval(
    approval_id: str,
    *,
    approval_level: str = "strong",
    requested_action: str = "delete_local_file",
    status: str = "pending",
) -> ApprovalRequest:
    return ApprovalRequest(
        approval_id=approval_id,
        task_id="task_approval_queue",
        run_id="run_approval_queue",
        approval_level=approval_level,
        requested_at=datetime(2026, 5, 2, 12, 0, 0, tzinfo=timezone.utc),
        requested_action=requested_action,
        reason="requires user decision",
        diff_ref=None,
        status=status,
    )


def test_approval_queue_route_returns_empty_wrapper_for_missing_store(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/api/approval/queue")

    assert response.status_code == 200
    assert response.json() == {"approvals": []}


def test_approval_queue_route_returns_pending_user_decision_records(tmp_path: Path) -> None:
    store = ApprovalQueueStore(_settings(tmp_path).state_dir)
    store.append(_approval("approval_pending"))

    response = _client(tmp_path).get("/api/approval/queue")

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"approvals"}
    assert len(body["approvals"]) == 1
    assert body["approvals"][0]["approval_id"] == "approval_pending"
    ApprovalRequest.model_validate(body["approvals"][0])


def test_approval_queue_filters_resolved_none_forbidden_and_red_line_records(tmp_path: Path) -> None:
    store = ApprovalQueueStore(_settings(tmp_path).state_dir)
    store.append(_approval("approval_pending"))
    store.append(_approval("approval_approved", status="approved"))
    store.append(_approval("approval_none", approval_level="none"))
    store.append(_approval("approval_forbidden", approval_level="forbidden"))
    store.append(_approval("approval_redline", requested_action="write_user_raw_vault"))

    response = _client(tmp_path).get("/api/approval/queue")

    assert response.status_code == 200
    assert [row["approval_id"] for row in response.json()["approvals"]] == ["approval_pending"]


def test_approval_queue_skips_corrupted_rows_without_500(tmp_path: Path) -> None:
    store = ApprovalQueueStore(_settings(tmp_path).state_dir)
    store.append(_approval("approval_good_001"))
    with store.path.open("a", encoding="utf-8") as fh:
        fh.write("{this is not valid json\n")
    store.append(_approval("approval_good_002"))

    response = _client(tmp_path).get("/api/approval/queue")

    assert response.status_code == 200
    assert [row["approval_id"] for row in response.json()["approvals"]] == [
        "approval_good_001",
        "approval_good_002",
    ]

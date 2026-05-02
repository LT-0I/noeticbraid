# SPDX-License-Identifier: Apache-2.0
"""Stage 2.4 one-app integration smoke over all seven OpenAPI 1.1.0 endpoints."""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parent.parent
SRC_ROOT = PACKAGE_ROOT / "src"
CORE_SRC_ROOT = REPO_ROOT / "packages" / "noeticbraid-core" / "src"
for path in (CORE_SRC_ROOT, SRC_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from noeticbraid_backend.app import create_app
from noeticbraid_backend.approval.queue_store import ApprovalQueueStore
from noeticbraid_backend.auth.token_store import TokenStore
from noeticbraid_backend.contracts import (
    AccountPoolDraft,
    ApprovalQueue,
    AuthResponse,
    EmptyDashboard,
    HealthResponse,
    RunLedgerRuns,
    WorkspaceThreads,
)
from noeticbraid_backend.settings import Settings
from noeticbraid_core.ledger import RunLedger
from noeticbraid_core.schemas import ApprovalRequest, RunRecord

FORBIDDEN_PUBLIC_MARKERS = (
    "cookie_value",
    "cookie_jar_path",
    "csrf_token",
    "session_token",
    "encrypted_password",
    "browser_session_id",
    "raw_token",
    "token_hash",
    "dpapi_blob",
    "credential_path",
    "profile_path",
    "profile_dir",
    "account_id",
    "profile_id",
    "quota_window",
    "private/",
    "\\private\\",
)

WRAPPER_EXPECTATIONS = {
    "health": (HealthResponse, ("status", "contract_version", "authoritative")),
    "auth": (AuthResponse, ("accepted", "mode")),
    "dashboard": (EmptyDashboard, ("tasks", "approvals", "accounts")),
    "workspace": (WorkspaceThreads, ("threads",)),
    "approval": (ApprovalQueue, ("approvals",)),
    "account": (AccountPoolDraft, ("profiles",)),
    "ledger": (RunLedgerRuns, ("runs",)),
}


def _seeded_run_record() -> RunRecord:
    return RunRecord(
        run_id="run_stage2_4_smoke",
        task_id="task_stage2_4_smoke",
        event_type="task_created",
        created_at=datetime(2026, 5, 2, 12, 24, 0, tzinfo=timezone.utc),
        actor="system",
        model_refs=[],
        source_refs=[],
        artifact_refs=[],
        routing_advice=None,
        status="recorded",
    )


def _seeded_approval_request() -> ApprovalRequest:
    return ApprovalRequest(
        approval_id="approval_stage2_4_smoke",
        task_id="task_stage2_4_smoke",
        run_id="run_stage2_4_smoke",
        approval_level="strong",
        requested_at=datetime(2026, 5, 2, 12, 25, 0, tzinfo=timezone.utc),
        requested_action="summarize_project_note",
        reason="requires user decision",
        diff_ref="0123456789abcdef0123456789abcdef01234567",
        status="pending",
    )


def _seed_local_state(tmp_path: Path, state_dir: Path) -> tuple[RunRecord, ApprovalRequest, str]:
    run_record = _seeded_run_record()
    approval_request = _seeded_approval_request()
    RunLedger(root=tmp_path).append(run_record)
    ApprovalQueueStore(state_dir).append(approval_request)
    bearer = TokenStore(state_dir).create_token("stage2_4_smoke")
    return run_record, approval_request, bearer


def _assert_wrapper(name: str, body: dict[str, Any]) -> None:
    model, expected_fields = WRAPPER_EXPECTATIONS[name]
    assert tuple(body.keys()) == expected_fields
    model.model_validate(body)
    _assert_no_forbidden_public_material(body)


def _assert_no_forbidden_public_material(payload: object) -> None:
    rendered = json.dumps(payload, sort_keys=True).lower()
    for marker in FORBIDDEN_PUBLIC_MARKERS:
        assert marker not in rendered


async def _run_one_app_seven_endpoint_smoke(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    seeded_run, seeded_approval, bearer = _seed_local_state(tmp_path, state_dir)
    settings = Settings(state_dir=state_dir, dpapi_blob_path=None)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://stage2-4-smoke") as client:
        responses = {
            "health": await client.get("/api/health"),
            "auth": await client.post("/api/auth/startup_token"),
            "dashboard": await client.get("/api/dashboard/empty"),
            "workspace": await client.get("/api/workspace/threads"),
            "approval": await client.get("/api/approval/queue"),
            "account": await client.get("/api/account/pool", headers={"Authorization": f"Bearer {bearer}"}),
            "ledger": await client.get("/api/ledger/runs"),
        }

    assert responses["auth"].request.content == b""
    for name, response in responses.items():
        assert response.status_code == 200, name
        body = response.json()
        assert isinstance(body, dict), name
        _assert_wrapper(name, body)

    ledger_body = responses["ledger"].json()
    matching_runs = [
        RunRecord.model_validate(record)
        for record in ledger_body["runs"]
        if record.get("run_id") == seeded_run.run_id
    ]
    assert matching_runs, "seeded RunRecord was not returned from /api/ledger/runs"
    assert matching_runs[0].task_id == seeded_run.task_id
    assert matching_runs[0].status == seeded_run.status

    approval_body = responses["approval"].json()
    matching_approvals = [
        ApprovalRequest.model_validate(record)
        for record in approval_body["approvals"]
        if record.get("approval_id") == seeded_approval.approval_id
    ]
    assert matching_approvals, "seeded ApprovalRequest was not returned from /api/approval/queue"
    assert matching_approvals[0].run_id == seeded_approval.run_id
    assert matching_approvals[0].status == seeded_approval.status


def test_stage2_4_one_app_seven_endpoint_contract_smoke(tmp_path: Path) -> None:
    asyncio.run(_run_one_app_seven_endpoint_smoke(tmp_path))

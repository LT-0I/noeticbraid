# SPDX-License-Identifier: Apache-2.0
"""Contract route smoke tests for all seven frozen Phase 1.2 v1.1.0 paths."""

from __future__ import annotations

import hashlib
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
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
from noeticbraid_backend.auth.token_store import TokenStore, utc_now
from noeticbraid_backend.contracts import ALL_SCHEMA_NAMES, CONTRACT_VERSION, FROZEN_ROUTE_SPECS
from noeticbraid_backend.settings import Settings
from noeticbraid_core.ledger import RunLedger
from noeticbraid_core.schemas import RunRecord

FROZEN_OPENAPI_PATH = REPO_ROOT / "docs" / "contracts" / "phase1_2_openapi.yaml"
FROZEN_OPENAPI_SHA256 = "0667bdec52cb4fe958d526bd171d43b21ecf92a2b2b56eef53c11bb0cb818438"
EXPECTED_RUN_RECORD_FIELDS = (
    "run_id",
    "task_id",
    "event_type",
    "created_at",
    "actor",
    "model_refs",
    "source_refs",
    "artifact_refs",
    "routing_advice",
    "status",
)

EXPECTED_FIXTURES = {
    ("GET", "/api/health"): {
        "status": "ok",
        "contract_version": "1.1.0",
        "authoritative": True,
    },
    ("POST", "/api/auth/startup_token"): {
        "accepted": False,
        "mode": "startup_credential_unavailable",
    },
    ("GET", "/api/dashboard/empty"): {"tasks": [], "approvals": [], "accounts": []},
    ("GET", "/api/workspace/threads"): {"threads": []},
    ("GET", "/api/approval/queue"): {"approvals": []},
    ("GET", "/api/account/pool"): {"profiles": []},
    ("GET", "/api/ledger/runs"): {"runs": []},
}


def make_record(
    run_id: str,
    task_id: str,
    created_at: datetime | None = None,
) -> RunRecord:
    return RunRecord(
        run_id=run_id,
        task_id=task_id,
        event_type="task_created",
        created_at=created_at or datetime(2026, 5, 2, 12, 0, 0, tzinfo=timezone.utc),
        actor="system",
        model_refs=[],
        source_refs=[],
        artifact_refs=[],
        routing_advice=None,
        status="recorded",
    )


def _settings(tmp_path: Path) -> Settings:
    return Settings(state_dir=tmp_path / "state", dpapi_blob_path=None)


def _client(tmp_path: Path) -> TestClient:
    app = create_app(_settings(tmp_path))
    return TestClient(app)


def _token_store(tmp_path: Path) -> TokenStore:
    return TokenStore(_settings(tmp_path).state_dir)


def _bearer_headers(tmp_path: Path, account_id: str = "account_local") -> dict[str, str]:
    token = _token_store(tmp_path).create_token(account_id)
    return {"Authorization": f"Bearer {token}"}


def _seed_ledger(tmp_path: Path, *records: RunRecord) -> RunLedger:
    ledger = RunLedger(root=tmp_path)
    for record in records:
        ledger.append(record)
    return ledger


def test_all_frozen_routes_return_expected_contract_bodies(tmp_path: Path) -> None:
    client = _client(tmp_path)
    for spec in FROZEN_ROUTE_SPECS:
        method = spec["method"]
        path = spec["path"]
        headers = _bearer_headers(tmp_path) if path == "/api/account/pool" else None
        response = client.request(method, path, headers=headers)
        assert response.status_code == 200
        assert response.json() == EXPECTED_FIXTURES[(method, path)]


def test_account_pool_requires_bearer_and_preserves_profiles_only(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/api/account/pool")

    assert response.status_code == 401
    assert response.json() == {"detail": "unauthorized"}
    assert "profile_records" not in str(response.json())


def test_account_pool_rejects_malformed_revoked_and_expired_bearers(tmp_path: Path) -> None:
    client = _client(tmp_path)
    store = _token_store(tmp_path)

    malformed = client.get("/api/account/pool", headers={"Authorization": "Basic not-bearer"})
    assert malformed.status_code == 401
    assert malformed.json() == {"detail": "unauthorized"}

    revoked_token = store.create_token("account_local")
    revoked_record = store.verify_token(revoked_token)
    assert revoked_record is not None
    assert store.revoke_token(revoked_record.token_id) is True
    revoked = client.get("/api/account/pool", headers={"Authorization": f"Bearer {revoked_token}"})
    assert revoked.status_code == 401
    assert revoked.json() == {"detail": "unauthorized"}

    expired_token = store.create_token("account_local")
    expired_record = store.verify_token(expired_token)
    assert expired_record is not None
    with sqlite3.connect(store.path) as conn:
        conn.execute(
            "UPDATE tokens SET expires_at = ? WHERE token_id = ?",
            ((utc_now() - timedelta(minutes=1)).isoformat(), expired_record.token_id),
        )
        conn.commit()
    expired = client.get("/api/account/pool", headers={"Authorization": f"Bearer {expired_token}"})
    assert expired.status_code == 401
    assert expired.json() == {"detail": "unauthorized"}

    for body in (malformed.json(), revoked.json(), expired.json()):
        rendered = str(body).lower()
        assert "token_hash" not in rendered
        assert "dpapi" not in rendered
        assert "credential" not in rendered


def test_account_pool_accepts_valid_bearer_and_has_no_secret_fields(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/api/account/pool", headers=_bearer_headers(tmp_path))

    assert response.status_code == 200
    assert response.json() == {"profiles": []}
    assert set(response.json()) == {"profiles"}
    assert "profile_records" not in response.json()


def test_runtime_openapi_has_no_bearer_security_or_authorization_parameter(tmp_path: Path) -> None:
    schema = _client(tmp_path).app.openapi()

    assert "securitySchemes" not in schema.get("components", {})
    for path_item in schema["paths"].values():
        for operation in path_item.values():
            assert "security" not in operation
    account_operation = schema["paths"]["/api/account/pool"]["get"]
    parameters = account_operation.get("parameters", [])
    assert all(parameter.get("name") != "Authorization" for parameter in parameters)


def test_ledger_route_returns_empty_runs_for_missing_state_ledger(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/api/ledger/runs")

    assert response.status_code == 200
    assert response.json() == {"runs": []}
    assert not (tmp_path / "state" / "ledger" / "run_ledger.jsonl").exists()


def test_ledger_route_returns_seeded_run_records_from_configured_state_dir(tmp_path: Path) -> None:
    _seed_ledger(
        tmp_path,
        make_record("run_alpha", "task_alpha", datetime(2026, 5, 2, 12, 0, 0, tzinfo=timezone.utc)),
        make_record("run_bravo", "task_bravo", datetime(2026, 5, 2, 12, 1, 0, tzinfo=timezone.utc)),
    )

    response = _client(tmp_path).get("/api/ledger/runs")

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"runs"}
    assert [record["run_id"] for record in body["runs"]] == ["run_alpha", "run_bravo"]
    assert len(body["runs"]) == 2
    for record in body["runs"]:
        assert tuple(record.keys()) == EXPECTED_RUN_RECORD_FIELDS
        RunRecord.model_validate(record)


def test_ledger_route_skips_corrupted_jsonl_without_500(tmp_path: Path) -> None:
    ledger = _seed_ledger(tmp_path, make_record("run_good_001", "task_good_001"))
    with open(ledger.path, "a", encoding="utf-8") as fh:
        fh.write("{this is not valid json\n")
    ledger.append(make_record("run_good_002", "task_good_002"))

    response = _client(tmp_path).get("/api/ledger/runs")

    assert response.status_code == 200
    body = response.json()
    assert [record["run_id"] for record in body["runs"]] == ["run_good_001", "run_good_002"]
    for record in body["runs"]:
        RunRecord.model_validate(record)


def test_openapi_has_seven_paths_and_expected_response_schemas(tmp_path: Path) -> None:
    schema = _client(tmp_path).app.openapi()
    assert set(schema["paths"].keys()) == {spec["path"] for spec in FROZEN_ROUTE_SPECS}
    for spec in FROZEN_ROUTE_SPECS:
        operation = schema["paths"][spec["path"]][spec["method"].lower()]
        assert operation["summary"] == spec["summary"]
        ref = operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
        assert ref == f"#/components/schemas/{spec['response_schema']}"


def test_runtime_metadata_and_ledger_operation_match_phase1_2_contract(tmp_path: Path) -> None:
    schema = _client(tmp_path).app.openapi()
    assert schema["openapi"] == "3.1.0"
    assert schema["info"]["title"] == "NoeticBraid Phase 1.2 API"
    assert schema["info"]["version"] == "1.1.0"
    assert schema["info"]["x-contract-version"] == "1.1.0"
    assert schema["info"]["x-status"] == "AUTHORITATIVE"
    assert schema["info"]["x-frozen"] is True
    assert CONTRACT_VERSION == "1.1.0"

    operation = schema["paths"]["/api/ledger/runs"]["get"]
    assert operation["tags"] == ["ledger"]
    assert operation["summary"] == "List run records"
    assert operation["operationId"] == "ledger_runs_api_ledger_runs_get"
    assert (
        operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
        == "#/components/schemas/RunLedgerRuns"
    )


def test_thirteen_schema_names_are_referenced_by_contract_helpers() -> None:
    assert ALL_SCHEMA_NAMES == (
        "HealthResponse",
        "AuthResponse",
        "EmptyDashboard",
        "WorkspaceThreads",
        "ApprovalQueue",
        "AccountPoolDraft",
        "RunLedgerRuns",
        "Task",
        "RunRecord",
        "SourceRecord",
        "ApprovalRequest",
        "SideNote",
        "DigestionItem",
    )


def test_openapi_components_contain_all_thirteen_schemas(tmp_path: Path) -> None:
    schema = _client(tmp_path).app.openapi()
    components = schema["components"]["schemas"]
    missing = set(ALL_SCHEMA_NAMES) - set(components.keys())
    assert set(ALL_SCHEMA_NAMES).issubset(components.keys()), f"missing: {missing}"
    assert "status" in components["HealthResponse"]["properties"]
    assert "accepted" in components["AuthResponse"]["properties"]
    assert "profiles" in components["AccountPoolDraft"]["properties"]
    assert "runs" in components["RunLedgerRuns"]["properties"]
    assert "threads" in components["WorkspaceThreads"]["properties"]
    assert "approvals" in components["ApprovalQueue"]["properties"]
    assert "tasks" in components["EmptyDashboard"]["properties"]


def test_frozen_openapi_1_1_0_yaml_anchors_and_sha_are_unchanged() -> None:
    contract_bytes = FROZEN_OPENAPI_PATH.read_bytes()
    assert hashlib.sha256(contract_bytes).hexdigest() == FROZEN_OPENAPI_SHA256
    contract = contract_bytes.decode("utf-8")
    for anchor in (
        "openapi: 3.1.0",
        "title: NoeticBraid Phase 1.2 API",
        "version: 1.1.0",
        "x-contract-version: 1.1.0",
        "x-status: AUTHORITATIVE",
        "x-frozen: true",
        "  /api/auth/startup_token:",
        "      operationId: startup_token_api_auth_startup_token_post",
        "                $ref: '#/components/schemas/AuthResponse'",
        "  /api/approval/queue:",
        "      operationId: approval_queue_api_approval_queue_get",
        "                $ref: '#/components/schemas/ApprovalQueue'",
        "  /api/account/pool:",
        "      operationId: account_pool_api_account_pool_get",
        "                $ref: '#/components/schemas/AccountPoolDraft'",
        "    AuthResponse:",
        "    ApprovalQueue:",
        "    ApprovalRequest:",
        "    AccountPoolDraft:",
        "    RunLedgerRuns:",
        "    RunRecord:",
        "    SourceRecord:",
    ):
        assert anchor in contract
    startup_section = contract.split("  /api/auth/startup_token:", 1)[1].split("  /api/dashboard/empty:", 1)[0]
    assert "requestBody" not in startup_section
    assert "securitySchemes" not in contract
    assert "security:" not in contract
    for schema_name in ALL_SCHEMA_NAMES:
        assert f"    {schema_name}:" in contract

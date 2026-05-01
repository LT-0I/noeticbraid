# SPDX-License-Identifier: Apache-2.0
"""Contract route smoke tests for all seven frozen v1.0.0 paths."""

from __future__ import annotations

import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PACKAGE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from fastapi.testclient import TestClient

from noeticbraid_backend.app import create_app
from noeticbraid_backend.contracts import ALL_SCHEMA_NAMES, FROZEN_ROUTE_SPECS
from noeticbraid_backend.settings import Settings

EXPECTED_FIXTURES = {
    ("GET", "/api/health"): {
        "status": "ok",
        "contract_version": "1.0.0",
        "authoritative": True,
    },
    ("POST", "/api/auth/startup_token"): {"accepted": False, "mode": "stage1_skeleton"},
    ("GET", "/api/dashboard/empty"): {"tasks": [], "approvals": [], "accounts": []},
    ("GET", "/api/workspace/threads"): {"threads": []},
    ("GET", "/api/approval/queue"): {"approvals": []},
    ("GET", "/api/account/pool"): {"profiles": []},
    ("GET", "/api/ledger/runs"): {"runs": []},
}


def _client(tmp_path: Path) -> TestClient:
    app = create_app(Settings(state_dir=tmp_path / "state", dpapi_blob_path=None))
    return TestClient(app)


def test_all_frozen_routes_return_200_and_exact_fixtures(tmp_path: Path) -> None:
    client = _client(tmp_path)
    for spec in FROZEN_ROUTE_SPECS:
        method = spec["method"]
        path = spec["path"]
        response = client.request(method, path)
        assert response.status_code == 200
        assert response.json() == EXPECTED_FIXTURES[(method, path)]


def test_account_pool_preserves_v1_0_0_profiles_only(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/api/account/pool")
    assert response.status_code == 200
    assert response.json() == {"profiles": []}
    assert "profile_records" not in response.json()


def test_openapi_has_seven_paths_and_expected_response_schemas(tmp_path: Path) -> None:
    schema = _client(tmp_path).app.openapi()
    assert set(schema["paths"].keys()) == {spec["path"] for spec in FROZEN_ROUTE_SPECS}
    for spec in FROZEN_ROUTE_SPECS:
        operation = schema["paths"][spec["path"]][spec["method"].lower()]
        assert operation["summary"] == spec["summary"]
        ref = operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
        assert ref == f"#/components/schemas/{spec['response_schema']}"


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


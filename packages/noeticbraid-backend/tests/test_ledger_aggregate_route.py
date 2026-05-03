# SPDX-License-Identifier: Apache-2.0
"""Ledger aggregate route smoke tests for contract 1.2.0."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parent.parent
SRC_ROOT = PACKAGE_ROOT / "src"
CORE_SRC_ROOT = REPO_ROOT / "packages" / "noeticbraid-core" / "src"
for path in (CORE_SRC_ROOT, SRC_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from noeticbraid_backend.app import create_app
from noeticbraid_backend.settings import Settings
from noeticbraid_core.schemas import RunRecordAggregate


def _client(tmp_path: Path) -> TestClient:
    app = create_app(Settings(state_dir=tmp_path / "state", dpapi_blob_path=None))
    return TestClient(app)


def test_aggregate_endpoint_smoke(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/api/ledger/runs/aggregate?run_id=run_test01")

    assert response.status_code in {200, 404}
    if response.status_code == 200:
        aggregate = RunRecordAggregate.model_validate(response.json())
        assert aggregate.run_id == "run_test01"


def test_aggregate_endpoint_invalid_run_id(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/api/ledger/runs/aggregate?run_id=invalid-uuid-xxx")

    assert response.status_code == 422

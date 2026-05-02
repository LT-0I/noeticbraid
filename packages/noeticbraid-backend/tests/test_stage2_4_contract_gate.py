# SPDX-License-Identifier: Apache-2.0
"""Stage 2.4 contract sidecar, frozen OpenAPI, and runtime OpenAPI gates."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parent.parent
SRC_ROOT = PACKAGE_ROOT / "src"
CORE_SRC_ROOT = REPO_ROOT / "packages" / "noeticbraid-core" / "src"
for path in (CORE_SRC_ROOT, SRC_ROOT, REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

_GATE_PATH = REPO_ROOT / "scripts" / "check_phase1_2_contract_gate.py"
_SPEC = importlib.util.spec_from_file_location("check_phase1_2_contract_gate", _GATE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
contract_gate = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = contract_gate
_SPEC.loader.exec_module(contract_gate)

EXPECTED_PATHS = (
    "/api/health",
    "/api/auth/startup_token",
    "/api/dashboard/empty",
    "/api/workspace/threads",
    "/api/approval/queue",
    "/api/account/pool",
    "/api/ledger/runs",
)
EXPECTED_SCHEMAS = {
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
}


def test_stage2_4_contract_gate_runs_mechanical_sidecar_and_runtime_checks() -> None:
    report = contract_gate.run_checks(REPO_ROOT)

    assert report.contract_sha256 == report.sidecar_sha256
    assert len(report.contract_sha256) == 64
    assert report.frozen_paths == EXPECTED_PATHS
    assert report.runtime_paths == EXPECTED_PATHS
    assert set(report.runtime_schema_names) == EXPECTED_SCHEMAS


def test_sidecar_parser_rejects_non_sidecar_format() -> None:
    bad_sidecar = b"0667BDEC52CB4FE958D526BD171D43B21ECF92A2B2B56EEF53C11BB0CB818438 phase1_2_openapi.yaml\n"

    try:
        contract_gate.parse_sidecar(bad_sidecar)
    except AssertionError as exc:
        assert "phase1_2_openapi.yaml.sha256" in str(exc)
    else:  # pragma: no cover - explicit failure branch for pytest output
        raise AssertionError("invalid sidecar format was accepted")

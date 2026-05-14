# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parent.parent
for path in (
    REPO_ROOT / "packages" / "noeticbraid-core" / "src",
    REPO_ROOT / "packages" / "noeticbraid-multimodel-alliance" / "src",
    PACKAGE_ROOT / "src",
):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from noeticbraid_backend.app import create_app
from noeticbraid_backend.settings import Settings
from noeticbraid_core.r6_gate import R6GateState, evaluate_r6_gate

FIXTURES = Path(__file__).resolve().parent / "fixtures"
FIXTURE_OMC_SOURCES = [
    (FIXTURES / "omc_source_claude_md_sample.md", "tests/fixtures/omc_source_claude_md_sample.md"),
    (FIXTURES / "omc_source_rtk_md_sample.md", "tests/fixtures/omc_source_rtk_md_sample.md"),
]
SEED_ID = "memory_omc_help_lesson"


def _client(tmp_path: Path) -> TestClient:
    return TestClient(
        create_app(Settings(state_dir=tmp_path / "state", dpapi_blob_path=None, omc_sources=FIXTURE_OMC_SOURCES))
    )


def _task_card() -> dict[str, object]:
    return json.loads((FIXTURES / "omc_task_card.json").read_text(encoding="utf-8"))


def _seed_from(client: TestClient) -> dict[str, object]:
    response = client.get("/api/projects/omc-ingest/candidates")
    assert response.status_code == 200, response.text
    candidates = response.json()["candidates"]
    return next(candidate for candidate in candidates if candidate["candidate_id"] == SEED_ID)


def _adopted_seed_from(client: TestClient) -> dict[str, object]:
    response = client.get("/api/projects/omc-ingest/adopted-history")
    assert response.status_code == 200, response.text
    adopted = response.json()["adopted_candidates"]
    return next(candidate for candidate in adopted if candidate["candidate_id"] == SEED_ID)


def _ledger_rows(tmp_path: Path) -> list[dict[str, object]]:
    ledger_path = tmp_path / "state" / "ledger" / "run_ledger.jsonl"
    return [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_three_omc_task_submits_confirm_seed_reuse_gate(tmp_path: Path) -> None:
    client = _client(tmp_path)

    run_refs: list[str] = []
    for expected_count in (1, 2, 3):
        response = client.post("/api/projects/omc-ingest/tasks", json=_task_card())

        assert response.status_code == 200, response.text
        body = response.json()
        assert "reused_lesson_refs" not in body
        run_refs.append(body["run_record_ref"])
        seed = _seed_from(client)
        assert seed["r6_gate"]["reuse_count"] == expected_count
        assert len(seed["r6_gate"]["ledger_evidence_refs"]) == expected_count

    seed = _seed_from(client)
    ledger_refs = seed["r6_gate"]["ledger_evidence_refs"]
    assert len(ledger_refs) == 3
    assert len(set(ledger_refs)) == 3
    assert ledger_refs == run_refs
    assert evaluate_r6_gate(R6GateState.model_validate(seed["r6_gate"])) == "confirmed"
    adopted_seed = _adopted_seed_from(client)
    assert adopted_seed["r6_gate"]["reuse_count"] == 3
    assert adopted_seed["r6_gate"]["ledger_evidence_refs"] == ledger_refs
    ledger_rows = _ledger_rows(tmp_path)
    assert {row["run_id"] for row in ledger_rows} == set(run_refs)
    for run_ref in run_refs:
        assert any(
            row["run_id"] == run_ref
            and row["event_type"] == "artifact_created"
            and f"SDD-D4-01 reuse evidence: {SEED_ID}" in str(row.get("routing_advice"))
            for row in ledger_rows
        )

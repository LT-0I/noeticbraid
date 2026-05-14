# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parent.parent
for path in (
    REPO_ROOT / "packages" / "noeticbraid-core" / "src",
    REPO_ROOT / "packages" / "noeticbraid-multimodel-alliance" / "src",
    PACKAGE_ROOT / "src",
):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from fastapi.testclient import TestClient

from noeticbraid_backend.app import create_app
from noeticbraid_backend.settings import Settings

FIXTURES = Path(__file__).resolve().parent / "fixtures"
FIXTURE_OMC_SOURCES = [
    (FIXTURES / "omc_source_claude_md_sample.md", "tests/fixtures/omc_source_claude_md_sample.md"),
    (FIXTURES / "omc_source_rtk_md_sample.md", "tests/fixtures/omc_source_rtk_md_sample.md"),
]


def _client(tmp_path: Path) -> TestClient:
    return TestClient(
        create_app(Settings(state_dir=tmp_path / "state", dpapi_blob_path=None, omc_sources=FIXTURE_OMC_SOURCES))
    )


def _task_card() -> dict[str, object]:
    return json.loads((FIXTURES / "omc_task_card.json").read_text(encoding="utf-8"))


def _create_candidate(client: TestClient) -> dict[str, object]:
    response = client.post("/api/projects/omc-ingest/tasks", json=_task_card())
    assert response.status_code == 200, response.text
    return response.json()


def test_omc_project_task_creates_candidate_from_d2_01_loop(tmp_path: Path) -> None:
    body = _create_candidate(_client(tmp_path))

    assert body["project_id"] == "omc-ingest"
    assert body["task_id"] == "task_omc_ingest"
    assert body["candidate_id"] == "memory_omc_ingest_debate_loop"
    assert body["run_record_ref"].startswith("run_")
    assert body["convergence_markdown_ref"].endswith(".md")
    assert "SDD-D2-01" in body["candidate"]["source_sdd_ids"]


def test_omc_candidates_list_is_project_scoped(tmp_path: Path) -> None:
    client = _client(tmp_path)
    created = _create_candidate(client)

    response = client.get("/api/projects/omc-ingest/candidates")

    assert response.status_code == 200
    candidates = response.json()["candidates"]
    assert [candidate["candidate_id"] for candidate in candidates] == [created["candidate_id"]]
    assert all(candidate["project_id"] == "omc-ingest" for candidate in candidates)


def test_adopted_history_returns_prior_ui_adoptions(tmp_path: Path) -> None:
    client = _client(tmp_path)
    created = _create_candidate(client)
    adopt = client.post(f"/api/candidates/{created['candidate_id']}/adopt")
    assert adopt.status_code == 200

    response = client.get("/api/projects/omc-ingest/adopted-history")

    assert response.status_code == 200
    adopted = response.json()["adopted_candidates"]
    assert [candidate["candidate_id"] for candidate in adopted] == [created["candidate_id"]]
    assert adopted[0]["adopted_at"] is not None
    assert adopted[0]["run_record_ref"] == created["run_record_ref"]


def test_candidate_adopt_requires_explicit_post_and_writes_ledger_refs(tmp_path: Path) -> None:
    client = _client(tmp_path)
    created = _create_candidate(client)
    before = client.get("/api/projects/omc-ingest/candidates").json()["candidates"][0]
    assert before["status"] == "candidate"
    assert before["adopted_at"] is None

    response = client.post(f"/api/candidates/{created['candidate_id']}/adopt")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "adopted"
    assert body["adopted_by"] == "user"
    assert body["run_record_ref"] == created["run_record_ref"]
    assert body["ledger_refs"][0] == created["run_record_ref"]
    assert any(ref.startswith("artifact_candidate_adoption_") for ref in body["ledger_refs"])


def test_candidate_adopt_writes_narrative_artifact_with_existing_artifact_event(tmp_path: Path) -> None:
    client = _client(tmp_path)
    created = _create_candidate(client)
    body = client.post(f"/api/candidates/{created['candidate_id']}/adopt").json()
    artifact_path = tmp_path / body["adoption_artifact_ref"]

    assert artifact_path.exists()
    assert "explicit UI adoption" in artifact_path.read_text(encoding="utf-8")
    ledger_lines = (tmp_path / "state" / "ledger" / "run_ledger.jsonl").read_text(encoding="utf-8").splitlines()
    event_types = [json.loads(line)["event_type"] for line in ledger_lines if line.strip()]
    assert "artifact_created" in event_types
    assert "candidate_adopted" not in event_types


def test_omc_run_record_references_adopted_candidate_for_reuse_evidence(tmp_path: Path) -> None:
    client = _client(tmp_path)
    created = _create_candidate(client)
    client.post(f"/api/candidates/{created['candidate_id']}/adopt")

    adopted = client.get("/api/projects/omc-ingest/adopted-history").json()["adopted_candidates"][0]

    assert adopted["run_record_ref"] == created["run_record_ref"]
    assert any(ref.startswith("artifact_candidate_adoption_") for ref in adopted["reuse_evidence_refs"])
    assert any("candidate-adoption-" in ref and ref.endswith(".md") for ref in adopted["artifact_refs"])


def test_empty_task_card_rejected_without_candidate_write(tmp_path: Path) -> None:
    client = _client(tmp_path)
    response = client.post("/api/projects/omc-ingest/tasks", json={**_task_card(), "prompt": "   "})

    assert response.status_code == 400
    assert client.get("/api/projects/omc-ingest/candidates").json() == {
        "project_id": "omc-ingest",
        "candidates": [],
    }

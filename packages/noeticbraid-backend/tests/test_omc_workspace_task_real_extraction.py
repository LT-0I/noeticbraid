# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
import re
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


def test_submit_omc_ingest_task_returns_real_summary(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("NOETICBRAID_OMC_EXTRACT_LIVE", raising=False)

    response = _client(tmp_path).post("/api/projects/omc-ingest/tasks", json=_task_card())

    assert response.status_code == 200, response.text
    summary = response.json()["candidate"]["summary"]
    assert summary.startswith("Extracted ")
    assert "OMC ingestion debate produced" not in summary
    assert re.search(r"[a-f0-9]{16}", summary)
    assert "source_omc_local_metadata" in response.json()["candidate"]["source_refs"]


def test_submit_omc_ingest_task_writes_narrative_artifact(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("NOETICBRAID_OMC_EXTRACT_LIVE", raising=False)

    body = _client(tmp_path).post("/api/projects/omc-ingest/tasks", json=_task_card()).json()
    narrative_refs = [ref for ref in body["artifact_refs"] if "omc-knowledge-extraction-" in ref and ref.endswith(".md")]

    assert narrative_refs
    artifact_path = tmp_path / narrative_refs[0]
    assert artifact_path.exists()
    assert artifact_path.read_text(encoding="utf-8").strip()

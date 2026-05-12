# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parent.parent
for path in (REPO_ROOT / "packages" / "noeticbraid-core" / "src", PACKAGE_ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from fastapi.testclient import TestClient

from noeticbraid_backend.app import create_app
from noeticbraid_backend.omc_workspace import capability_registry as target_module
from noeticbraid_backend.settings import Settings


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(Settings(state_dir=tmp_path / "state", dpapi_blob_path=None)))


def test_capabilities_route_lists_four_first_stage_entries(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/api/capabilities")

    assert response.status_code == 200
    capabilities = response.json()["capabilities"]
    assert [item["display_name"] for item in capabilities] == [
        "Claude Code CLI",
        "Codex CLI",
        "Gemini CLI",
        "Gemini Web",
    ]
    assert all(item["first_stage"] is True for item in capabilities)


def test_health_check_defaults_to_mock_without_cli_execution(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("NOETICBRAID_HEALTH_CHECK_LIVE", raising=False)

    def explode(*_args, **_kwargs):
        raise AssertionError("mock health check must not execute provider CLI")

    monkeypatch.setattr(target_module, "run", explode)
    response = _client(tmp_path).post("/api/capabilities/cap_codex_cli/health-check")

    assert response.status_code == 200
    body = response.json()
    assert body["result"]["mode"] == "mock"
    assert body["capability"]["health_mode"] == "mock"
    assert body["result"]["artifact_ref"] is None


def test_health_check_real_mode_requires_noeticbraid_health_check_live_opt_in(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("NOETICBRAID_HEALTH_CHECK_LIVE", raising=False)
    mock = _client(tmp_path).post("/api/capabilities/cap_codex_cli/health-check").json()
    assert mock["result"]["mode"] == "mock"

    monkeypatch.setenv("NOETICBRAID_HEALTH_CHECK_LIVE", "1")
    monkeypatch.setattr(
        target_module,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="codex 5.5", stderr=""),
    )
    live = _client(tmp_path).post("/api/capabilities/cap_codex_cli/health-check").json()

    assert live["result"]["mode"] == "live_opt_in"
    assert live["capability"]["health_mode"] == "live_opt_in"


def test_health_check_real_mode_writes_artifact_trace_when_enabled(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("NOETICBRAID_HEALTH_CHECK_LIVE", "1")
    monkeypatch.setattr(
        target_module,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="codex 5.5", stderr=""),
    )

    response = _client(tmp_path).post("/api/capabilities/cap_codex_cli/health-check")

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["mode"] == "live_opt_in"
    artifact_path = tmp_path / result["artifact_ref"]
    assert artifact_path.exists()
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["mode"] == "live"
    assert artifact["capability_id"] == "cap_codex_cli"


def test_capabilities_routes_status_field_unhealthy_when_subprocess_fails(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("NOETICBRAID_HEALTH_CHECK_LIVE", "1")
    monkeypatch.setattr(
        target_module,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stdout="", stderr="provider unavailable"),
    )

    response = _client(tmp_path).post("/api/capabilities/cap_codex_cli/health-check")

    assert response.status_code == 200
    body = response.json()
    assert body["result"]["status"] == "unhealthy"
    assert body["capability"]["status"] == "unhealthy"
    assert body["result"]["error_msg"] == "provider unavailable"


def test_capabilities_routes_returns_http_200_even_on_unhealthy(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("NOETICBRAID_HEALTH_CHECK_LIVE", "1")

    def fake_run(*_args, **_kwargs):
        raise FileNotFoundError("missing codex")

    monkeypatch.setattr(target_module, "run", fake_run)

    response = _client(tmp_path).post("/api/capabilities/cap_codex_cli/health-check")

    assert response.status_code == 200
    body = response.json()
    assert body["result"]["status"] == "unhealthy"
    assert body["result"]["version"] is None
    assert body["result"]["error_msg"] == "codex executable not found"


def test_live_artifact_ref_falls_back_to_filename_outside_project_root(tmp_path: Path) -> None:
    outside_project = tmp_path / "external" / "health-check-cap_codex_cli.json"
    project_root = tmp_path / "project"

    assert (
        target_module._relative_if_possible(outside_project, project_root)
        == "health-check-cap_codex_cli.json"
    )

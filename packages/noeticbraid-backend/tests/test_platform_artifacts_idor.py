# SPDX-License-Identifier: Apache-2.0
# ruff: noqa: E402
"""C6 artifact download IDOR and traversal hardening tests."""

from __future__ import annotations

import sys
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
from noeticbraid_backend.auth.token_store import TokenStore
from noeticbraid_backend.platform.artifacts.store import persist
from noeticbraid_backend.platform.tasks.store import create_task
from noeticbraid_backend.settings import Settings


def test_artifact_download_cross_user_and_traversal_return_404_without_leak(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "platform-data"
    monkeypatch.setenv("NOETICBRAID_PLATFORM_ENABLED", "1")
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(data_root))
    store = TokenStore(data_root)
    beta_one_token = store.create_token("beta_user_01")
    beta_two_token = store.create_token("beta_user_02")
    task_id = "task_beta_two_artifact"
    foreign_bytes = b"beta two private artifact\n"
    create_task("beta_user_02", task_id=task_id, title="Private", modality_targets=["text"])
    artifact = persist("beta_user_02", task_id, "text", foreign_bytes)
    client = TestClient(create_app(Settings(state_dir=tmp_path / "state")))

    own_response = client.get(
        f"/platform/tasks/{task_id}/artifacts/{artifact.artifact_id}",
        headers={"authorization": f"Bearer {beta_two_token}"},
    )
    assert own_response.status_code == 200
    assert own_response.content == foreign_bytes
    assert own_response.headers["content-type"].startswith("text/markdown")
    assert "attachment" in own_response.headers["content-disposition"]

    cross_response = client.get(
        f"/platform/tasks/{task_id}/artifacts/{artifact.artifact_id}",
        headers={"authorization": f"Bearer {beta_one_token}"},
    )
    assert cross_response.status_code == 404
    assert foreign_bytes not in cross_response.content

    traversal_response = client.get(
        f"/platform/tasks/{task_id}/artifacts/%2e%2e",
        headers={"authorization": f"Bearer {beta_two_token}"},
    )
    assert traversal_response.status_code == 404
    assert foreign_bytes not in traversal_response.content

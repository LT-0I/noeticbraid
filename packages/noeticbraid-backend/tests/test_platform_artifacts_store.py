# SPDX-License-Identifier: Apache-2.0
# ruff: noqa: E402
"""C6 platform artifact store persistence and ledger tests."""

from __future__ import annotations

import hashlib
import json
import stat
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parent.parent
SRC_ROOT = PACKAGE_ROOT / "src"
CORE_SRC_ROOT = REPO_ROOT / "packages" / "noeticbraid-core" / "src"
for path in (CORE_SRC_ROOT, SRC_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from noeticbraid_backend.platform.artifacts.store import persist
from noeticbraid_backend.platform.ledger.writer import ledger_path_for
from noeticbraid_backend.platform.tasks.store import create_task
from noeticbraid_backend.platform.workspace_paths import resolve_user_path


def _ledger_rows(account: str, task_id: str) -> list[dict[str, object]]:
    return [json.loads(line) for line in ledger_path_for(account, task_id).read_text(encoding="utf-8").splitlines()]


def test_persist_raw_bytes_writes_in_account_root_and_ledgers_artifact(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(tmp_path / "platform-data"))
    account = "beta_user_01"
    task_id = "task_artifact_store"
    create_task(account, task_id=task_id, title="Store", modality_targets=["text"])
    content = b"artifact bytes\n"

    artifact = persist(account, task_id, "text", content)

    artifact_path = resolve_user_path(account, artifact.rel_path)
    assert artifact.task_id == task_id
    assert artifact.modality == "text"
    assert artifact.status == "produced"
    assert artifact.bytes == len(content)
    assert artifact.sha256 == hashlib.sha256(content).hexdigest()
    assert artifact.rel_path == f"tasks/{task_id}/artifacts/{artifact.artifact_id}.md"
    assert artifact_path.is_file()
    assert artifact_path.read_bytes() == content
    assert artifact_path.is_relative_to(resolve_user_path(account, "."))
    assert stat.S_IMODE(artifact_path.stat().st_mode) == 0o600

    rows = _ledger_rows(account, task_id)
    produced = [row for row in rows if row["type"] == "artifact_produced"]
    assert len(produced) == 1
    assert produced[0]["payload"] == {
        "modality": "text",
        "rel_path": artifact.rel_path,
        "sha256": artifact.sha256,
        "bytes": len(content),
    }


def test_persist_existing_in_root_path_preserves_safe_basename(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(tmp_path / "platform-data"))
    account = "beta_user_02"
    task_id = "task_artifact_source"
    create_task(account, task_id=task_id, title="Store source", modality_targets=["image"])
    source = resolve_user_path(account, f"tasks/{task_id}/artifacts/hub-image.png")
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"image bytes\n")

    artifact = persist(account, task_id, "image", source)

    assert artifact.artifact_id == "hub-image"
    assert artifact.rel_path == f"tasks/{task_id}/artifacts/hub-image.png"
    assert resolve_user_path(account, artifact.rel_path).read_bytes() == b"image bytes\n"

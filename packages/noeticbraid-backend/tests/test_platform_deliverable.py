# SPDX-License-Identifier: Apache-2.0
# ruff: noqa: E402
"""SDD-D17 single deliverable endpoint and local materialization tests."""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
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
from noeticbraid_backend.cli.__main__ import main as cli_main
from noeticbraid_backend.platform.artifacts.store import persist
from noeticbraid_backend.platform.ledger.events import ai_call_event
from noeticbraid_backend.platform.ledger.writer import append_event
from noeticbraid_backend.platform.tasks.store import create_task
from noeticbraid_backend.platform.workspace_paths import resolve_user_path
from noeticbraid_backend.settings import Settings

try:
    from PIL import Image
except Exception:  # pragma: no cover - test environment provisioning failure is explicit below
    Image = None  # type: ignore[assignment]

ACCOUNT = "beta_user_01"
OTHER_ACCOUNT = "beta_user_02"
DOCUMENT_TASK = "task_promo_smoke_1778967211"
CONVERT_TASK = "task_promo_chatgpt_1778967273"
IMAGE_TASK = "task_promo_image_1778991545"
VIDEO_TASK = "task_promo_gemini_1778968111"
NOT_MATERIALIZED = (
    "Local .pptx/poster conversion has not been materialized yet "
    "(run: noeticbraid platform materialize-deliverable)."
)


def _client(monkeypatch, tmp_path: Path) -> tuple[TestClient, Path]:
    data_root = tmp_path / "platform-data"
    monkeypatch.setenv("NOETICBRAID_PLATFORM_ENABLED", "1")
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(data_root))
    app = create_app(Settings(state_dir=tmp_path / "state"))
    return TestClient(app), data_root


def _token(data_root: Path, account: str = ACCOUNT) -> str:
    return TokenStore(data_root).create_token(account)


def _headers(token: str) -> dict[str, str]:
    return {"authorization": f"Bearer {token}"}


def _seed_plan(account: str = ACCOUNT) -> None:
    create_task(account, task_id=DOCUMENT_TASK, title="NoeticBraid promo material", modality_targets=["document"])
    create_task(
        account,
        task_id=CONVERT_TASK,
        title="NoeticBraid promo material",
        modality_targets=["document", "slides", "poster", "image"],
    )
    create_task(account, task_id=IMAGE_TASK, title="NoeticBraid promo material", modality_targets=["image"])
    create_task(account, task_id=VIDEO_TASK, title="NoeticBraid promo material", modality_targets=["video"])
    persist(account, DOCUMENT_TASK, "document", b"# NoeticBraid promo\n\nTraceable enterprise AI work.\n")
    persist(
        account,
        CONVERT_TASK,
        "slides",
        b"NoeticBraid Promo Deck Outline\n1. Title\nNoeticBraid: Enterprise AI Task Panels\n2. Value\nTraceable execution.\n",
    )
    persist(
        account,
        CONVERT_TASK,
        "poster",
        b"NoeticBraid Poster Copy & Layout Guidance\nPoster Title\nNoeticBraid\nHero Line\nStructured execution.\n",
    )
    append_event(
        account,
        ai_call_event(
            IMAGE_TASK,
            op="webai_chatgpt_generate_image",
            vendor="chatgpt",
            gate_status="not_implemented",
            redacted_payload={"status": "not_implemented", "reason": "hub dispatch timed out"},
        ),
    )
    append_event(
        account,
        ai_call_event(
            VIDEO_TASK,
            op="webai_gemini_generate_video",
            vendor="gemini",
            gate_status="not_implemented",
            redacted_payload={"status": "not_implemented", "reason": "artifact path governance violation"},
        ),
    )
    _write_unledgered(account, IMAGE_TASK, "a.png", b"old image")
    _write_unledgered(account, IMAGE_TASK, "z.png", b"new image")
    _write_unledgered(account, VIDEO_TASK, "promo.mp4", b"\x00\x00\x00 ftypmp42real video")


def _write_unledgered(account: str, task_id: str, name: str, content: bytes) -> Path:
    path = resolve_user_path(account, f"tasks/{task_id}/artifacts/{name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    path.chmod(0o600)
    return path


def test_deliverable_endpoint_returns_six_modality_contract_and_account_binding(monkeypatch, tmp_path: Path) -> None:
    client, data_root = _client(monkeypatch, tmp_path)
    _seed_plan()
    token = _token(data_root)

    response = client.get("/platform/deliverable", headers=_headers(token))

    assert response.status_code == 200
    payload = response.json()["deliverable"]
    assert set(payload) == {"title", "generated_at", "modalities"}
    assert payload["generated_at"] is None
    modalities = {item["modality"]: item for item in payload["modalities"]}
    assert tuple(modalities) == ("document", "slides", "poster", "image", "video", "music")
    assert {item["status"] for item in modalities.values()} <= {"delivered", "converted", "blocked"}
    assert {item["provenance"]["kind"] for item in modalities.values()} <= {
        "ai_produced_markdown",
        "local_format_conversion",
        "on_disk_unledgered_real_binary",
        "not_attempted",
    }
    assert modalities["document"]["status"] == "delivered"
    assert modalities["document"]["filename"] == "NoeticBraid-Promo-Document.md"
    assert modalities["slides"]["status"] == "blocked"
    assert modalities["slides"]["blocked_reason"] == NOT_MATERIALIZED
    assert modalities["slides"]["sha256"] is None
    assert modalities["slides"]["download_url"] is None
    assert modalities["poster"]["blocked_reason"] == NOT_MATERIALIZED
    assert modalities["image"]["status"] == "blocked"
    assert modalities["image"]["blocked_reason"] == "hub dispatch timed out"
    assert modalities["image"]["provenance"]["ledgered"] is False
    assert modalities["image"]["sha256"] == hashlib.sha256(b"new image").hexdigest()
    assert modalities["image"]["download_url"] == "/platform/deliverable/artifacts/image"
    assert modalities["video"]["blocked_reason"] == "artifact path governance violation"
    assert modalities["music"]["provenance"]["kind"] == "not_attempted"
    assert modalities["music"]["download_url"] is None

    other_token = _token(data_root, OTHER_ACCOUNT)
    cross_response = client.get("/platform/deliverable", headers=_headers(other_token))
    assert cross_response.status_code == 404
    assert cross_response.json() == {"detail": "not_found"}


def test_nonledgered_scoped_route_serves_allowlisted_confined_file_and_rejects_other_modalities(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client, data_root = _client(monkeypatch, tmp_path)
    _seed_plan()
    token = _token(data_root)

    image_response = client.get("/platform/deliverable/artifacts/image", headers=_headers(token))
    assert image_response.status_code == 200
    assert image_response.content == b"new image"
    assert image_response.headers["content-type"].startswith("image/png")
    assert "NoeticBraid-Promo-Image.png" in image_response.headers["content-disposition"]

    assert client.get("/platform/deliverable/artifacts/music", headers=_headers(token)).status_code == 404
    assert client.get("/platform/deliverable/artifacts/audio", headers=_headers(token)).status_code == 404
    assert client.get("/platform/deliverable/artifacts/image%2F..", headers=_headers(token)).status_code != 200


def test_materialize_cli_produces_valid_deterministic_pptx_png_and_sidecar(monkeypatch, tmp_path: Path) -> None:
    if Image is None:
        raise AssertionError("Pillow is required for SDD-D17 poster materialization tests")
    client, _data_root = _client(monkeypatch, tmp_path)
    _seed_plan()

    assert cli_main(["platform", "materialize-deliverable", "--account", ACCOUNT]) == 0
    artifacts_root = resolve_user_path(ACCOUNT, f"tasks/{CONVERT_TASK}/artifacts")
    pptx = artifacts_root / "NoeticBraid-Promo-Deck.pptx"
    png = artifacts_root / "NoeticBraid-Promo-Poster.png"
    sidecar = artifacts_root / ".deliverable_materialization.json"
    first_hashes = tuple(_sha(path) for path in (pptx, png, sidecar))

    with zipfile.ZipFile(pptx) as archive:
        names = set(archive.namelist())
    assert "ppt/presentation.xml" in names
    assert "[Content_Types].xml" in names
    image = Image.open(png)
    assert image.width > 0 and image.height > 0
    sidecar_payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert sidecar_payload["slides"]["sha256"] == first_hashes[0]
    assert sidecar_payload["poster"]["sha256"] == first_hashes[1]

    assert cli_main(["platform", "materialize-deliverable", "--account", ACCOUNT]) == 0
    assert tuple(_sha(path) for path in (pptx, png, sidecar)) == first_hashes

    token = _token(tmp_path / "platform-data")
    response = client.get("/platform/deliverable", headers=_headers(token))
    assert response.status_code == 200
    modalities = {item["modality"]: item for item in response.json()["deliverable"]["modalities"]}
    assert modalities["slides"]["status"] == "converted"
    assert modalities["slides"]["sha256"] == first_hashes[0]
    assert modalities["slides"]["provenance"]["source_artifact_sha256"]
    assert "NOT an AI-generated binary" in modalities["slides"]["provenance"]["note"]
    assert modalities["poster"]["status"] == "converted"

    slides_download = client.get("/platform/deliverable/artifacts/slides", headers=_headers(token))
    assert slides_download.status_code == 200
    assert slides_download.content == pptx.read_bytes()
    with zipfile.ZipFile(pptx) as archive:
        assert "ppt/presentation.xml" in archive.namelist()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

# SPDX-License-Identifier: Apache-2.0
# ruff: noqa: E402
"""Platform server-side STT fails closed and keeps audio private."""

from __future__ import annotations

import importlib.util
import os
import sys
import wave
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parent.parent
SRC_ROOT = PACKAGE_ROOT / "src"
CORE_SRC_ROOT = REPO_ROOT / "packages" / "noeticbraid-core" / "src"
for path in (CORE_SRC_ROOT, SRC_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import pytest
from fastapi.testclient import TestClient

from noeticbraid_backend.app import create_app
from noeticbraid_backend.auth.token_store import TokenStore
from noeticbraid_backend.platform.stt import endpoint as stt_endpoint
from noeticbraid_backend.platform.stt.transcribe import transcribe
from noeticbraid_backend.settings import Settings


def _client_and_token(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[TestClient, str, Path]:
    data_root = tmp_path / "platform-data"
    monkeypatch.setenv("NOETICBRAID_PLATFORM_ENABLED", "1")
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(data_root))
    token = TokenStore(data_root).create_token("beta_user_01")
    app = create_app(Settings(state_dir=tmp_path / "state"))
    return TestClient(app), token, data_root


def _post_audio(
    client: TestClient,
    token: str,
    *,
    filename: str = "voice.wav",
    body: bytes = b"RIFF....WAVEfmt ",
    mime: str = "audio/wav",
):
    return client.post(
        "/platform/stt/transcribe",
        headers={"Authorization": f"Bearer {token}"},
        files={"audio": (filename, body, mime)},
    )


def test_stt_not_provisioned_returns_structured_refusal_without_path_leak(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    absent_model_dir = tmp_path / "absent-model-dir"
    monkeypatch.setenv("NOETICBRAID_PLATFORM_STT_MODEL_DIR", str(absent_model_dir))
    client, token, data_root = _client_and_token(monkeypatch, tmp_path)

    response = _post_audio(client, token)

    assert response.status_code == 200
    assert response.json() == {"status": "not_provisioned"}
    assert str(absent_model_dir) not in response.text
    assert str(data_root) not in response.text
    assert str(tmp_path) not in response.text


def test_stt_upload_bound_rejects_oversized_multipart(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(stt_endpoint, "MAX_UPLOAD_BYTES", 32)
    client, token, _data_root = _client_and_token(monkeypatch, tmp_path)

    response = _post_audio(client, token, body=b"x" * 128)

    assert response.status_code == 413
    assert response.json() == {"detail": "upload_too_large"}


def test_stt_rejects_bad_mime_and_extension(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client, token, _data_root = _client_and_token(monkeypatch, tmp_path)

    response = _post_audio(client, token, filename="voice.txt", body=b"hello", mime="text/plain")

    assert response.status_code == 415
    assert response.json() == {"detail": "unsupported_audio_type"}


def test_stt_temp_path_ignores_filename_traversal_and_deletes_upload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    seen_audio_paths: list[Path] = []

    def fake_transcribe(audio_path: Path, account: str) -> dict[str, int | str]:
        assert account == "beta_user_01"
        assert audio_path.exists()
        seen_audio_paths.append(audio_path)
        return {"text": "ok", "duration_ms": 1}

    monkeypatch.setattr(stt_endpoint, "transcribe", fake_transcribe)
    client, token, data_root = _client_and_token(monkeypatch, tmp_path)

    response = _post_audio(client, token, filename="../../escape.wav", body=b"RIFFaudio", mime="audio/wav")

    assert response.status_code == 200
    assert response.json() == {"text": "ok", "duration_ms": 1}
    assert len(seen_audio_paths) == 1
    temp_path = seen_audio_paths[0]
    assert temp_path.suffix == ".wav"
    assert temp_path.parent == data_root / "users" / "beta_user_01" / "tmp" / "stt"
    assert not temp_path.exists()
    assert not (tmp_path / "escape.wav").exists()


def test_stt_temp_file_deleted_after_not_provisioned_call(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("NOETICBRAID_PLATFORM_STT_MODEL_DIR", str(tmp_path / "missing-model"))
    seen_audio_paths: list[Path] = []
    original_transcribe = stt_endpoint.transcribe

    def recording_transcribe(audio_path: Path, account: str) -> dict[str, int | str]:
        assert audio_path.exists()
        seen_audio_paths.append(audio_path)
        return original_transcribe(audio_path, account)

    monkeypatch.setattr(stt_endpoint, "transcribe", recording_transcribe)
    client, token, _data_root = _client_and_token(monkeypatch, tmp_path)

    response = _post_audio(client, token)

    assert response.json() == {"status": "not_provisioned"}
    assert len(seen_audio_paths) == 1
    assert not seen_audio_paths[0].exists()


def test_stt_resolve_user_path_errors_are_generic(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def blocked_resolve(_account: str, _rel: str) -> Path:
        raise ValueError("workspace path escapes user root: /private/path")

    monkeypatch.setattr(stt_endpoint, "resolve_user_path", blocked_resolve)
    client, token, _data_root = _client_and_token(monkeypatch, tmp_path)

    response = _post_audio(client, token)

    assert response.status_code == 400
    assert response.json() == {"detail": "invalid_temp_path"}
    assert "/private/path" not in response.text


def _model_dir_is_available() -> bool:
    raw_model_dir = os.environ.get("NOETICBRAID_PLATFORM_STT_MODEL_DIR")
    if not raw_model_dir:
        return False
    model_dir = Path(raw_model_dir).expanduser()
    return model_dir.is_dir() and any(model_dir.iterdir())


@pytest.mark.skipif(
    not _model_dir_is_available() or importlib.util.find_spec("faster_whisper") is None,
    reason="faster-whisper optional extra and local model dir are not provisioned",
)
def test_real_faster_whisper_decode_when_model_is_provisioned(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    audio_path = tmp_path / "silence.wav"
    with wave.open(str(audio_path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(16_000)
        wav_file.writeframes(b"\x00\x00" * 16_000)

    monkeypatch.setenv("NOETICBRAID_PLATFORM_STT_MODEL_DIR", os.environ["NOETICBRAID_PLATFORM_STT_MODEL_DIR"])

    result = transcribe(audio_path, "beta_user_01")

    assert "text" in result
    assert "duration_ms" in result

# SPDX-License-Identifier: Apache-2.0
"""Fail-closed faster-whisper transcription boundary for platform STT."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from noeticbraid_backend.platform.settings import PlatformSettings

NotProvisioned = dict[str, str]
Transcription = dict[str, int | str]


def transcribe(audio_path: Path, account: str) -> Transcription | NotProvisioned:
    """Transcribe a local user-scoped audio file, or return not_provisioned.

    The faster-whisper import and model load are intentionally lazy so the base
    backend import/test path does not require the optional platform extra or a
    local model. Any unavailable dependency/model condition fails closed without
    echoing filesystem paths.
    """

    del account  # Account scoping happens before this boundary via resolve_user_path.
    model_dir = _model_dir()
    if model_dir is None:
        return _not_provisioned()

    try:
        from faster_whisper import WhisperModel  # type: ignore[import-not-found]
    except Exception:
        return _not_provisioned()

    try:
        model = WhisperModel(str(model_dir), device="cpu", compute_type="int8")
        segments, info = model.transcribe(str(audio_path))
        completed_segments = list(segments)
    except Exception:
        return _not_provisioned()

    text = " ".join(segment.text.strip() for segment in completed_segments if segment.text.strip())
    duration_ms = _duration_ms(info)
    return {"text": text, "duration_ms": duration_ms}


def _model_dir() -> Path | None:
    model_dir = PlatformSettings.from_env().stt_model_dir
    if model_dir is None or not model_dir.is_dir():
        return None
    try:
        if not any(model_dir.iterdir()):
            return None
    except OSError:
        return None
    return model_dir


def _duration_ms(info: Any) -> int:
    duration = getattr(info, "duration", 0.0)
    try:
        return max(0, int(round(float(duration) * 1000)))
    except (TypeError, ValueError):
        return 0


def _not_provisioned() -> NotProvisioned:
    return {"status": "not_provisioned"}


__all__ = ["transcribe"]

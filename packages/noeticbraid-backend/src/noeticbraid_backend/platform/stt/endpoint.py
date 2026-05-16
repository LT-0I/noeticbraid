# SPDX-License-Identifier: Apache-2.0
"""Multipart HTTP endpoint for platform speech-to-text."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from email.message import Message
from email.parser import BytesParser
from email.policy import default
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status

from noeticbraid_backend.platform.auth import require_platform_bearer
from noeticbraid_backend.platform.stt.transcribe import transcribe
from noeticbraid_backend.platform.workspace_paths import resolve_user_path

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
_ALLOWED_EXTENSIONS = frozenset({".wav", ".webm", ".m4a", ".mp3", ".ogg"})
_ALLOWED_MIME_TYPES = frozenset(
    {
        "audio/wav",
        "audio/x-wav",
        "audio/wave",
        "audio/webm",
        "video/webm",
        "audio/mp4",
        "audio/x-m4a",
        "audio/mpeg",
        "audio/mp3",
        "audio/ogg",
        "application/ogg",
    }
)


@dataclass(frozen=True, slots=True)
class _UploadedAudio:
    filename: str
    content_type: str
    body: bytes


def register_platform_stt_routes(platform_app: FastAPI) -> None:
    """Register platform STT routes on the mounted sub-app."""

    @platform_app.post("/stt/transcribe", summary="Transcribe uploaded audio")
    async def platform_stt_transcribe(request: Request) -> dict[str, int | str]:
        account = require_platform_bearer(request.headers.get("authorization"))
        _enforce_content_length(request)
        upload = await _read_audio_part(request)
        _validate_audio(upload)

        suffix = Path(upload.filename).suffix.lower()
        temp_path: Path | None = None
        try:
            temp_path = resolve_user_path(account, f"tmp/stt/{uuid.uuid4().hex}{suffix}")
            temp_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            temp_path.write_bytes(upload.body)
            return transcribe(temp_path, account)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_temp_path") from exc
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass


def _enforce_content_length(request: Request) -> None:
    raw_length = request.headers.get("content-length")
    if raw_length is None:
        return
    try:
        content_length = int(raw_length)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_content_length") from exc
    if content_length > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="upload_too_large")


async def _read_audio_part(request: Request) -> _UploadedAudio:
    content_type = request.headers.get("content-type", "")
    if not _is_multipart(content_type):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="multipart_required")

    body = await request.body()
    if len(body) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="upload_too_large")

    message = BytesParser(policy=default).parsebytes(
        b"Content-Type: " + content_type.encode("latin-1") + b"\r\nMIME-Version: 1.0\r\n\r\n" + body
    )
    if not message.is_multipart():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="multipart_required")

    first_file: _UploadedAudio | None = None
    for part in message.iter_parts():
        disposition = part.get_content_disposition()
        filename = part.get_filename()
        if disposition != "form-data" or filename is None:
            continue
        uploaded = _UploadedAudio(
            filename=filename,
            content_type=part.get_content_type().lower(),
            body=part.get_payload(decode=True) or b"",
        )
        if part.get_param("name", header="content-disposition") == "audio":
            return uploaded
        if first_file is None:
            first_file = uploaded

    if first_file is not None:
        return first_file
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="audio_part_required")


def _is_multipart(content_type: str) -> bool:
    message = Message()
    message["content-type"] = content_type
    return message.get_content_type().lower() == "multipart/form-data" and bool(
        message.get_param("boundary", header="content-type")
    )


def _validate_audio(upload: _UploadedAudio) -> None:
    suffix = Path(upload.filename).suffix.lower()
    if suffix not in _ALLOWED_EXTENSIONS or upload.content_type not in _ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="unsupported_audio_type")
    if not upload.body:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="empty_audio")


__all__ = ["MAX_UPLOAD_BYTES", "register_platform_stt_routes"]

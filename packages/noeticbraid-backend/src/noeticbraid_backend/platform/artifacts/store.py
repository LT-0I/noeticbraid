# SPDX-License-Identifier: Apache-2.0
"""Per-account platform artifact store backed by the C2 ledger."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Union

from noeticbraid_backend.platform.ledger.events import artifact_produced_event
from noeticbraid_backend.platform.ledger.writer import append_event
from noeticbraid_backend.platform.tasks.models import validate_task_id
from noeticbraid_backend.platform.workspace_paths import resolve_user_path

BytesOrPath = Union[bytes, bytearray, memoryview, str, Path]
_ARTIFACT_ID_RE = re.compile(r"[^A-Za-z0-9_-]+")
_MODALITY_EXTENSIONS = {
    "text": "md",
    "document": "md",
    "slides": "md",
    "poster": "md",
    "image": "png",
    "video": "mp4",
    "music": "mp3",
    "audio": "wav",
}


@dataclass(frozen=True, slots=True)
class Artifact:
    """Persisted artifact metadata mirrored into the append-only ledger."""

    artifact_id: str
    task_id: str
    modality: str
    rel_path: str
    sha256: str
    bytes: int
    status: str


def persist(account: str, task_id: str, modality: str, bytes_or_path: BytesOrPath) -> Artifact:
    """Persist bytes under the account task artifact directory and ledger the result."""

    task_key = validate_task_id(task_id)
    normalized_modality = _normalize_modality(modality)
    extension = _extension_for_modality(normalized_modality)
    content, preferred_id = _read_content(account, bytes_or_path)
    digest = hashlib.sha256(content).hexdigest()
    artifact_id = _artifact_id(preferred_id=preferred_id, modality=normalized_modality, digest=digest)
    rel_path = _artifact_rel_path(task_key, artifact_id, extension)
    target = resolve_user_path(account, rel_path)

    if target.exists() and target.read_bytes() != content:
        artifact_id = _artifact_id(
            preferred_id=f"{artifact_id[:63]}-{digest}",
            modality=normalized_modality,
            digest=digest,
        )
        rel_path = _artifact_rel_path(task_key, artifact_id, extension)
        target = resolve_user_path(account, rel_path)

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    target.chmod(0o600)
    append_event(
        account,
        artifact_produced_event(
            task_key,
            modality=normalized_modality,
            rel_path=rel_path,
            sha256=digest,
            bytes_count=len(content),
        ),
    )
    return Artifact(
        artifact_id=artifact_id,
        task_id=task_key,
        modality=normalized_modality,
        rel_path=rel_path,
        sha256=digest,
        bytes=len(content),
        status="produced",
    )


def extension_for_modality(modality: str) -> str:
    """Return the persisted artifact extension for a platform modality."""

    return _extension_for_modality(_normalize_modality(modality))


def _read_content(account: str, bytes_or_path: BytesOrPath) -> tuple[bytes, str | None]:
    if isinstance(bytes_or_path, bytes):
        return bytes_or_path, None
    if isinstance(bytes_or_path, (bytearray, memoryview)):
        return bytes(bytes_or_path), None

    source = _resolve_source_path(account, bytes_or_path)
    if not source.is_file():
        raise ValueError("artifact source must be a regular file")
    return source.read_bytes(), source.stem


def _resolve_source_path(account: str, source: str | Path) -> Path:
    raw_path = Path(os.fspath(source))
    if raw_path.is_absolute():
        user_root = resolve_user_path(account, ".")
        root_real = Path(os.path.realpath(user_root))
        source_real = Path(os.path.realpath(raw_path))
        if not source_real.is_relative_to(root_real):
            raise ValueError("artifact source escapes user root")
        return source_real
    return resolve_user_path(account, raw_path)


def _normalize_modality(modality: str) -> str:
    normalized = str(modality or "").strip().lower()
    if not normalized:
        raise ValueError("modality must be a non-empty string")
    return normalized


def _extension_for_modality(modality: str) -> str:
    return _MODALITY_EXTENSIONS.get(modality, "bin")


def _artifact_id(*, preferred_id: str | None, modality: str, digest: str) -> str:
    if preferred_id:
        candidate = _sanitize_artifact_id(preferred_id)
        if candidate:
            return candidate
    return _sanitize_artifact_id(f"{modality}-{digest}")


def _sanitize_artifact_id(value: str) -> str:
    sanitized = _ARTIFACT_ID_RE.sub("-", value.strip()).strip("-_")
    return sanitized[:128]


def _artifact_rel_path(task_id: str, artifact_id: str, extension: str) -> str:
    safe_id = _sanitize_artifact_id(artifact_id)
    if not safe_id:
        raise ValueError("artifact_id must be non-empty")
    safe_extension = _extension_for_rel_path(extension)
    return f"tasks/{task_id}/artifacts/{safe_id}.{safe_extension}"


def _extension_for_rel_path(extension: str) -> str:
    safe = str(extension or "bin").lower().lstrip(".")
    if not safe or not safe.isalnum() or len(safe) > 16:
        return "bin"
    return safe


__all__ = ["Artifact", "BytesOrPath", "extension_for_modality", "persist"]

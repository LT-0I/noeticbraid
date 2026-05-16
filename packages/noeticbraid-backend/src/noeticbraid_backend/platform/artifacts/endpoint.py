# SPDX-License-Identifier: Apache-2.0
"""Authenticated platform artifact download endpoint."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import re
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse

from noeticbraid_backend.platform.auth import require_platform_bearer
from noeticbraid_backend.platform.ledger.writer import ledger_path_for
from noeticbraid_backend.platform.tasks import store as task_store
from noeticbraid_backend.platform.tasks.models import account_ref_for
from noeticbraid_backend.platform.workspace_paths import resolve_user_path

_ARTIFACT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_CONTENT_TYPES_BY_MODALITY = {
    "text": "text/markdown; charset=utf-8",
    "document": "text/markdown; charset=utf-8",
    "slides": "text/markdown; charset=utf-8",
    "poster": "text/markdown; charset=utf-8",
    "image": "image/png",
    "video": "video/mp4",
    "music": "audio/mpeg",
    "audio": "audio/wav",
}


def register_platform_artifact_routes(platform_app: FastAPI) -> None:
    """Register artifact download routes on the mounted platform sub-app."""

    @platform_app.get("/tasks/{task_id}/artifacts/{artifact_id}", summary="Download a platform task artifact")
    async def platform_download_artifact(request: Request, task_id: str, artifact_id: str) -> FileResponse:
        account = require_platform_bearer(request.headers.get("authorization"))
        artifact = _resolve_owned_artifact(account, task_id, artifact_id)
        return FileResponse(
            artifact.path,
            media_type=artifact.content_type,
            filename=artifact.path.name,
            content_disposition_type="attachment",
        )


class _ResolvedArtifact:
    def __init__(self, *, path: Path, content_type: str) -> None:
        self.path = path
        self.content_type = content_type


def _resolve_owned_artifact(account: str, task_id: str, artifact_id: str) -> _ResolvedArtifact:
    if not _is_safe_artifact_id(artifact_id):
        raise _not_found()

    try:
        task = task_store.load_task(account, task_id)
        if task.account_id_ref != account_ref_for(account):
            raise ValueError("task/account binding mismatch")
        candidates = tuple(_artifact_events(account, task.task_id))
    except Exception as exc:
        raise _not_found() from exc

    for payload in candidates:
        try:
            rel_path = str(payload["rel_path"])
            path = resolve_user_path(account, rel_path)
            if path.stem != artifact_id:
                continue
            if not _is_task_artifact_rel_path(task.task_id, rel_path):
                continue
            if not _is_under_account_root(account, path):
                continue
            if not path.is_file():
                continue
            expected_sha = payload.get("sha256")
            if isinstance(expected_sha, str) and expected_sha:
                if hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha.lower():
                    continue
            modality = str(payload.get("modality") or "")
            return _ResolvedArtifact(path=path, content_type=_content_type(modality, path))
        except Exception:
            continue
    raise _not_found()


def _artifact_events(account: str, task_id: str) -> list[dict[str, Any]]:
    path = ledger_path_for(account, task_id)
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError("ledger row must be an object")
        if row.get("type") != "artifact_produced":
            continue
        payload = row.get("payload")
        if isinstance(payload, dict):
            events.append(payload)
    return events


def _is_safe_artifact_id(artifact_id: str) -> bool:
    return isinstance(artifact_id, str) and _ARTIFACT_ID_RE.fullmatch(artifact_id) is not None


def _is_task_artifact_rel_path(task_id: str, rel_path: str) -> bool:
    normalized = rel_path.replace("\\", "/")
    prefix = f"tasks/{task_id}/artifacts/"
    if not normalized.startswith(prefix):
        return False
    suffix = normalized[len(prefix) :]
    return bool(suffix) and "/" not in suffix and suffix not in {".", ".."}


def _is_under_account_root(account: str, path: Path) -> bool:
    root = resolve_user_path(account, ".")
    return path.is_relative_to(root)


def _content_type(modality: str, path: Path) -> str:
    if modality in _CONTENT_TYPES_BY_MODALITY:
        return _CONTENT_TYPES_BY_MODALITY[modality]
    guessed, _encoding = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")


__all__ = ["register_platform_artifact_routes"]

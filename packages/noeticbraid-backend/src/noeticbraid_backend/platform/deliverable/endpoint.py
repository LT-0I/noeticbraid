# SPDX-License-Identifier: Apache-2.0
"""Authenticated SDD-D17 single deliverable endpoints."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse

from noeticbraid_backend.platform.artifacts.ledger import _ledger_rows
from noeticbraid_backend.platform.auth import require_platform_bearer
from noeticbraid_backend.platform.deliverable.materialize import (
    MaterializationError,
    read_sidecar,
    resolve_ledger_artifact,
    resolve_materialized_artifact,
)
from noeticbraid_backend.platform.deliverable.plan import (
    _CONTENT_TYPES,
    _DELIVERABLE_PLAN,
    _DOWNLOAD_MODALITIES,
    _FALLBACK_BLOCKED_REASONS,
    _FILENAMES,
    _MODALITIES,
    _NOT_ATTEMPTED_REASON,
    _NOT_MATERIALIZED_REASON,
    _UNLEDGERED_NOTES,
    Modality,
)
from noeticbraid_backend.platform.tasks import store as task_store
from noeticbraid_backend.platform.tasks.models import account_ref_for
from noeticbraid_backend.platform.workspace_paths import resolve_user_path

_UNLEDGERED_EXTENSIONS: dict[Modality, str] = {"image": ".png", "video": ".mp4"}


def register_platform_deliverable_routes(platform_app: FastAPI) -> None:
    """Register the SDD-D17 deliverable aggregation and scoped artifact routes."""

    @platform_app.get("/deliverable", summary="Read the single promo deliverable")
    async def platform_read_deliverable(request: Request) -> dict[str, Any]:
        account = require_platform_bearer(request.headers.get("authorization"))
        try:
            _verify_planned_task_ownership(account)
            return {"deliverable": _serialize_deliverable(account)}
        except Exception as exc:
            raise _not_found() from exc

    @platform_app.get(
        "/deliverable/artifacts/{modality}",
        summary="Download a scoped deliverable artifact",
    )
    async def platform_download_deliverable_artifact(request: Request, modality: str) -> FileResponse:
        account = require_platform_bearer(request.headers.get("authorization"))
        if modality not in _DOWNLOAD_MODALITIES:
            raise _not_found()
        try:
            _verify_planned_task_ownership(account)
            resolved = _resolve_download(account, modality)  # type: ignore[arg-type]
        except Exception as exc:
            raise _not_found() from exc
        return FileResponse(
            resolved["path"],
            media_type=resolved["content_type"],
            filename=_FILENAMES[modality][1],
            content_disposition_type="attachment",
        )


def _verify_planned_task_ownership(account: str) -> None:
    for item in _DELIVERABLE_PLAN.values():
        if item.source_task_id is None:
            continue
        task = task_store.load_task(account, item.source_task_id)
        if task.account_id_ref != account_ref_for(account):
            raise ValueError("task/account binding mismatch")


def _serialize_deliverable(account: str) -> dict[str, Any]:
    sidecar = read_sidecar(account)
    generated_at = sidecar.get("materialized_at") if isinstance(sidecar, dict) else None
    if not isinstance(generated_at, str):
        generated_at = None
    return {
        "title": "NoeticBraid promo material",
        "generated_at": generated_at,
        "modalities": [_serialize_modality(account, modality, generated_at) for modality in _MODALITIES],
    }


def _serialize_modality(account: str, modality: Modality, generated_at: str | None) -> dict[str, Any]:
    item = _DELIVERABLE_PLAN[modality]
    title, filename = _FILENAMES[modality]
    base: dict[str, Any] = {
        "modality": modality,
        "title": title,
        "filename": filename,
        "content_type": _CONTENT_TYPES[modality],
    }
    if item.source_kind == "ledger":
        return {**base, **_ledgered_markdown_payload(account, modality)}
    if item.source_kind == "ledger_to_convert":
        return {**base, **_converted_payload(account, modality, generated_at)}
    if item.source_kind == "on_disk_unledgered":
        return {**base, **_unledgered_binary_payload(account, modality)}
    return {**base, **_not_attempted_payload()}


def _ledgered_markdown_payload(account: str, modality: Modality) -> dict[str, Any]:
    artifact = resolve_ledger_artifact(account, modality)
    return {
        "status": "delivered",
        "bytes": artifact.bytes,
        "sha256": artifact.sha256,
        "download_url": f"/platform/deliverable/artifacts/{modality}",
        "blocked_reason": None,
        "provenance": {
            "source_task_id": artifact.task_id,
            "ledgered": True,
            "kind": "ai_produced_markdown",
            "note": f"AI-produced markdown artifact recorded in the source task ledger (sha {artifact.sha256}).",
            "source_artifact_sha256": artifact.sha256,
        },
    }


def _converted_payload(account: str, modality: Modality, generated_at: str | None) -> dict[str, Any]:
    source = resolve_ledger_artifact(account, modality)
    materialized = resolve_materialized_artifact(account, modality)
    if materialized is None or generated_at is None:
        return {
            "status": "blocked",
            "bytes": None,
            "sha256": None,
            "download_url": None,
            "blocked_reason": _NOT_MATERIALIZED_REASON,
            "provenance": {
                "source_task_id": source.task_id,
                "ledgered": True,
                "kind": "local_format_conversion",
                "note": "Local deterministic format conversion has not been materialized yet.",
                "source_artifact_sha256": source.sha256,
            },
        }
    return {
        "status": "converted",
        "bytes": materialized.bytes,
        "sha256": materialized.sha256,
        "download_url": f"/platform/deliverable/artifacts/{modality}",
        "blocked_reason": None,
        "provenance": {
            "source_task_id": source.task_id,
            "ledgered": True,
            "kind": "local_format_conversion",
            "note": (
                f"Rendered locally on {generated_at} from the AI-produced {modality} markdown "
                f"(sha {source.sha256}). Deterministic offline format conversion. "
                "NOT an AI-generated binary."
            ),
            "source_artifact_sha256": source.sha256,
        },
    }


def _unledgered_binary_payload(account: str, modality: Modality) -> dict[str, Any]:
    selected = _select_unledgered_binary(account, modality)
    reason = _blocked_reason_from_ledger(account, modality)
    item = _DELIVERABLE_PLAN[modality]
    provenance = {
        "source_task_id": item.source_task_id,
        "ledgered": False,
        "kind": "on_disk_unledgered_real_binary",
        "note": _UNLEDGERED_NOTES[modality],
    }
    if selected is None:
        return {
            "status": "blocked",
            "bytes": None,
            "sha256": None,
            "download_url": None,
            "blocked_reason": reason,
            "provenance": provenance,
        }
    data = selected.read_bytes()
    return {
        "status": "blocked",
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "download_url": f"/platform/deliverable/artifacts/{modality}",
        "blocked_reason": reason,
        "provenance": provenance,
    }


def _not_attempted_payload() -> dict[str, Any]:
    return {
        "status": "blocked",
        "bytes": None,
        "sha256": None,
        "download_url": None,
        "blocked_reason": _NOT_ATTEMPTED_REASON,
        "provenance": {
            "source_task_id": None,
            "ledgered": False,
            "kind": "not_attempted",
            "note": _NOT_ATTEMPTED_REASON,
        },
    }


def _resolve_download(account: str, modality: Modality) -> dict[str, Any]:
    if modality == "document":
        artifact = resolve_ledger_artifact(account, "document")
        return {"path": artifact.path, "content_type": _CONTENT_TYPES[modality]}
    if modality in {"slides", "poster"}:
        # Re-check the source ledger row and sha before exposing the converted binary.
        resolve_ledger_artifact(account, modality)
        materialized = resolve_materialized_artifact(account, modality)
        if materialized is None:
            raise MaterializationError("materialized artifact missing")
        return {"path": materialized.path, "content_type": _CONTENT_TYPES[modality]}
    if modality in _UNLEDGERED_EXTENSIONS:
        selected = _select_unledgered_binary(account, modality)
        if selected is None:
            raise FileNotFoundError(modality)
        return {"path": selected, "content_type": _CONTENT_TYPES[modality]}
    raise FileNotFoundError(modality)


def _select_unledgered_binary(account: str, modality: Modality) -> Path | None:
    item = _DELIVERABLE_PLAN[modality]
    if item.source_task_id is None:
        return None
    extension = _UNLEDGERED_EXTENSIONS[modality]
    artifact_dir = resolve_user_path(account, f"tasks/{item.source_task_id}/artifacts")
    account_root = resolve_user_path(account, ".")
    if not artifact_dir.is_dir() or not artifact_dir.is_relative_to(account_root):
        return None
    matches = [
        path
        for path in artifact_dir.iterdir()
        if path.suffix.lower() == extension and path.is_file() and path.is_relative_to(account_root)
    ]
    if not matches:
        return None
    selected = sorted(matches, key=lambda path: path.name)[-1]
    if not selected.is_file() or not selected.is_relative_to(account_root):
        return None
    return selected


def _blocked_reason_from_ledger(account: str, modality: Modality) -> str:
    item = _DELIVERABLE_PLAN[modality]
    if item.source_task_id is None:
        return _NOT_ATTEMPTED_REASON
    try:
        rows = _ledger_rows(account, item.source_task_id)
    except Exception:
        return _FALLBACK_BLOCKED_REASONS[modality]
    for row in reversed(rows):
        payload = row.get("payload")
        if not isinstance(payload, dict):
            continue
        reason = payload.get("reason")
        if isinstance(reason, str) and reason:
            return reason
        redacted = payload.get("redacted_payload")
        if isinstance(redacted, dict):
            redacted_reason = redacted.get("reason")
            if isinstance(redacted_reason, str) and redacted_reason:
                return redacted_reason
    return _FALLBACK_BLOCKED_REASONS[modality]


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")


__all__ = ["register_platform_deliverable_routes"]

# SPDX-License-Identifier: Apache-2.0
"""Dashboard route backed by safe local read state."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request

from noeticbraid_backend.api.deps import get_settings
from noeticbraid_backend.approval.queue_store import ApprovalQueueStore
from noeticbraid_backend.contracts import EmptyDashboard

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["dashboard"])

_FORBIDDEN_PUBLIC_KEYS = frozenset(
    {
        "account_id",
        "token_id",
        "token_hash",
        "raw_token",
        "dpapi_blob",
        "credential_path",
        "profile_path",
        "profile_dir",
        "browser_profile",
        "startup_secret",
    }
)
_FORBIDDEN_PUBLIC_TEXT_MARKERS = (
    "account_id",
    "token_id",
    "token_hash",
    "raw_token",
    "raw token",
    "bearer ",
    "dpapi",
    "dpapi_blob",
    "credential",
    "credential_path",
    "private/",
    "\\private\\",
    "c:\\users\\",
    "\\appdata\\",
    "/users/",
    "/home/",
    "~/",
    "browser profile",
    "profile_path",
    "profile_dir",
    "startup secret",
    ".git",
)
_SAFE_DIFF_REF_PATTERNS = (
    re.compile(r"^[0-9a-f]{7,40}$", re.IGNORECASE),
    re.compile(r"^git:[0-9a-f]{7,40}$", re.IGNORECASE),
    re.compile(r"^sha256:[0-9a-f]{64}$", re.IGNORECASE),
)


@router.get("/dashboard/empty", response_model=EmptyDashboard, summary="Empty dashboard state")
async def dashboard_empty(request: Request) -> EmptyDashboard:
    """Return the dashboard wrapper, populated only with safe read-state arrays."""

    approvals = _safe_pending_approvals(get_settings(request).state_dir)
    return EmptyDashboard(tasks=[], approvals=approvals, accounts=[])


def _safe_pending_approvals(state_dir: Path) -> list[dict[str, Any]]:
    """Read public pending approval records without leaking account or token material."""

    try:
        store = ApprovalQueueStore(state_dir)
        approvals: list[dict[str, Any]] = []
        for record in store.iter_pending():
            payload = record.model_dump(mode="json")
            if _contains_forbidden_public_material(payload):
                LOGGER.warning("dashboard approval omitted from public summary due to sensitive marker")
                continue
            approvals.append(payload)
        return approvals
    except Exception as exc:
        LOGGER.warning("dashboard approval summary degraded: %s", type(exc).__name__)
        return []


def _contains_forbidden_public_material(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized_key = str(key).lower()
            if normalized_key in _FORBIDDEN_PUBLIC_KEYS:
                return True
            if any(marker in normalized_key for marker in _FORBIDDEN_PUBLIC_TEXT_MARKERS):
                return True
            if normalized_key == "diff_ref" and not _is_safe_public_diff_ref(child):
                return True
            if _contains_forbidden_public_material(child):
                return True
        return False
    if isinstance(value, list):
        return any(_contains_forbidden_public_material(child) for child in value)
    if isinstance(value, str):
        normalized_value = value.lower()
        return any(marker in normalized_value for marker in _FORBIDDEN_PUBLIC_TEXT_MARKERS)
    return False


def _is_safe_public_diff_ref(value: Any) -> bool:
    if value is None:
        return True
    if not isinstance(value, str):
        return False
    normalized_value = value.strip()
    if not normalized_value:
        return True
    return any(pattern.fullmatch(normalized_value) for pattern in _SAFE_DIFF_REF_PATTERNS)


__all__ = ["dashboard_empty", "_safe_pending_approvals"]

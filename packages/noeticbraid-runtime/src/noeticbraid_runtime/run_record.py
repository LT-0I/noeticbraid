# SPDX-License-Identifier: Apache-2.0
"""RunRecord-compatible artifact reference helpers for C2 runtime events."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Literal

_SAFE_REF_RE = re.compile(r"[^A-Za-z0-9_]+")
_FROZEN_EVENT_TYPES = frozenset({"artifact_created", "profile_health_checked", "task_failed"})


def runtime_artifact_refs(
    *,
    tab_id: str | None = None,
    cdp_port: int | None = None,
    process_pid: int | None = None,
) -> list[str]:
    """Build artifact refs that satisfy frozen RunRecord `artifact_` prefix rules."""

    refs: list[str] = []
    if tab_id:
        refs.append(f"artifact_c2_tab_{_safe_ref_part(tab_id)}")
    if cdp_port is not None:
        refs.append(f"artifact_c2_cdp_port_{int(cdp_port)}")
    if process_pid is not None:
        refs.append(f"artifact_c2_process_pid_{int(process_pid)}")
    return refs


def runtime_event_payload(
    *,
    run_id: str,
    task_id: str,
    artifact_refs: list[str],
    event_type: Literal["artifact_created", "profile_health_checked", "task_failed"] = "artifact_created",
    actor: Literal["system", "local_review"] = "system",
    status: Literal["draft", "recorded", "failed"] = "draft",
    created_at: datetime | None = None,
) -> dict[str, object]:
    """Return a compact RunRecord-shaped payload without introducing new enums."""

    if event_type not in _FROZEN_EVENT_TYPES:
        raise ValueError(f"event_type not in frozen RunRecord enum: {event_type}")
    timestamp = created_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    else:
        timestamp = timestamp.astimezone(timezone.utc)
    return {
        "run_id": run_id,
        "task_id": task_id,
        "event_type": event_type,
        "actor": actor,
        "artifact_refs": list(artifact_refs),
        "status": status,
        "created_at": timestamp.isoformat(),
    }


def _safe_ref_part(value: str) -> str:
    cleaned = _SAFE_REF_RE.sub("_", value.strip()).strip("_")
    return cleaned or "unknown"


__all__ = ["runtime_artifact_refs", "runtime_event_payload"]

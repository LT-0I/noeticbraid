# SPDX-License-Identifier: Apache-2.0
"""Deterministic lesson matcher for the OMC task reuse loop."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .project_store import OMCProjectStore


def find_matching_lessons(
    store: OMCProjectStore,
    task_source_refs: list[str],
    *,
    exclude_candidate_id: str | None = None,
) -> list[dict[str, Any]]:
    """Return candidates whose source_refs intersect task_source_refs, ordered."""

    task_refs = set(task_source_refs)
    matches: list[dict[str, Any]] = []
    for candidate in store.candidates():
        if candidate.get("candidate_id") == exclude_candidate_id:
            continue
        candidate_source_refs = candidate["source_refs"]
        if not isinstance(candidate_source_refs, list):
            raise TypeError("candidate.source_refs must be a list")
        if set(candidate_source_refs) & task_refs:
            matches.append(candidate)
    return sorted(matches, key=_sort_key)


def _sort_key(candidate: dict[str, Any]) -> tuple[int, int, float, str]:
    status = candidate.get("status")
    if status == "adopted":
        secondary = _parse_datetime(candidate.get("adopted_at"))
    else:
        r6_gate = candidate.get("r6_gate") or {}
        if not isinstance(r6_gate, dict):
            raise TypeError("candidate.r6_gate must be an object when present")
        secondary = _parse_datetime(r6_gate.get("adopted_at"))
    return (
        0 if status == "adopted" else 1,
        0 if secondary is not None else 1,
        -secondary.timestamp() if secondary is not None else 0.0,
        str(candidate["candidate_id"]),
    )


def _parse_datetime(value: object | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _ensure_utc(value)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    return _ensure_utc(datetime.fromisoformat(text))


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


__all__ = ["find_matching_lessons"]

# SPDX-License-Identifier: Apache-2.0
"""Shared platform ledger readers for artifact-facing read routes."""

from __future__ import annotations

import json
from typing import Any

from noeticbraid_backend.platform.ledger.writer import ledger_path_for


def _ledger_rows(account: str, task_id: str) -> list[dict[str, Any]]:
    path = ledger_path_for(account, task_id)
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError("ledger row must be an object")
        rows.append(row)
    return rows


def _artifact_events(account: str, task_id: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for row in _ledger_rows(account, task_id):
        if row.get("type") != "artifact_produced":
            continue
        payload = row.get("payload")
        if isinstance(payload, dict):
            events.append(payload)
    return events


__all__ = ["_artifact_events", "_ledger_rows"]

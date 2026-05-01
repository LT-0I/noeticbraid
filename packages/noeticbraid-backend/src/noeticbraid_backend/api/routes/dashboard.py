# SPDX-License-Identifier: Apache-2.0
"""Dashboard route skeleton."""

from __future__ import annotations

from fastapi import APIRouter

from noeticbraid_backend.contracts import EmptyDashboard

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard/empty", response_model=EmptyDashboard, summary="Empty dashboard state")
async def dashboard_empty() -> EmptyDashboard:
    """Return the frozen empty dashboard fixture."""

    return EmptyDashboard(tasks=[], approvals=[], accounts=[])

# SPDX-License-Identifier: Apache-2.0
"""Approval route skeleton."""

from __future__ import annotations

from fastapi import APIRouter

from noeticbraid_backend.contracts import ApprovalQueue

router = APIRouter(prefix="/api", tags=["approval"])


@router.get("/approval/queue", response_model=ApprovalQueue, summary="List approval queue")
async def approval_queue() -> ApprovalQueue:
    """Return an empty approval queue fixture."""

    return ApprovalQueue(approvals=[])

# SPDX-License-Identifier: Apache-2.0
"""Approval queue routes."""

from __future__ import annotations

from fastapi import APIRouter, Request

from noeticbraid_backend.api.deps import get_settings
from noeticbraid_backend.approval.queue_store import ApprovalQueueStore
from noeticbraid_backend.contracts import ApprovalQueue

router = APIRouter(prefix="/api", tags=["approval"])


@router.get("/approval/queue", response_model=ApprovalQueue, summary="List approval queue")
async def approval_queue(request: Request) -> ApprovalQueue:
    """Return pending user-decision approval records from local state."""

    store = ApprovalQueueStore(get_settings(request).state_dir)
    approvals = [record.model_dump(mode="json") for record in store.iter_pending()]
    return ApprovalQueue(approvals=approvals)

# SPDX-License-Identifier: Apache-2.0
"""Workspace route skeleton."""

from __future__ import annotations

from fastapi import APIRouter

from noeticbraid_backend.contracts import WorkspaceThreads

router = APIRouter(prefix="/api", tags=["workspace"])


@router.get("/workspace/threads", response_model=WorkspaceThreads, summary="List workspace threads")
async def workspace_threads() -> WorkspaceThreads:
    """Return an empty workspace thread fixture."""

    return WorkspaceThreads(threads=[])

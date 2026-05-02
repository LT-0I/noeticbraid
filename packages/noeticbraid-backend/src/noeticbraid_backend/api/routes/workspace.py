# SPDX-License-Identifier: Apache-2.0
"""Workspace route with explicit Stage 2.3 thread-source deferral."""

from __future__ import annotations

from fastapi import APIRouter

from noeticbraid_backend.contracts import WorkspaceThreads

router = APIRouter(prefix="/api", tags=["workspace"])

WORKSPACE_THREAD_SOURCE_DECISION = (
    "Stage 2.3 has no stable non-ledger workspace/task source; RunRecord rows are not Task-compatible."
)


@router.get("/workspace/threads", response_model=WorkspaceThreads, summary="List workspace threads")
async def workspace_threads() -> WorkspaceThreads:
    """Return an explicit empty thread list until a Task-compatible source is connected."""

    return WorkspaceThreads(threads=_workspace_threads_from_configured_sources())


def _workspace_threads_from_configured_sources() -> list[dict[str, object]]:
    """Defer durable workspace derivation instead of synthesizing Task dictionaries."""

    return []


__all__ = ["WORKSPACE_THREAD_SOURCE_DECISION", "workspace_threads"]

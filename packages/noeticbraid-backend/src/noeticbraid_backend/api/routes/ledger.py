# SPDX-License-Identifier: Apache-2.0
"""Run-ledger route skeleton."""

from __future__ import annotations

from fastapi import APIRouter

from noeticbraid_backend.contracts import RunLedgerRuns

router = APIRouter(prefix="/api", tags=["ledger"])


@router.get("/ledger/runs", response_model=RunLedgerRuns, summary="List run records")
async def ledger_runs() -> RunLedgerRuns:
    """Return an empty run-ledger fixture."""

    return RunLedgerRuns(runs=[])

# SPDX-License-Identifier: Apache-2.0
"""Run-ledger route backed by local Phase 1.1 ledger storage."""

from __future__ import annotations

from fastapi import APIRouter, Request

from noeticbraid_backend.contracts import RunLedgerRuns
from noeticbraid_backend.storage.factories import create_run_ledger

router = APIRouter(prefix="/api", tags=["ledger"])


@router.get(
    "/ledger/runs",
    response_model=RunLedgerRuns,
    summary="List run records",
    operation_id="ledger_runs_api_ledger_runs_get",
)
async def ledger_runs(request: Request) -> RunLedgerRuns:
    """Return run records from ``{settings.state_dir}/ledger/run_ledger.jsonl``."""

    settings = request.app.state.settings
    ledger = create_run_ledger(root=settings.state_dir.parent)
    runs = [record.model_dump(mode="json") for record in ledger.iter_all()]
    return RunLedgerRuns(runs=runs)

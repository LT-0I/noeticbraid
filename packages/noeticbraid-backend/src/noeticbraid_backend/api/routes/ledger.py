# SPDX-License-Identifier: Apache-2.0
"""Run-ledger route backed by local Phase 1.1 ledger storage."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from noeticbraid_backend.contracts import RunLedgerRuns
from noeticbraid_backend.storage.factories import create_run_ledger
from noeticbraid_core.ledger import RunRecordAggregator
from noeticbraid_core.schemas import RunRecordAggregate

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


@router.get(
    "/ledger/runs/aggregate",
    response_model=RunRecordAggregate,
    summary="Aggregate run record",
    operation_id="aggregate_run_record_api_ledger_runs_aggregate_get",
)
async def aggregate_run_record(
    request: Request,
    run_id: str = Query(..., pattern=r"^run_[A-Za-z0-9_]+$", max_length=128),
) -> RunRecordAggregate:
    """Return a best-effort aggregate view for one run_id."""

    settings = request.app.state.settings
    ledger = create_run_ledger(root=settings.state_dir.parent)
    events = [record for record in ledger.iter_all() if record.run_id == run_id]
    return RunRecordAggregator.group_by_run_id(events, run_id=run_id, task_id=None)

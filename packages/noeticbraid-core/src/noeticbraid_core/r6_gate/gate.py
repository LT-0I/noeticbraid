"""Pure R-6 candidate→confirmed gate evaluation helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from .state import R6GateState

R6_GATE_DEFAULT_TTL_DAYS = 30
R6GateStatus = Literal["candidate", "confirmed", "expired"]


def evaluate_r6_gate(state: R6GateState | None, *, now: datetime | None = None) -> R6GateStatus:
    """Evaluate an R-6 gate state without mutating it.

    R-6 allows confirmation only through explicit adoption or reproducible reuse
    evidence (reuse >=3 and at least one independently checkable ledger ref).
    Expiry applies only to candidates that are not already confirmed.
    """

    if state is None:
        return "candidate"
    if state.adopted_at is not None:
        return "confirmed"
    if state.reuse_count >= 3 and len(state.ledger_evidence_refs) >= 1:
        return "confirmed"
    if state.expires_at is not None and _ensure_utc(now or datetime.now(timezone.utc)) > state.expires_at:
        return "expired"
    return "candidate"


def record_reuse(state: R6GateState | None, ledger_run_id: str) -> R6GateState:
    """Return an updated gate state with deduped ledger evidence.

    ``reuse_count`` is derived from the deduped ``ledger_evidence_refs`` list to
    prevent counter/ref drift in callers that use this helper.
    """

    ledger_ref = str(ledger_run_id).strip()
    if not ledger_ref:
        raise ValueError("ledger_run_id must not be blank")
    base = state or R6GateState()
    refs = list(base.ledger_evidence_refs)
    if ledger_ref not in refs:
        refs.append(ledger_ref)
    return R6GateState(
        reuse_count=len(refs),
        ledger_evidence_refs=refs,
        adopted_at=base.adopted_at,
        expires_at=base.expires_at,
        r6_gate_schema_version=base.r6_gate_schema_version,
    )


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)

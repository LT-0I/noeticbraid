from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from noeticbraid_core.r6_gate import R6_GATE_DEFAULT_TTL_DAYS, R6GateState, evaluate_r6_gate, record_reuse

NOW = datetime(2026, 5, 12, 12, 0, tzinfo=timezone.utc)


def test_default_state_is_candidate() -> None:
    assert evaluate_r6_gate(R6GateState(), now=NOW) == "candidate"


def test_adopted_at_set_confirms() -> None:
    state = R6GateState(adopted_at=NOW)

    assert evaluate_r6_gate(state, now=NOW) == "confirmed"


def test_three_reuses_with_ledger_confirms() -> None:
    state = R6GateState(reuse_count=3, ledger_evidence_refs=["run_alpha", "run_beta", "run_gamma"])

    assert evaluate_r6_gate(state, now=NOW) == "confirmed"


def test_reuse_count_without_matching_ledger_refs_is_rejected() -> None:
    with pytest.raises(ValueError, match="reuse_count must equal"):
        R6GateState(reuse_count=3, ledger_evidence_refs=[])


def test_two_reuses_stays_candidate() -> None:
    state = R6GateState(reuse_count=2, ledger_evidence_refs=["run_alpha", "run_beta"])

    assert evaluate_r6_gate(state, now=NOW) == "candidate"


def test_expired_when_past_ttl_not_confirmed() -> None:
    state = R6GateState(expires_at=NOW - timedelta(seconds=1))

    assert evaluate_r6_gate(state, now=NOW) == "expired"


def test_expired_does_not_apply_when_already_confirmed() -> None:
    state = R6GateState(adopted_at=NOW - timedelta(days=1), expires_at=NOW - timedelta(seconds=1))

    assert evaluate_r6_gate(state, now=NOW) == "confirmed"


def test_record_reuse_appends_ledger_ref() -> None:
    state = record_reuse(R6GateState(), "run_alpha")

    assert state.ledger_evidence_refs == ["run_alpha"]
    assert state.reuse_count == 1


def test_record_reuse_dedupes_same_ledger_ref() -> None:
    state = record_reuse(record_reuse(R6GateState(), "run_alpha"), "run_alpha")

    assert state.ledger_evidence_refs == ["run_alpha"]
    assert state.reuse_count == 1


def test_adopted_at_takes_priority_over_expiry() -> None:
    state = R6GateState(adopted_at=NOW, reuse_count=0, ledger_evidence_refs=[], expires_at=NOW - timedelta(days=1))

    assert evaluate_r6_gate(state, now=NOW) == "confirmed"


def test_ttl_default_is_30_days() -> None:
    assert R6_GATE_DEFAULT_TTL_DAYS == 30


def test_reuse_count_equals_len_ledger_refs() -> None:
    state = R6GateState()
    for ref in ["run_alpha", "run_beta", "run_alpha", "run_gamma"]:
        state = record_reuse(state, ref)

    assert state.ledger_evidence_refs == ["run_alpha", "run_beta", "run_gamma"]
    assert state.reuse_count == len(state.ledger_evidence_refs) == 3
    assert evaluate_r6_gate(state, now=NOW) == "confirmed"

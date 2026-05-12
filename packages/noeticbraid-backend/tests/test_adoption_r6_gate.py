# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parent.parent
for path in (
    REPO_ROOT / "packages" / "noeticbraid-core" / "src",
    PACKAGE_ROOT / "src",
):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from noeticbraid_backend.omc_workspace.adoption import adopt_candidate, record_reuse
from noeticbraid_backend.omc_workspace.project_store import DEFAULT_UPGRADE_RULE, OMCProjectStore
from noeticbraid_core.r6_gate import R6GateState, evaluate_r6_gate
from noeticbraid_core.schemas import CandidateLesson


def _candidate(candidate_id: str = "memory_alpha", *, r6_gate: R6GateState | None = None) -> dict[str, object]:
    return CandidateLesson(
        candidate_id=candidate_id,
        project_id="omc-ingest",
        source_sdd_ids=["SDD-D2-01", "SDD-D2-02"],
        summary="candidate lesson for R6 gate tests",
        status="candidate",
        upgrade_rule=DEFAULT_UPGRADE_RULE,
        adopted_at=None,
        adopted_by=None,
        run_record_ref=f"run_{candidate_id}",
        reuse_evidence_refs=[],
        artifact_refs=["artifact_convergence_alpha"],
        source_refs=["source_omc_metadata"],
        r6_gate=r6_gate,
    ).model_dump(mode="json")


def test_adopt_writes_gate_adopted_at(tmp_path: Path) -> None:
    adopted = adopt_candidate(
        _candidate(r6_gate=R6GateState(expires_at=datetime.now(timezone.utc) + timedelta(days=1))),
        project_root=tmp_path,
        actor="user",
    )

    candidate = CandidateLesson.model_validate(adopted["candidate"])
    assert candidate.adopted_at is not None
    assert candidate.r6_gate is not None
    assert candidate.r6_gate.adopted_at == candidate.adopted_at
    assert evaluate_r6_gate(candidate.r6_gate) == "confirmed"


def test_record_reuse_writes_state(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    store = OMCProjectStore(state_dir)
    store.upsert_candidate(_candidate(r6_gate=R6GateState()))

    result = record_reuse("memory_alpha", "run_reuse_001", state_dir=state_dir)

    stored = CandidateLesson.model_validate(store.find_candidate("memory_alpha"))
    assert result["gate_status"] == "candidate"
    assert stored.r6_gate is not None
    assert stored.r6_gate.ledger_evidence_refs == ["run_reuse_001"]
    assert stored.r6_gate.reuse_count == 1


def test_three_reuses_plus_ledger_returns_confirmed(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    store = OMCProjectStore(state_dir)
    store.upsert_candidate(_candidate(r6_gate=R6GateState()))

    record_reuse("memory_alpha", "run_reuse_001", state_dir=state_dir)
    record_reuse("memory_alpha", "run_reuse_002", state_dir=state_dir)
    result = record_reuse("memory_alpha", "run_reuse_003", state_dir=state_dir)

    stored = CandidateLesson.model_validate(store.find_candidate("memory_alpha"))
    assert result["gate_status"] == "confirmed"
    assert stored.r6_gate is not None
    assert stored.r6_gate.reuse_count == 3
    assert stored.r6_gate.ledger_evidence_refs == ["run_reuse_001", "run_reuse_002", "run_reuse_003"]


def test_legacy_candidates_without_gate_state_default_to_candidate(tmp_path: Path) -> None:
    store = OMCProjectStore(tmp_path / "state")
    store.upsert_candidate(_candidate(r6_gate=None))

    stored = CandidateLesson.model_validate(store.find_candidate("memory_alpha"))

    assert stored.r6_gate is None
    assert evaluate_r6_gate(stored.r6_gate) == "candidate"

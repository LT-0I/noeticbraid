# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parent.parent
for path in (
    REPO_ROOT / "packages" / "noeticbraid-core" / "src",
    PACKAGE_ROOT / "src",
):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from noeticbraid_backend.omc_workspace.lesson_matcher import find_matching_lessons
from noeticbraid_backend.omc_workspace.project_store import DEFAULT_UPGRADE_RULE, OMCProjectStore
from noeticbraid_core.r6_gate import R6GateState
from noeticbraid_core.schemas import CandidateLesson


def _empty_store(tmp_path: Path) -> OMCProjectStore:
    store = OMCProjectStore(tmp_path / "state")
    state = store.load()
    state["_seed_initialized"] = True
    state["candidates"] = []
    state["adopted_history"] = []
    state["project"]["candidate_refs"] = []
    state["project"]["adopted_candidate_refs"] = []
    state["project"]["run_refs"] = []
    store.save(state)
    return store


def _candidate(
    candidate_id: str,
    source_refs: list[str],
    *,
    status: str = "candidate",
    adopted_at: datetime | None = None,
    gate_adopted_at: datetime | None = None,
) -> dict[str, object]:
    artifact_refs = [f"artifact_convergence_{candidate_id}"]
    if status == "adopted":
        artifact_refs.append(f".omx/artifacts/candidate-adoption-{candidate_id}-test.md")
    return CandidateLesson(
        candidate_id=candidate_id,
        project_id="omc-ingest",
        source_sdd_ids=["SDD-D2-01", "SDD-D2-02"],
        summary=f"{candidate_id} matcher fixture",
        status=status,  # type: ignore[arg-type]
        upgrade_rule=DEFAULT_UPGRADE_RULE,
        adopted_at=adopted_at,
        adopted_by="test" if status == "adopted" else None,
        run_record_ref=f"run_{candidate_id}",
        reuse_evidence_refs=[],
        artifact_refs=artifact_refs,
        source_refs=source_refs,
        r6_gate=R6GateState(adopted_at=gate_adopted_at),
    ).model_dump(mode="json")


def test_empty_store_returns_no_matches(tmp_path: Path) -> None:
    store = _empty_store(tmp_path)

    assert find_matching_lessons(store, ["source_alpha"], exclude_candidate_id="memory_new") == []


def test_zero_source_ref_intersection_returns_no_matches(tmp_path: Path) -> None:
    store = _empty_store(tmp_path)
    store.upsert_candidate(_candidate("memory_alpha", ["source_alpha"]))

    assert find_matching_lessons(store, ["source_beta"], exclude_candidate_id="memory_new") == []


def test_single_intersecting_candidate_returns_one_entry(tmp_path: Path) -> None:
    store = _empty_store(tmp_path)
    store.upsert_candidate(_candidate("memory_alpha", ["source_alpha", "source_beta"]))

    matches = find_matching_lessons(store, ["source_beta"], exclude_candidate_id="memory_new")

    assert [match["candidate_id"] for match in matches] == ["memory_alpha"]


def test_adopted_candidate_sorts_before_candidate(tmp_path: Path) -> None:
    store = _empty_store(tmp_path)
    store.upsert_candidate(
        _candidate(
            "memory_candidate",
            ["source_shared"],
            gate_adopted_at=datetime(2026, 5, 14, tzinfo=timezone.utc),
        )
    )
    store.upsert_candidate(
        _candidate(
            "memory_adopted",
            ["source_shared"],
            status="adopted",
            adopted_at=datetime(2026, 5, 12, tzinfo=timezone.utc),
        )
    )

    matches = find_matching_lessons(store, ["source_shared"], exclude_candidate_id="memory_new")

    assert [match["candidate_id"] for match in matches] == ["memory_adopted", "memory_candidate"]


def test_exclude_candidate_id_removes_self_match(tmp_path: Path) -> None:
    store = _empty_store(tmp_path)
    store.upsert_candidate(_candidate("memory_alpha", ["source_alpha"]))

    matches = find_matching_lessons(store, ["source_alpha"], exclude_candidate_id="memory_alpha")

    assert matches == []


def test_tie_breaks_by_candidate_id_ascending(tmp_path: Path) -> None:
    store = _empty_store(tmp_path)
    store.upsert_candidate(_candidate("memory_zeta", ["source_shared"]))
    store.upsert_candidate(_candidate("memory_alpha", ["source_shared"]))

    matches = find_matching_lessons(store, ["source_shared"], exclude_candidate_id="memory_new")

    assert [match["candidate_id"] for match in matches] == ["memory_alpha", "memory_zeta"]

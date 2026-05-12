from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from noeticbraid_core.schemas import CandidateLesson


def test_candidate_lesson_requires_r6_upgrade_rule(load_schema_fixture) -> None:
    data = load_schema_fixture("omc_candidate_lesson")
    data["upgrade_rule"] = "not denied becomes confirmed"

    with pytest.raises(ValidationError):
        CandidateLesson.model_validate(data)


def test_explicit_adoption_sets_adopted_at_and_run_record_ref(load_schema_fixture) -> None:
    data = load_schema_fixture("omc_candidate_lesson")
    data.update(
        {
            "status": "adopted",
            "adopted_at": datetime(2026, 5, 12, 12, 0, tzinfo=timezone.utc).isoformat(),
            "adopted_by": "user",
            "run_record_ref": "run_omc_ingest_demo",
            "artifact_refs": [
                "artifact_convergence_markdown",
                ".omx/artifacts/candidate-adoption-memory_omc_ingest_debate_loop-20260512T120000Z.md",
            ],
        }
    )

    candidate = CandidateLesson.model_validate(data)

    assert candidate.status == "adopted"
    assert candidate.adopted_at is not None
    assert candidate.run_record_ref == "run_omc_ingest_demo"


def test_candidate_adoption_artifact_ref_is_narrative_markdown(load_schema_fixture) -> None:
    data = load_schema_fixture("omc_candidate_lesson")
    path = ".omx/artifacts/candidate-adoption-memory_omc_ingest_debate_loop-20260512T120000Z.md"
    data.update(
        {
            "status": "confirmed",
            "adopted_at": "2026-05-12T12:00:00Z",
            "adopted_by": "user",
            "artifact_refs": [path],
        }
    )

    candidate = CandidateLesson.model_validate(data)

    assert candidate.adoption_artifact_refs() == [path]

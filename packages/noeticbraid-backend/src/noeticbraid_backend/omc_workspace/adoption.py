# SPDX-License-Identifier: Apache-2.0
"""Explicit UI-triggered OMC candidate adoption."""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from noeticbraid_core.ledger import RunLedger
from noeticbraid_core.schemas import CandidateLesson, RunRecord

from .project_store import DEFAULT_UPGRADE_RULE


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def timestamp_slug(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def safe_ref_slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_") or "candidate"


def artifact_dir(project_root: Path) -> Path:
    preferred = project_root / ".omx" / "artifacts"
    try:
        preferred.mkdir(parents=True, exist_ok=True)
        return preferred
    except OSError:
        fallback = os.getenv("NOETICBRAID_ARTIFACTS_DIR")
        if fallback:
            path = Path(fallback)
            path.mkdir(parents=True, exist_ok=True)
            return path
        raise


def adopt_candidate(candidate: dict[str, Any], *, project_root: Path, actor: str = "user") -> dict[str, Any]:
    """Mark a candidate adopted only because the UI POST explicitly requested it."""

    prior = CandidateLesson.model_validate(candidate)
    moment = utc_now()
    slug = timestamp_slug(moment)
    directory = artifact_dir(project_root)
    artifact_path = directory / f"candidate-adoption-{prior.candidate_id}-{slug}.md"
    run_record_ref = prior.run_record_ref or f"run_{safe_ref_slug(prior.candidate_id)}"
    artifact_text = (
        f"# Candidate adoption\n\n"
        f"- candidate_id: `{prior.candidate_id}`\n"
        f"- adopted_at: `{moment.isoformat().replace('+00:00', 'Z')}`\n"
        f"- adopted_by: `{actor}`\n"
        f"- run_record_ref: `{run_record_ref}`\n\n"
        "This narrative artifact records explicit UI adoption for SDD-D2-02. "
        "It uses existing RunRecord `artifact_created` evidence and does not add a RunRecord event type.\n"
    )
    artifact_path.write_text(artifact_text, encoding="utf-8")
    artifact_ref = f"artifact_candidate_adoption_{safe_ref_slug(prior.candidate_id)}_{slug}"
    ledger = RunLedger(root=project_root)
    ledger.append(
        RunRecord(
            run_id=run_record_ref,
            task_id="task_omc_ingest",
            event_type="artifact_created",
            created_at=moment,
            actor="system",
            model_refs=[],
            source_refs=list(prior.source_refs),
            artifact_refs=[artifact_ref],
            routing_advice=f"SDD-D2-02 explicit UI adoption artifact: {artifact_path}",
            status="recorded",
        )
    )
    artifact_value = str(artifact_path)
    if artifact_path.is_relative_to(project_root):
        artifact_value = str(artifact_path.relative_to(project_root))
    adopted = prior.model_copy(
        update={
            "status": "adopted",
            "adopted_at": moment,
            "adopted_by": actor,
            "run_record_ref": run_record_ref,
            "upgrade_rule": prior.upgrade_rule or DEFAULT_UPGRADE_RULE,
            "artifact_refs": list(dict.fromkeys([*prior.artifact_refs, artifact_value])),
            "reuse_evidence_refs": list(dict.fromkeys([*prior.reuse_evidence_refs, artifact_ref])),
        }
    )
    return {
        "candidate": adopted.model_dump(mode="json"),
        "adopted_at": moment.isoformat().replace("+00:00", "Z"),
        "adoption_artifact_ref": artifact_value,
        "ledger_refs": [run_record_ref, artifact_ref],
    }


__all__ = ["adopt_candidate", "artifact_dir"]

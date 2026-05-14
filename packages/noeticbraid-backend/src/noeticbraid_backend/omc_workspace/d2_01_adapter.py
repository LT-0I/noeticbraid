# SPDX-License-Identifier: Apache-2.0
"""D2-01 public outlet adapter for SDD-D2-02 OMC ingestion tasks."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .adoption import artifact_dir
from .omc_knowledge_extractor import ExtractionResult, Section, extract_omc_knowledge

DEFAULT_OMC_SOURCE_PATHS = (
    Path.home() / ".claude" / "CLAUDE.md",
    Path.home() / ".claude" / "RTK.md",
)
LOCAL_METADATA_SOURCE_REF = "source_omc_local_metadata"
NARRATIVE_ARTIFACT_REF = "artifact_omc_knowledge_extraction"
LIVE_ARTIFACT_REF = "artifact_omx_exec_omc_knowledge"


def run_omc_debate_loop(
    task_card: dict[str, Any],
    *,
    state_root: Path,
    artifact_root: Path,
    mock_invocations: bool = True,
) -> dict[str, Any]:
    """Call the D2-01 public API without modifying SP-B internals."""

    from noeticbraid.tools.multimodel_alliance import run_debate_loop
    from noeticbraid.tools.multimodel_alliance.ledger_bridge import append_ledger_records

    project_root = Path(state_root)
    extraction = extract_omc_knowledge(
        list(DEFAULT_OMC_SOURCE_PATHS),
        live=os.getenv("NOETICBRAID_OMC_EXTRACT_LIVE") == "1",
        artifact_root=artifact_dir(project_root),
    )
    enriched_task_card = _task_card_with_local_source(task_card)

    result = run_debate_loop(
        enriched_task_card,
        state_root=state_root,
        artifact_root=artifact_root,
        mock_invocations=mock_invocations,
        provider_mode=False,
    )
    compact_d2_records = _compact_d2_ledger_records(result)
    public_artifact_refs = _public_extraction_artifact_refs(extraction, project_root=project_root)
    candidate_source_refs = _candidate_source_refs(result["candidate"].get("source_refs", []), extraction.outline)
    candidate_artifact_refs = list(dict.fromkeys([*result["candidate"].get("artifact_refs", []), *public_artifact_refs]))

    result["candidate"]["summary"] = extraction.summary
    result["candidate"]["source_refs"] = candidate_source_refs
    result["candidate"]["artifact_refs"] = candidate_artifact_refs

    for memory_candidate in result.get("convergence", {}).get("memory_candidates", []):
        if memory_candidate.get("candidate_id") == result["candidate"]["candidate_id"]:
            memory_candidate["summary"] = extraction.summary
            memory_candidate["source_refs"] = candidate_source_refs

    result.setdefault("artifact_paths", {})["omc_narrative"] = _artifact_path_from_line_ref(extraction.narrative_artifact_ref)
    if extraction.live_artifact_ref:
        result.setdefault("artifact_paths", {})["omx_exec_enrichment"] = extraction.live_artifact_ref
    result["artifact_refs"] = list(dict.fromkeys([*result.get("artifact_refs", []), *public_artifact_refs]))

    extraction_records = _extraction_ledger_records(
        result,
        extraction=extraction,
        public_artifact_refs=public_artifact_refs,
    )
    if extraction_records:
        append_ledger_records(state_root, extraction_records)
    result["ledger_records"] = [*compact_d2_records, *extraction_records]
    result["ledger_event_types"] = [
        *result.get("ledger_event_types", []),
        *[record["event_type"] for record in extraction_records],
    ]
    return result


def _task_card_with_local_source(task_card: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(task_card)
    enriched["source_refs"] = list(dict.fromkeys([*enriched.get("source_refs", []), LOCAL_METADATA_SOURCE_REF]))
    return enriched


def _candidate_source_refs(existing: list[str], _outline: list[Section]) -> list[str]:
    # CandidateLesson source_refs are reused as RunRecord.source_refs during explicit
    # adoption, so they must remain frozen-contract source_* identifiers. Path:line
    # evidence lives in the narrative artifact generated from the full outline.
    return list(dict.fromkeys([*existing, LOCAL_METADATA_SOURCE_REF]))


def _public_extraction_artifact_refs(extraction: ExtractionResult, *, project_root: Path) -> list[str]:
    refs = [_public_artifact_path(_artifact_path_from_line_ref(extraction.narrative_artifact_ref), project_root=project_root)]
    if extraction.live_artifact_ref:
        refs.append(_public_artifact_path(extraction.live_artifact_ref, project_root=project_root))
    return refs


def _artifact_path_from_line_ref(ref: str) -> str:
    return ref.rsplit(":", 1)[0]


def _public_artifact_path(value: str, *, project_root: Path) -> str:
    path = Path(value)
    try:
        return str(path.relative_to(project_root))
    except ValueError:
        parts = path.parts
        if ".omx" in parts:
            index = parts.index(".omx")
            return str(Path(*parts[index:]))
        return str(path)


def _compact_d2_ledger_records(result: dict[str, Any]) -> list[dict[str, Any]]:
    candidate = result["candidate"]
    run_id = result.get("route", {}).get("run_refs", [None])[0] or f"run_{result['task_id'].removeprefix('task_')}"
    model_refs = _route_model_refs(result)
    return [
        {
            "run_id": run_id,
            "task_id": result["task_id"],
            "event_type": event_type,
            "actor": "system",
            "status": "recorded",
            "artifact_refs": list(candidate.get("artifact_refs", [])),
            "source_refs": list(candidate.get("source_refs", [])),
            "model_refs": model_refs,
            "routing_advice": f"SDD-D2-01 {event_type}",
            "created_at": candidate.get("created_at"),
        }
        for event_type in result.get("ledger_event_types", [])
    ]


def _extraction_ledger_records(
    result: dict[str, Any],
    *,
    extraction: ExtractionResult,
    public_artifact_refs: list[str],
) -> list[dict[str, Any]]:
    candidate = result["candidate"]
    run_id = result.get("route", {}).get("run_refs", [None])[0] or f"run_{result['task_id'].removeprefix('task_')}"
    model_refs = _route_model_refs(result)
    source_refs = [LOCAL_METADATA_SOURCE_REF]
    created_at = candidate.get("created_at")
    narrative_public_ref = public_artifact_refs[0]
    records: list[dict[str, Any]] = [
        {
            "run_id": run_id,
            "task_id": result["task_id"],
            "event_type": "artifact_created",
            "created_at": created_at,
            "actor": "system",
            "model_refs": model_refs,
            "source_refs": source_refs,
            "artifact_refs": [NARRATIVE_ARTIFACT_REF],
            "routing_advice": f"SDD-D3-01 deterministic OMC narrative artifact: {narrative_public_ref}",
            "status": "recorded",
        }
    ]
    if extraction.live_artifact_ref:
        live_public_ref = public_artifact_refs[1]
        records.append(
            {
                "run_id": run_id,
                "task_id": result["task_id"],
                "event_type": "artifact_created",
                "created_at": created_at,
                "actor": "system",
                "model_refs": model_refs,
                "source_refs": source_refs,
                "artifact_refs": [LIVE_ARTIFACT_REF],
                "routing_advice": f"SDD-D3-01 live OMC enrichment artifact: {live_public_ref}",
                "status": "recorded",
            }
        )
    return records


def _route_model_refs(result: dict[str, Any]) -> list[str]:
    return [item["model_ref"] for item in result.get("route", {}).get("selected_models", []) if item.get("model_ref")]


__all__ = ["run_omc_debate_loop"]

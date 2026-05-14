# SPDX-License-Identifier: Apache-2.0
"""D2-01 public outlet adapter for SDD-D2-02 OMC ingestion tasks."""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .adoption import artifact_dir, record_reuse
from .lesson_matcher import find_matching_lessons
from .omc_knowledge_extractor import ExtractionResult, Section, extract_omc_knowledge
from .project_store import OMCProjectStore, candidate_from_d2_result

LOCAL_METADATA_SOURCE_REF = "source_omc_local_metadata"
NARRATIVE_ARTIFACT_REF = "artifact_omc_knowledge_extraction"
LIVE_ARTIFACT_REF = "artifact_omx_exec_omc_knowledge"


def run_omc_debate_loop(
    task_card: dict[str, Any],
    *,
    state_root: Path,
    artifact_root: Path,
    omc_sources: list[tuple[Path, str]],
    store: OMCProjectStore,
    raw_task_card_source_refs: list[str],
    mock_invocations: bool = True,
) -> dict[str, Any]:
    """Call the D2-01 public API without modifying SP-B internals."""

    from noeticbraid.tools.multimodel_alliance import run_debate_loop
    from noeticbraid.tools.multimodel_alliance.ledger_bridge import append_ledger_records

    project_root = Path(state_root)
    extraction = extract_omc_knowledge(
        omc_sources,
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

    original_run_id = _run_id_from_result(result)
    unique_run_id = _unique_submit_run_id(original_run_id, store)
    _apply_submit_run_id(result, unique_run_id)
    new_candidate = candidate_from_d2_result(result)
    matches = find_matching_lessons(
        store,
        raw_task_card_source_refs,
        exclude_candidate_id=new_candidate["candidate_id"],
    )

    compact_d2_records = _compact_d2_ledger_records(result, submit_run_id=unique_run_id)
    extraction_records = _extraction_ledger_records(
        result,
        extraction=extraction,
        public_artifact_refs=public_artifact_refs,
        reuse_lesson_refs=[match["candidate_id"] for match in matches],
    )
    if extraction_records:
        append_ledger_records(state_root, extraction_records)
    result["ledger_records"] = [*compact_d2_records, *extraction_records]
    result["ledger_event_types"] = [
        *result.get("ledger_event_types", []),
        *[record["event_type"] for record in extraction_records],
    ]
    reused_lesson_refs: list[str] = []
    for match in matches:
        record_reuse(match["candidate_id"], unique_run_id, store=store)
        reused_lesson_refs.append(match["candidate_id"])
    result["reused_lesson_refs"] = reused_lesson_refs
    return result


def _run_id_from_result(result: dict[str, Any]) -> str:
    return result.get("run_record_ref") or result.get("route", {}).get("run_refs", [None])[0] or f"run_{result['task_id'].removeprefix('task_')}"


def _apply_submit_run_id(result: dict[str, Any], run_id: str) -> None:
    route = result.setdefault("route", {})
    route["run_refs"] = [run_id, *[ref for ref in route.get("run_refs", [])[1:] if ref != run_id]]
    result["run_record_ref"] = run_id


def _unique_submit_run_id(base_run_id: str, store: OMCProjectStore) -> str:
    used = _used_run_ids(store)
    if base_run_id not in used:
        return base_run_id
    while True:
        timestamp_slug = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        candidate = f"{base_run_id}_{timestamp_slug}"
        if candidate not in used:
            return candidate
        time.sleep(1.0)


def _used_run_ids(store: OMCProjectStore) -> set[str]:
    state = store.load()
    used: set[str] = set()
    for record in state.get("run_records", []):
        run_id = record.get("run_id")
        if run_id:
            used.add(str(run_id))
    for candidate in [*state.get("candidates", []), *state.get("adopted_history", [])]:
        run_ref = candidate.get("run_record_ref")
        if run_ref:
            used.add(str(run_ref))
        r6_gate = candidate.get("r6_gate") or {}
        if isinstance(r6_gate, dict):
            used.update(str(ref) for ref in r6_gate.get("ledger_evidence_refs", []))
    used.update(str(ref) for ref in state.get("project", {}).get("run_refs", []))
    return used


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


def _compact_d2_ledger_records(result: dict[str, Any], *, submit_run_id: str) -> list[dict[str, Any]]:
    candidate = result["candidate"]
    run_refs = result.get("route", {}).get("run_refs")
    if not isinstance(run_refs, list) or not run_refs or not run_refs[0]:
        raise ValueError("cannot compact D2 ledger records without result.route.run_refs[0]")
    run_id = str(run_refs[0])
    model_refs = _route_model_refs(result)
    records: list[dict[str, Any]] = []
    for event_type in result.get("ledger_event_types", []):
        record = {
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
        record["run_id"] = submit_run_id
        records.append(record)
    return records


def _extraction_ledger_records(
    result: dict[str, Any],
    *,
    extraction: ExtractionResult,
    public_artifact_refs: list[str],
    reuse_lesson_refs: list[str],
) -> list[dict[str, Any]]:
    candidate = result["candidate"]
    run_id = result.get("route", {}).get("run_refs", [None])[0] or f"run_{result['task_id'].removeprefix('task_')}"
    model_refs = _route_model_refs(result)
    source_refs = [LOCAL_METADATA_SOURCE_REF]
    created_at = candidate.get("created_at")
    narrative_public_ref = public_artifact_refs[0]
    reuse_advice = _reuse_routing_advice(reuse_lesson_refs)
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
            "routing_advice": f"SDD-D3-01 deterministic OMC narrative artifact: {narrative_public_ref}{reuse_advice}",
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


def _reuse_routing_advice(reuse_lesson_refs: list[str]) -> str:
    if not reuse_lesson_refs:
        return ""
    markers = [f"SDD-D4-01 reuse evidence: {lesson_id}" for lesson_id in reuse_lesson_refs]
    return "; " + "; ".join(markers)


def _route_model_refs(result: dict[str, Any]) -> list[str]:
    return [item["model_ref"] for item in result.get("route", {}).get("selected_models", []) if item.get("model_ref")]


__all__ = ["run_omc_debate_loop"]

# SPDX-License-Identifier: Apache-2.0
"""OMC ingestion project routes for SDD-D2-02."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from noeticbraid_backend.api.deps import get_settings
from noeticbraid_backend.contracts import (
    CandidateAdoptionResponse,
    OMCProjectAdoptedHistory,
    OMCProjectCandidates,
    OMCProjectTaskRequest,
    OMCProjectTaskResponse,
)
from noeticbraid_backend.omc_workspace.adoption import adopt_candidate
from noeticbraid_backend.omc_workspace.d2_01_adapter import run_omc_debate_loop
from noeticbraid_backend.omc_workspace.omc_knowledge_extractor import OMCKnowledgeExtractionError, OMCLiveEnrichmentError
from noeticbraid_backend.omc_workspace.project_store import OMCProjectStore, PROJECT_ID, candidate_from_d2_result, public_artifact_ref

router = APIRouter(prefix="/api", tags=["projects"])


def _store(request: Request) -> OMCProjectStore:
    return OMCProjectStore(get_settings(request).state_dir)


def _project_root(request: Request):
    return get_settings(request).state_dir.parent


@router.post(
    "/projects/omc-ingest/tasks",
    response_model=OMCProjectTaskResponse,
    summary="Submit OMC ingestion task card",
    operation_id="submit_omc_ingest_task_api_projects_omc_ingest_tasks_post",
)
async def submit_omc_ingest_task(request: Request, task: OMCProjectTaskRequest) -> OMCProjectTaskResponse:
    """Run the OMC task card through D2-01 mock/manual-safe adapter and persist candidate evidence."""

    if not task.prompt.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="task prompt is required")
    settings = get_settings(request)
    root = _project_root(request)
    try:
        result = run_omc_debate_loop(
            {
                "task_id": "task_omc_ingest",
                "title": task.title,
                "trigger": "task_card",
                "risk_hint": "high",
                "required_capabilities": ["planning", "adversary", "source_audit", "convergence"],
                "source_refs": task.source_refs
                or ["source_project_definition_v3_2", "source_ai_invocation_reference", "source_omc_metadata"],
                "description": task.prompt,
            },
            state_root=root,
            artifact_root=root / ".omx" / "artifacts",
            omc_sources=settings.omc_sources,
            mock_invocations=True,
        )
    except OMCKnowledgeExtractionError as exc:
        missing = ", ".join(str(path) for path in exc.missing)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"OMC source missing: {missing}") from exc
    except OMCLiveEnrichmentError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OMC live enrichment failed: {exc.reason}",
        ) from exc
    candidate = candidate_from_d2_result(result)
    run_records = list(result.get("ledger_records", []))
    # D2-01 exposes event types and writes JSONL; keep route-visible records compact when the adapter
    # does not expose raw rows in the public return payload.
    if not run_records:
        run_records = [
            {
                "run_id": candidate["run_record_ref"],
                "task_id": result["task_id"],
                "event_type": event_type,
                "actor": "system",
                "status": "recorded",
                "artifact_refs": candidate["artifact_refs"],
                "source_refs": candidate["source_refs"],
                "model_refs": result.get("route", {}).get("model_refs", []),
                "routing_advice": f"SDD-D2-01 {event_type}",
                "created_at": result.get("candidate", {}).get("created_at"),
            }
            for event_type in result.get("ledger_event_types", [])
        ]
    stored_candidate = _store(request).upsert_candidate(candidate, run_records=run_records)
    markdown_ref = public_artifact_ref(str(result.get("artifact_paths", {}).get("convergence_markdown", "")))
    return OMCProjectTaskResponse(
        project_id=PROJECT_ID,
        task_id=result["task_id"],
        candidate_id=stored_candidate["candidate_id"],
        convergence_markdown_ref=markdown_ref,
        run_record_ref=stored_candidate["run_record_ref"],
        artifact_refs=stored_candidate["artifact_refs"],
        candidate=stored_candidate,
        run_records=run_records,
    )


@router.get(
    "/projects/omc-ingest/candidates",
    response_model=OMCProjectCandidates,
    summary="List OMC ingestion candidates",
    operation_id="omc_ingest_candidates_api_projects_omc_ingest_candidates_get",
)
async def omc_ingest_candidates(request: Request) -> OMCProjectCandidates:
    return OMCProjectCandidates(project_id=PROJECT_ID, candidates=_store(request).candidates())


@router.get(
    "/projects/omc-ingest/adopted-history",
    response_model=OMCProjectAdoptedHistory,
    summary="List OMC adopted candidates",
    operation_id="omc_ingest_adopted_history_api_projects_omc_ingest_adopted_history_get",
)
async def omc_ingest_adopted_history(request: Request) -> OMCProjectAdoptedHistory:
    return OMCProjectAdoptedHistory(project_id=PROJECT_ID, adopted_candidates=_store(request).adopted_history())


@router.post(
    "/candidates/{id}/adopt",
    response_model=CandidateAdoptionResponse,
    summary="Adopt OMC candidate explicitly",
    operation_id="adopt_omc_candidate_api_candidates_id_adopt_post",
)
async def adopt_omc_candidate(request: Request, id: str) -> CandidateAdoptionResponse:
    store = _store(request)
    candidate = store.find_candidate(id)
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="candidate not found")
    adopted = adopt_candidate(candidate, project_root=_project_root(request), actor="user")
    stored_candidate = store.adopt_candidate(adopted["candidate"])
    return CandidateAdoptionResponse(
        project_id=PROJECT_ID,
        candidate_id=id,
        status=stored_candidate["status"],
        adopted_at=adopted["adopted_at"],
        adopted_by="user",
        run_record_ref=stored_candidate["run_record_ref"],
        adoption_artifact_ref=adopted["adoption_artifact_ref"],
        ledger_refs=adopted["ledger_refs"],
        candidate=stored_candidate,
    )


__all__ = [
    "submit_omc_ingest_task",
    "omc_ingest_candidates",
    "omc_ingest_adopted_history",
    "adopt_omc_candidate",
]

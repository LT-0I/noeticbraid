# SPDX-License-Identifier: Apache-2.0
"""Authenticated conversational task panel endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Request, status

from noeticbraid_backend.platform.auth import require_platform_bearer
from noeticbraid_backend.platform.conversation import model
from noeticbraid_backend.platform.deliverable.endpoint import _serialize_deliverable
from noeticbraid_backend.platform.elicitation.capabilities import serialize_capabilities
from noeticbraid_backend.platform.elicitation.local_ai import generic_degraded_question, run_elicitation_probe
from noeticbraid_backend.platform.ledger.events import ai_call_event
from noeticbraid_backend.platform.ledger.writer import append_event
from noeticbraid_backend.platform.orchestrate import engine as orchestration_engine
from noeticbraid_backend.platform.orchestrate import state as orchestration_state
from noeticbraid_backend.platform.tasks import store as task_store
from noeticbraid_backend.platform.tasks.models import account_ref_for

_ALLOWED_VIEW_KEYS = frozenset({"conversation", "deliverables", "coarse_status", "capability_notice"})


def register_platform_conversational_routes(platform_app: FastAPI) -> None:
    """Register Phase-1 conversational routes on the mounted sub-app."""

    @platform_app.post("/tasks", summary="Create a conversational platform task")
    async def platform_create_conversational_task(request: Request) -> dict[str, Any]:
        account = require_platform_bearer(request.headers.get("authorization"))
        payload = await _json_body(request)
        title = str(payload.get("title") or "").strip()
        if not title:
            raise _bad_request("title_required")
        try:
            task = task_store.create_task(account, task_id=model.new_task_id(), title=title, modality_targets=[])
            model.initialize_task_files(account, task.task_id)
            view = _view_payload(account, task.task_id)
        except Exception as exc:
            raise _not_found() from exc
        return {"task": _serialize_task(task), "view": view}

    @platform_app.post("/tasks/{task_id}/elicit", summary="Elicit requirements for a platform task")
    async def platform_elicit_task(request: Request, task_id: str) -> dict[str, Any]:
        account = require_platform_bearer(request.headers.get("authorization"))
        payload = await _json_body(request)
        raw_requirement = str(payload.get("raw_requirement") or "").strip()
        if not raw_requirement:
            raise _bad_request("raw_requirement_required")
        try:
            _load_owned_task(account, task_id)
            memory_profile = model.load_memory_profile(account)
            probe = run_elicitation_probe(raw_requirement, memory_profile=memory_profile)
            model.append_conversation_row(account, task_id, role="user", kind="message", text=raw_requirement)
            requirements = model.candidate_requirements_from_probe(raw_requirement, probe)
            model.write_requirements(
                account,
                task_id,
                {
                    "task_id": task_id,
                    "schema_version": model.REQUIREMENTS_SCHEMA_VERSION,
                    "status": "eliciting",
                    "requirements": requirements,
                },
            )
            _append_elicitation_response(account, task_id, raw_requirement, probe)
            if probe.get("ok") is not True:
                _ledger_local_failure(account, task_id, probe)
            view = _view_payload(account, task_id)
        except HTTPException:
            raise
        except Exception as exc:
            raise _not_found() from exc
        return {"view": view}

    @platform_app.post("/tasks/{task_id}/conversation", summary="Append a conversational platform task turn")
    async def platform_continue_conversation(request: Request, task_id: str) -> dict[str, Any]:
        account = require_platform_bearer(request.headers.get("authorization"))
        payload = await _json_body(request)
        text = str(payload.get("text") or "").strip()
        if not text:
            raise _bad_request("text_required")
        try:
            _load_owned_task(account, task_id)
            memory_profile = model.load_memory_profile(account)
            probe = run_elicitation_probe(text, memory_profile=memory_profile)
            model.append_conversation_row(account, task_id, role="user", kind="answer", text=text)
            current = model.load_requirements(account, task_id)
            candidates = model.candidate_requirements_from_probe(text, probe)
            if current.get("status") != "confirmed" and candidates:
                model.write_requirements(
                    account,
                    task_id,
                    {
                        "task_id": task_id,
                        "schema_version": model.REQUIREMENTS_SCHEMA_VERSION,
                        "status": "eliciting",
                        "requirements": candidates,
                    },
                )
            _append_elicitation_response(account, task_id, text, probe)
            if probe.get("ok") is not True:
                _ledger_local_failure(account, task_id, probe)
            view = _view_payload(account, task_id)
        except HTTPException:
            raise
        except Exception as exc:
            raise _not_found() from exc
        return {"view": view}

    @platform_app.post("/tasks/{task_id}/requirements/confirm", summary="Confirm conversational task requirements")
    async def platform_confirm_requirements(request: Request, task_id: str) -> dict[str, Any]:
        account = require_platform_bearer(request.headers.get("authorization"))
        payload = await _json_body(request)
        requirements = payload.get("requirements")
        if not isinstance(requirements, list):
            raise _bad_request("requirements_required")
        try:
            _load_owned_task(account, task_id)
            stamped = model.stamp_confirmed_requirements(task_id, requirements)
            model.write_requirements(account, task_id, stamped)
            conversation = model.serialize_visible_conversation(account, task_id)
            model.persist_memory_from_confirm(account, stamped, conversation)
            for row in model.serialize_coarse_status(stamped):
                if row["coarse_state"] == "blocked":
                    model.append_conversation_row(
                        account,
                        task_id,
                        role="assistant",
                        kind="coarse_status",
                        text=str(row.get("blocked_reason") or row["text"]),
                        requirement_id=str(row["requirement_id"]),
                    )
            view = _view_payload(account, task_id)
        except HTTPException:
            raise
        except Exception as exc:
            raise _not_found() from exc
        return {"requirements": stamped, "view": view}

    @platform_app.post("/tasks/{task_id}/orchestrate", summary="Run confirmed conversational task orchestration")
    async def platform_orchestrate_task(request: Request, task_id: str) -> dict[str, Any]:
        account = require_platform_bearer(request.headers.get("authorization"))
        try:
            _load_owned_task(account, task_id)
            requirements = model.load_requirements(account, task_id)
            if requirements.get("status") != "confirmed":
                raise _bad_request("not_confirmed")
            orchestration_engine.run_orchestration(account, task_id)
            view = _view_payload(account, task_id)
        except HTTPException:
            raise
        except Exception as exc:
            raise _not_found() from exc
        return {"view": view}

    @platform_app.get("/tasks/{task_id}/orchestrate/status", summary="Read conversational task orchestration status")
    async def platform_read_orchestration_status(request: Request, task_id: str) -> dict[str, Any]:
        account = require_platform_bearer(request.headers.get("authorization"))
        try:
            _load_owned_task(account, task_id)
            requirements = model.load_requirements(account, task_id)
            return {
                "coarse_status": model.serialize_coarse_status(requirements),
                "phase": orchestration_state.current_phase(account, task_id, requirements),
            }
        except Exception as exc:
            raise _not_found() from exc

    @platform_app.get("/tasks/{task_id}/view", summary="Read the conversational two-zone task view")
    async def platform_read_conversational_view(request: Request, task_id: str) -> dict[str, Any]:
        account = require_platform_bearer(request.headers.get("authorization"))
        try:
            _load_owned_task(account, task_id)
            view = _view_payload(account, task_id)
        except Exception as exc:
            raise _not_found() from exc
        return view

    @platform_app.get("/capabilities", summary="Read conversational platform capability registry")
    async def platform_read_conversational_capabilities(request: Request) -> dict[str, Any]:
        require_platform_bearer(request.headers.get("authorization"))
        return {"capabilities": serialize_capabilities()}


def _load_owned_task(account: str, task_id: str):
    task = task_store.load_task(account, task_id)
    if task.account_id_ref != account_ref_for(account):
        raise ValueError("task/account binding mismatch")
    return task


def _view_payload(account: str, task_id: str) -> dict[str, Any]:
    requirements = model.load_requirements(account, task_id)
    payload = {
        "conversation": model.serialize_visible_conversation(account, task_id),
        "deliverables": _safe_deliverables(account),
        "coarse_status": model.serialize_coarse_status(requirements),
        "capability_notice": model.capability_notices(requirements),
    }
    if set(payload) != _ALLOWED_VIEW_KEYS:
        raise ValueError("view serializer field drift")
    _assert_no_engineering_keys(payload)
    return payload


def _assert_no_engineering_keys(value: Any) -> None:
    forbidden = {
        "ledger",
        "dispatch",
        "critique",
        "internal_reason",
        "internal-reason",
        "orchestration",
        "rounds",
        "directive",
        "reviewer",
        "verdict",
        "evidence_node_ids",
        "workflow",
        "selector",
    }
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key) in forbidden:
                raise ValueError("view serializer included an engineering field")
            _assert_no_engineering_keys(item)
        return
    if isinstance(value, list):
        for item in value:
            _assert_no_engineering_keys(item)


def _safe_deliverables(account: str) -> list[dict[str, Any]]:
    try:
        deliverable = _serialize_deliverable(account)
    except Exception:
        return []
    return [deliverable]


def _append_elicitation_response(account: str, task_id: str, raw_text: str, probe: dict[str, Any]) -> None:
    if probe.get("ok") is not True:
        question = generic_degraded_question(raw_text)
        model.append_conversation_row(account, task_id, role="assistant", kind="question", text=question["question"])
        return
    questions = model.questions_from_probe(raw_text, probe)
    if questions:
        question = questions[0]
        text = question["question"]
        suggested = question.get("suggested_answer")
        if suggested:
            text = f"{text}\n\nSuggested answer: {suggested}"
        model.append_conversation_row(account, task_id, role="assistant", kind="question", text=text)
        return
    model.append_conversation_row(
        account,
        task_id,
        role="assistant",
        kind="message",
        text="I have enough information to draft the requirement list. Please review and confirm before execution is armed.",
    )


def _ledger_local_failure(account: str, task_id: str, probe: dict[str, Any]) -> None:
    try:
        append_event(
            account,
            ai_call_event(
                task_id,
                op="local_ai_elicitation",
                vendor="local",
                gate_status=str(probe.get("error_type") or "failed"),
                redacted_payload={
                    "status": "degraded",
                    "error_type": str(probe.get("error_type") or "failed"),
                    "reason": str(probe.get("error") or "local model unavailable"),
                },
            ),
        )
    except Exception:
        return


async def _json_body(request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception as exc:
        raise _bad_request("invalid_json") from exc
    if not isinstance(payload, dict):
        raise _bad_request("json_object_required")
    return payload


def _serialize_task(task) -> dict[str, Any]:
    return {
        "task_id": task.task_id,
        "title": task.title,
        "state": task.state.value,
        "created_ts": task.created_ts,
        "updated_ts": task.updated_ts,
        "modality_targets": list(task.modality_targets),
    }


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")


__all__ = ["register_platform_conversational_routes"]

"""Manual multimodel debate loop orchestrator for SDD-D2-01."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .candidate_store import (
    SDD_ID,
    UPGRADE_RULE,
    append_candidate_record,
    assert_safe_output_root,
    build_debate_candidate,
    scan_forbidden_material,
)
from .convergence import converge
from .convergence_markdown import write_convergence_markdown
from .debate_runner import run_debate
from .invocation_plan import build_invocation_plan, execute_invocation_plan
from .ledger_bridge import record_debate_loop_ledger
from .provider_round_parser import ProviderRoundParseError, build_real_rounds
from .schema_loader import FIXTURE_DIR, load_json
from .validator import validate_convergence_record, validate_debate_record, validate_route_record

DEFAULT_MAX_ROUNDS = 5
DEFAULT_MIN_ROUNDS = 3
OMC_MOCK_FIXTURE = FIXTURE_DIR / "omc_debate_loop_mock.json"


class DebateLoopError(ValueError):
    """Raised when a debate loop violates SDD-D2-01 boundaries."""


def _stable_hash(*parts: object, length: int = 12) -> str:
    return hashlib.sha256("|".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:length]


def _slug(value: object, *, default: str = "item", max_length: int = 80) -> str:
    slug = re.sub(r"[^A-Za-z0-9_]+", "_", str(value or "")).strip("_")
    if not slug:
        slug = f"{default}_{_stable_hash(value)}"
    if len(slug) > max_length:
        slug = f"{slug[: max_length - 13].rstrip('_')}_{_stable_hash(slug)}"
    return slug


def _prefixed(prefix: str, value: object, *, default: str = "item", max_length: int = 128) -> str:
    slug = _slug(value, default=default, max_length=max_length - len(prefix) - 1)
    candidate = slug if slug.startswith(prefix + "_") else f"{prefix}_{slug}"
    if len(candidate) > max_length:
        candidate = f"{candidate[: max_length - 13].rstrip('_')}_{_stable_hash(candidate)}"
    return candidate


def _load_task_card(task_card: str | Path | dict[str, Any]) -> dict[str, Any]:
    if isinstance(task_card, dict):
        loaded = copy.deepcopy(task_card)
    else:
        loaded = load_json(Path(task_card))
    if not isinstance(loaded, dict):
        raise DebateLoopError("task card JSON must be an object")
    return loaded


def _ensure_manual_task_trigger(task_card: dict[str, Any]) -> None:
    blocked = {"scheduler", "cron", "on_save", "onsave", "b1_detector", "b_1_detector", "b-1_detector", "b-1"}
    trigger = str(task_card.get("trigger") or "task_card").strip().lower()
    trigger_source = str(task_card.get("trigger_source") or task_card.get("source_trigger") or "").strip().lower()
    if trigger != "task_card" or trigger_source in blocked or trigger in blocked:
        raise DebateLoopError("SDD-D2-01 requires a manual user task-card trigger; scheduler/cron/b-1 triggers are out of scope")
    if task_card.get("auto_trigger") or task_card.get("scheduler") or task_card.get("cron"):
        raise DebateLoopError("SDD-D2-01 rejects automatic debate-loop triggers")


def _source_refs(task_card: dict[str, Any]) -> list[str]:
    refs = task_card.get("source_refs") or task_card.get("sp_h_source_refs") or []
    if not isinstance(refs, list):
        raise DebateLoopError("task_card.source_refs must be a list when provided")
    normalized = [str(ref) for ref in refs]
    if not normalized:
        normalized = ["source_task_card"]
    for ref in normalized:
        if not re.fullmatch(r"source_[A-Za-z0-9_]+", ref):
            raise DebateLoopError(f"source ref must use source_* prefix: {ref}")
    return list(dict.fromkeys(normalized))


def _task_id(task_card: dict[str, Any]) -> str:
    supplied = task_card.get("task_id") or "task_debate_loop"
    return _prefixed("task", supplied, default="task")


def build_fixed_three_model_route(task_card: dict[str, Any]) -> dict[str, Any]:
    """Build the D2-01 fixed Claude/Codex/Gemini ModelRoute."""

    task_id = _task_id(task_card)
    base = task_id.removeprefix("task_")
    route_record = {
        "route_id": _prefixed("route", f"{base}_debate_loop", default="route"),
        "task_id": task_id,
        "route_type": "multi_review",
        "trigger": "task_card",
        "risk_level": "high",
        "required_capabilities": ["planning", "adversary", "source_audit", "convergence"],
        "selected_models": [
            {
                "model_ref": "model_claude_opus_4_7",
                "role": "producer",
                "invocation": "manual",
                "reason": "Claude produces the initial synthesis and later convergence framing for the fixed D2-01 debate trio.",
            },
            {
                "model_ref": "model_codex_gpt_5_5",
                "role": "adversary",
                "invocation": "codex_cli",
                "reason": "Codex acts as the aggressive adversary for boundary, security, and technical objections.",
            },
            {
                "model_ref": "model_gemini_3_1_pro",
                "role": "source_auditor",
                "invocation": "manual",
                "reason": "Gemini acts as source auditor / external-view reviewer for OMC and project-definition evidence.",
            },
        ],
        "rejected_models": [],
        "run_refs": [_prefixed("run", f"{base}_debate_loop", default="run")],
        "artifact_refs": [],
        "source_refs": _source_refs(task_card),
        "status": "selected",
        "rationale": (
            "SDD-D2-01 decision A1 fixes the manual debate participants to Claude producer/convergence, "
            "Codex adversary, and Gemini source auditor; no majority-vote acceptance is allowed."
        ),
    }
    validate_route_record(route_record, "d2_01_fixed_route.json")
    return route_record


def _load_mock_rounds() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    fixture = load_json(OMC_MOCK_FIXTURE)
    if not isinstance(fixture, dict):
        raise DebateLoopError("OMC mock fixture must be an object")
    rounds = fixture.get("rounds")
    provider_artifacts = fixture.get("provider_artifacts", [])
    if not isinstance(rounds, list) or not rounds:
        raise DebateLoopError("OMC mock fixture must contain rounds[]")
    if not isinstance(provider_artifacts, list):
        raise DebateLoopError("OMC mock fixture provider_artifacts must be a list")
    scan_forbidden_material(fixture, "omc_debate_loop_mock")
    return copy.deepcopy(rounds), copy.deepcopy(provider_artifacts)


def _load_manual_rounds(paths: list[str | Path]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rounds: list[dict[str, Any]] = []
    provider_artifacts: list[dict[str, Any]] = []
    for path_text in paths:
        path = Path(path_text)
        payload = load_json(path)
        scan_forbidden_material(payload, f"manual_provider_artifact:{path.name}")
        if not isinstance(payload, dict):
            raise DebateLoopError(f"manual provider artifact must be an object: {path}")
        if isinstance(payload.get("rounds"), list):
            rounds.extend(payload["rounds"])
        elif isinstance(payload.get("round"), dict):
            rounds.append(payload["round"])
        else:
            raise DebateLoopError(f"manual provider artifact missing round(s): {path}")
        provider_artifacts.append(
            {
                "artifact_ref": payload.get("artifact_ref") or payload.get("round", {}).get("artifact_ref"),
                "provider": payload.get("provider", "manual"),
                "model_ref": payload.get("model_ref", "model_manual_provider"),
                "role": payload.get("role", "manual"),
                "summary": payload.get("summary", f"Manual provider artifact {path.name}"),
                "source_refs": payload.get("source_refs", []),
            }
        )
    return rounds, provider_artifacts


def _contains_external_side_effect(text: str) -> bool:
    action_terms = ("publish", "external send", "send externally", "delete", "payment", "pay ", "account change", "change account")
    return any(re.search(rf"\b{re.escape(term.strip())}\b", text, re.IGNORECASE) for term in action_terms)


def _inject_external_action_blocks(rounds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    guarded = copy.deepcopy(rounds)
    for index, round_record in enumerate(guarded):
        text = " ".join(str(round_record.get(field, "")) for field in ("summary", "recommendation", "content"))
        if not _contains_external_side_effect(text):
            continue
        objections = round_record.setdefault("objections", [])
        objections.append(
            {
                "objection_id": _prefixed("obj", f"external_side_effect_{index}", default="external_side_effect"),
                "severity": "critical",
                "status": "needs_user_decision",
                "summary": "External publishing/sending/deleting/payment/account-change suggestion requires explicit user authorization.",
                "evidence_refs": [round_record.get("artifact_ref") or _prefixed("artifact", f"external_side_effect_{index}")],
            }
        )
    return guarded


def _unresolved_high_or_critical(rounds: list[dict[str, Any]]) -> set[str]:
    unresolved: set[str] = set()
    for round_record in rounds:
        for objection in round_record.get("objections", []) or []:
            oid = objection.get("objection_id")
            if not oid:
                continue
            if objection.get("addresses_objection_ref") and objection.get("status") in {"accepted", "rejected"}:
                unresolved.discard(str(objection["addresses_objection_ref"]))
            if objection.get("severity") in {"critical", "high"} and objection.get("status") in {"raised", "unresolved", "needs_user_decision"}:
                unresolved.add(str(oid))
    return unresolved


def _select_rounds_with_policy(rounds: list[dict[str, Any]], *, max_rounds: int = DEFAULT_MAX_ROUNDS, min_rounds: int = DEFAULT_MIN_ROUNDS) -> tuple[list[dict[str, Any]], str]:
    if max_rounds > DEFAULT_MAX_ROUNDS:
        raise DebateLoopError("D2-01 max round cap is 5")
    if max_rounds < 1:
        raise DebateLoopError("max_rounds must be positive")
    selected: list[dict[str, Any]] = []
    stopped_reason = "input_exhausted"
    for raw in rounds[:max_rounds]:
        selected.append(raw)
        if len(selected) >= min_rounds and not _unresolved_high_or_critical(selected):
            stopped_reason = "early_no_unresolved_high_critical"
            break
    if len(rounds) > max_rounds and len(selected) == max_rounds:
        stopped_reason = "round_cap_5"
    elif _unresolved_high_or_critical(selected) and len(selected) == len(rounds[:max_rounds]):
        stopped_reason = "input_exhausted_with_unresolved_blockers"
    return selected, stopped_reason


def _write_json_artifact(path: Path, payload: Any) -> Path:
    scan_forbidden_material(payload, path.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_provider_artifacts(artifact_root: Path, provider_artifacts: list[dict[str, Any]]) -> dict[str, str]:
    refs_to_paths: dict[str, str] = {}
    for artifact in provider_artifacts:
        ref = artifact.get("artifact_ref")
        if not isinstance(ref, str) or not ref.startswith("artifact_"):
            continue
        safe_payload = {
            "artifact_ref": ref,
            "provider": artifact.get("provider", "mock"),
            "model_ref": artifact.get("model_ref"),
            "role": artifact.get("role"),
            "summary": artifact.get("summary", "Mock provider artifact."),
            "source_refs": artifact.get("source_refs", []),
        }
        path = artifact_root / f"{ref}.json"
        _write_json_artifact(path, safe_payload)
        refs_to_paths[ref] = str(path)
    return refs_to_paths


def _candidate_summary(task_card: dict[str, Any], convergence: dict[str, Any]) -> str:
    task_id = task_card.get("task_id", "task_debate_loop")
    if str(task_id) == "task_omc_ingest":
        return (
            "OMC ingestion debate produced a program-memory candidate for the manual §10.4 debate-loop slice; "
            "it does not claim the full §10.1 OMC demo is complete. "
            f"Convergence decision: {convergence['decision_status']}."
        )
    return f"Manual multimodel debate loop candidate for {task_id}; convergence decision: {convergence['decision_status']}."


def run_debate_loop(
    task_card: str | Path | dict[str, Any],
    *,
    state_root: str | Path,
    artifact_root: str | Path,
    mock_invocations: bool = True,
    manual_invocation_artifacts: list[str | Path] | None = None,
    provider_mode: bool = False,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
    min_rounds: int = DEFAULT_MIN_ROUNDS,
) -> dict[str, Any]:
    """Run the manual D2-01 route → debate → convergence → candidate loop."""

    task = _load_task_card(task_card)
    scan_forbidden_material(task, "task_card")
    _ensure_manual_task_trigger(task)
    state_root_path = assert_safe_output_root(state_root)
    artifact_root_path = assert_safe_output_root(artifact_root)
    artifact_root_path.mkdir(parents=True, exist_ok=True)

    route_record = build_fixed_three_model_route(task)
    invocation_plan = build_invocation_plan(task, artifact_root=artifact_root_path, provider_mode=provider_mode)

    provider_artifacts: list[dict[str, Any]]
    if provider_mode:
        execute_invocation_plan(invocation_plan, provider_mode=True)
        try:
            rounds_input, provider_artifacts = build_real_rounds(invocation_plan, task)
        except ProviderRoundParseError as exc:
            raise DebateLoopError(f"provider_mode round parse failed: {exc}") from exc
    elif manual_invocation_artifacts:
        rounds_input, provider_artifacts = _load_manual_rounds(manual_invocation_artifacts)
    elif mock_invocations:
        rounds_input, provider_artifacts = _load_mock_rounds()
    else:
        raise DebateLoopError("provider mode is disabled; use mock_invocations or manual_invocation_artifacts")

    rounds_input = _inject_external_action_blocks(rounds_input)
    selected_rounds, stopped_reason = _select_rounds_with_policy(rounds_input, max_rounds=max_rounds, min_rounds=min_rounds)
    provider_artifact_paths = _write_provider_artifacts(artifact_root_path, provider_artifacts)

    debate_record = run_debate(route_record, selected_rounds)
    validate_debate_record(debate_record, route_record, "d2_01_debate.json")
    convergence_record = converge(debate_record)

    model_refs = [item["model_ref"] for item in route_record["selected_models"]]
    debate_artifact_refs = [round_record["artifact_ref"] for round_record in debate_record["rounds"]]
    structured_artifact_refs = [
        _prefixed("artifact", route_record["route_id"], default="route"),
        _prefixed("artifact", debate_record["debate_id"], default="debate"),
        _prefixed("artifact", convergence_record["convergence_id"], default="convergence"),
        _prefixed("artifact", f"{convergence_record['convergence_id']}_markdown", default="convergence_markdown"),
    ]
    candidate_record = build_debate_candidate(
        task_id=route_record["task_id"],
        route_id=route_record["route_id"],
        debate_id=debate_record["debate_id"],
        convergence_id=convergence_record["convergence_id"],
        summary=_candidate_summary(task, convergence_record),
        source_refs=route_record["source_refs"],
        artifact_refs=structured_artifact_refs + debate_artifact_refs,
        model_refs=model_refs,
        decision_status=convergence_record["decision_status"],
    )
    convergence_record["memory_candidates"] = [
        {
            "candidate_id": candidate_record["candidate_id"],
            "summary": candidate_record["summary"],
            "source_refs": candidate_record["source_refs"],
        }
    ]
    validate_convergence_record(convergence_record, debate_record, "d2_01_convergence.json")

    route_path = _write_json_artifact(artifact_root_path / f"{route_record['route_id']}.json", route_record)
    debate_path = _write_json_artifact(artifact_root_path / f"{debate_record['debate_id']}.json", debate_record)
    convergence_path = _write_json_artifact(artifact_root_path / f"{convergence_record['convergence_id']}.json", convergence_record)
    candidate_jsonl_path = append_candidate_record(state_root_path, candidate_record)
    markdown_path = write_convergence_markdown(
        artifact_root_path / f"{convergence_record['convergence_id']}.md",
        route=route_record,
        debate=debate_record,
        convergence=convergence_record,
        candidates=[candidate_record],
    )

    artifact_refs = list(dict.fromkeys(candidate_record["artifact_refs"]))
    run_id = route_record["run_refs"][0]
    ledger_path, ledger_records = record_debate_loop_ledger(
        state_root_path,
        run_id=run_id,
        task_id=route_record["task_id"],
        route_id=route_record["route_id"],
        debate_id=debate_record["debate_id"],
        convergence_id=convergence_record["convergence_id"],
        candidate_ids=[candidate_record["candidate_id"]],
        model_refs=model_refs,
        source_refs=route_record["source_refs"],
        artifact_refs=artifact_refs,
        provider_mode="provider" if provider_mode else "manual" if manual_invocation_artifacts else "mock",
        decision_status=convergence_record["decision_status"],
        blocked_decision_count=sum(1 for item in convergence_record["user_decision_requirements"] if item.get("blocking")),
    )

    artifact_paths = {
        "route": str(route_path),
        "debate": str(debate_path),
        "convergence": str(convergence_path),
        "candidate_jsonl": str(candidate_jsonl_path),
        "convergence_markdown": str(markdown_path),
        "ledger_jsonl": str(ledger_path),
        "provider_artifacts": provider_artifact_paths,
    }
    return {
        "status": "completed",
        "sdd_id": SDD_ID,
        "provider_mode": "provider" if provider_mode else "manual" if manual_invocation_artifacts else "mock",
        "task_id": route_record["task_id"],
        "route_id": route_record["route_id"],
        "debate_id": debate_record["debate_id"],
        "convergence_id": convergence_record["convergence_id"],
        "candidate_ids": [candidate_record["candidate_id"]],
        "decision_status": convergence_record["decision_status"],
        "blocked_decision_count": sum(1 for item in convergence_record["user_decision_requirements"] if item.get("blocking")),
        "round_count": len(debate_record["rounds"]),
        "stopped_reason": stopped_reason,
        "upgrade_rule": UPGRADE_RULE,
        "artifact_paths": artifact_paths,
        "ledger_event_types": [record["event_type"] for record in ledger_records],
        "route": route_record,
        "debate": debate_record,
        "convergence": convergence_record,
        "candidate": candidate_record,
        "invocation_plan": invocation_plan,
    }

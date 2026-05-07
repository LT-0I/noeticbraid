"""Rule-table router for SP-B ModelRoute records.

The router is intentionally deterministic and file-local: it decides an
alliance shape but does not invoke models. SP-C2 can later read
``selected_models[].invocation`` and perform the actual calls.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable

from .constants import CAPABILITIES, DEFAULT_AVAILABLE_MODELS, INVOCATIONS, MODEL_ROLES, RISK_LEVELS, TRIGGERS
from .validator import ValidationError, validate_route_record

_BRANCH_CAPABILITIES = {"coding", "code_review", "security_review", "verification", "convergence"}
_HIGH_CAPABILITIES = {"security_review", "adversary"}
_MEDIUM_CAPABILITIES = {"coding", "code_review", "source_audit", "verification", "convergence"}

_ROLE_CAPABILITY_HINTS = {
    "planner": ("planning",),
    "producer": ("planning", "writing", "research", "coding"),
    "writer": ("writing",),
    "coder": ("coding", "file_io"),
    "reviewer": ("code_review",),
    "adversary": ("adversary", "security_review"),
    "source_auditor": ("source_audit",),
    "verifier": ("verification",),
    "convergence_editor": ("convergence",),
    "human_decision": ("convergence",),
    "orchestrator": ("planning", "convergence"),
}


class RoutingError(ValueError):
    """Raised when a task card cannot be converted to a valid route."""


def _stable_hash(*parts: object, length: int = 12) -> str:
    payload = "|".join(str(part) for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:length]


def _slug(value: object, default: str = "item", max_length: int = 72) -> str:
    raw = str(value or "").strip()
    slug = re.sub(r"[^A-Za-z0-9_]+", "_", raw).strip("_")
    if not slug:
        slug = f"{default}_{_stable_hash(raw)}"
    if len(slug) > max_length:
        slug = f"{slug[: max_length - 13].rstrip('_')}_{_stable_hash(slug)}"
    return slug


def _make_prefixed(prefix: str, value: object, default: str = "item", max_length: int = 128) -> str:
    slug = _slug(value, default=default, max_length=max_length - len(prefix) - 1)
    if slug.startswith(prefix + "_"):
        candidate = slug
    else:
        candidate = f"{prefix}_{slug}"
    if len(candidate) > max_length:
        candidate = f"{candidate[: max_length - 13].rstrip('_')}_{_stable_hash(candidate)}"
    return candidate


def _task_id(task_card: dict[str, Any]) -> str:
    supplied = task_card.get("task_id")
    if supplied:
        return _make_prefixed("task", supplied, "task")
    seed = task_card.get("description") or task_card.get("task_type") or repr(task_card)
    return f"task_generated_{_stable_hash(seed)}"


def _normalize_capabilities(task_card: dict[str, Any]) -> list[str]:
    raw = task_card.get("required_capabilities") or task_card.get("capabilities")
    if raw is None:
        task_type = str(task_card.get("task_type") or "planning").lower()
        raw = [
            {
                "writing": "writing",
                "research": "research",
                "coding": "coding",
                "review": "code_review",
                "code_review": "code_review",
                "security": "security_review",
            }.get(task_type, "planning")
        ]
    if not isinstance(raw, list) or not raw:
        raise RoutingError("task_card.required_capabilities must be a non-empty list")
    capabilities: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            raise RoutingError("task_card.required_capabilities must contain strings")
        capability = item.strip().lower()
        if capability not in CAPABILITIES:
            raise RoutingError(f"unknown required capability: {item}")
        if capability not in capabilities:
            capabilities.append(capability)
    return capabilities


def _risk(task_card: dict[str, Any], capabilities: set[str]) -> str:
    if task_card.get("disputed") is True:
        return "disputed"
    risk = str(task_card.get("risk_hint") or task_card.get("risk_level") or "").strip().lower()
    if risk:
        if risk not in RISK_LEVELS:
            raise RoutingError(f"unknown risk_hint: {risk}")
        return risk
    if capabilities & _HIGH_CAPABILITIES:
        return "high"
    if capabilities & _MEDIUM_CAPABILITIES:
        return "medium"
    return "low"


def _trigger(task_card: dict[str, Any]) -> str:
    trigger = str(task_card.get("trigger") or "task_card").strip().lower()
    if trigger not in TRIGGERS:
        raise RoutingError(f"unknown trigger: {trigger}")
    return trigger


def _as_list(value: Any, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise RoutingError(f"available_models[].{field} must be a list when provided")
    result = []
    for item in value:
        if not isinstance(item, str):
            raise RoutingError(f"available_models[].{field} must contain strings")
        normalized = item.strip()
        if normalized not in result:
            result.append(normalized)
    return result


def _normalize_available_models(task_card: dict[str, Any]) -> list[dict[str, Any]]:
    raw_models = task_card.get("available_models")
    if raw_models is None:
        raw_models = list(DEFAULT_AVAILABLE_MODELS)
    if not isinstance(raw_models, list) or not raw_models:
        raise RoutingError("task_card.available_models must be a non-empty list")

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_models):
        if not isinstance(raw, dict):
            raise RoutingError(f"available_models[{index}] must be an object")
        model_ref = raw.get("model_ref")
        if not isinstance(model_ref, str) or not re.fullmatch(r"model_[A-Za-z0-9_]+", model_ref):
            raise RoutingError(f"available_models[{index}].model_ref must match model_*")
        if model_ref in seen:
            raise RoutingError(f"duplicate available model_ref: {model_ref}")
        seen.add(model_ref)

        role = raw.get("role")
        roles = _as_list(raw.get("roles"), "roles")
        if role is not None:
            if not isinstance(role, str):
                raise RoutingError(f"available_models[{index}].role must be a string")
            if role not in roles:
                roles.insert(0, role)
        if not roles:
            raise RoutingError(f"available_models[{index}] must define role or roles")
        for candidate_role in roles:
            if candidate_role not in MODEL_ROLES:
                raise RoutingError(f"available_models[{index}] unknown role: {candidate_role}")

        capabilities = _as_list(raw.get("capabilities"), "capabilities")
        if not capabilities:
            raise RoutingError(f"available_models[{index}].capabilities must be a non-empty list")
        for capability in capabilities:
            if capability not in CAPABILITIES:
                raise RoutingError(f"available_models[{index}] unknown capability: {capability}")

        invocation = raw.get("invocation") or "manual"
        if invocation not in INVOCATIONS:
            raise RoutingError(f"available_models[{index}] unknown invocation: {invocation}")

        normalized.append(
            {
                "model_ref": model_ref,
                "role": role or roles[0],
                "roles": roles,
                "capabilities": capabilities,
                "invocation": invocation,
            }
        )
    return normalized


def _score_model(model: dict[str, Any], role: str, used_refs: set[str], capability_hint: str | None) -> tuple[int, int, int, int, str]:
    roles = set(model["roles"])
    capabilities = set(model["capabilities"])
    role_score = 0 if role in roles else 1
    capability_score = 0 if capability_hint is None or capability_hint in capabilities else 1
    distinct_score = 0 if model["model_ref"] not in used_refs else 1
    exact_default_score = 0 if model["role"] == role else 1
    return (role_score, distinct_score, capability_score, exact_default_score, model["model_ref"])


def _choose_model(models: list[dict[str, Any]], role: str, used_refs: set[str], capability_hint: str | None = None) -> dict[str, Any]:
    candidates = [model for model in models if role in model["roles"]]
    if not candidates:
        hints = set(_ROLE_CAPABILITY_HINTS.get(role, ()))
        candidates = [model for model in models if hints & set(model["capabilities"])]
    if not candidates:
        available_roles = sorted({r for model in models for r in model["roles"]})
        available_capabilities = sorted({c for model in models for c in model["capabilities"]})
        raise RoutingError(
            f"no model satisfies role={role!r} or capability_hint={capability_hint!r}; "
            f"available roles={available_roles}, available capabilities={available_capabilities}"
        )
    return sorted(candidates, key=lambda model: _score_model(model, role, used_refs, capability_hint))[0]


def _candidate_refs(models: list[dict[str, Any]], role: str) -> set[str]:
    candidates = [model for model in models if role in model["roles"]]
    if not candidates:
        hints = set(_ROLE_CAPABILITY_HINTS.get(role, ()))
        candidates = [model for model in models if hints & set(model["capabilities"])]
    return {model["model_ref"] for model in candidates}


def _require_distinct_assignment(models: list[dict[str, Any]], route_type: str, roles: tuple[str, ...]) -> None:
    candidate_refs = [_candidate_refs(models, role) for role in roles]
    for role, refs in zip(roles, candidate_refs):
        if not refs:
            _choose_model(models, role, set())

    ordered = sorted(zip(roles, candidate_refs), key=lambda item: len(item[1]))

    def can_assign(index: int, used_refs: set[str]) -> bool:
        if index == len(ordered):
            return True
        _, refs = ordered[index]
        return any(can_assign(index + 1, used_refs | {ref}) for ref in refs if ref not in used_refs)

    if not can_assign(0, set()):
        candidates = {role: sorted(refs) for role, refs in zip(roles, candidate_refs)}
        raise RoutingError(f"{route_type} requires distinct model_ref assignment for roles {roles}; candidates={candidates}")


def _select(role: str, model: dict[str, Any], reason: str) -> dict[str, str]:
    return {
        "model_ref": model["model_ref"],
        "role": role,
        "invocation": model["invocation"],
        "reason": reason,
    }


def _append_unique(selected: list[dict[str, str]], item: dict[str, str]) -> None:
    key = (item["model_ref"], item["role"])
    if key not in {(entry["model_ref"], entry["role"]) for entry in selected}:
        selected.append(item)


def _require_distinct(selected: list[dict[str, str]], roles: tuple[str, ...], route_type: str) -> None:
    refs = [item["model_ref"] for item in selected if item["role"] in roles]
    if len(set(refs)) < len(refs):
        raise RoutingError(f"{route_type} requires distinct model_ref for roles {roles}; got {refs}")


def _build_selection(route_type: str, models: list[dict[str, Any]], capabilities: set[str]) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    used_refs: set[str] = set()
    producer_role = "coder" if "coding" in capabilities else "producer"
    if route_type == "producer_reviewer":
        _require_distinct_assignment(models, route_type, (producer_role, "reviewer"))
    elif route_type == "dual_review":
        _require_distinct_assignment(models, route_type, ("reviewer", "reviewer"))
    elif route_type == "multi_review":
        _require_distinct_assignment(models, route_type, ("reviewer", "adversary"))
    elif route_type == "manual_convergence":
        _require_distinct_assignment(models, route_type, ("reviewer", "adversary"))

    def add(role: str, reason: str, capability_hint: str | None = None) -> None:
        model = _choose_model(models, role, used_refs, capability_hint)
        _append_unique(selected, _select(role, model, reason))
        used_refs.add(model["model_ref"])

    if route_type == "single_model":
        preferred_role = "writer" if "writing" in capabilities else "researcher" if "research" in capabilities else "planner"
        if "coding" in capabilities:
            preferred_role = "coder"
        add(preferred_role, "Single-model route selected because risk is low and one capable model is sufficient.")
    elif route_type == "producer_reviewer":
        add(producer_role, "Produces the initial artifact for a low-risk task that still needs review.", "coding" if producer_role == "coder" else None)
        add("reviewer", "Reviews the produced artifact before convergence.", "code_review")
    elif route_type == "dual_review":
        add("producer", "Produces the first artifact for independent dual review.")
        add("reviewer", "First independent reviewer checks correctness and scope.", "code_review")
        add("reviewer", "Second independent reviewer checks source and process risks.", "source_audit")
        add("convergence_editor", "Merges reviewer findings without majority-vote shortcuts.", "convergence")
    elif route_type == "multi_review":
        add("coder" if "coding" in capabilities else "producer", "Produces the bounded implementation or plan for high-risk review.", "coding" if "coding" in capabilities else None)
        add("reviewer", "Checks contract and functional correctness.", "code_review")
        add("adversary", "Searches for boundary, security, and failure-mode risks.", "security_review" if "security_review" in capabilities else "adversary")
        add("verifier", "Provides an evidence gate before acceptance is claimed.", "verification")
        add("convergence_editor", "Records accepted, rejected, and carried objections.", "convergence")
    elif route_type == "manual_convergence":
        add("reviewer", "Represents the accepting or baseline review position.", "code_review")
        add("adversary", "Carries the blocking disagreement or minority opinion.", "adversary")
        add("convergence_editor", "Frames unresolved conflict for explicit decision.", "convergence")
        add("human_decision", "Final authority for disputed scope or risk acceptance.", "convergence")
    else:  # pragma: no cover - guarded by caller
        raise RoutingError(f"unknown route_type: {route_type}")

    if route_type == "producer_reviewer":
        _require_distinct(selected, (producer_role, "reviewer"), route_type)
    elif route_type == "dual_review":
        _require_distinct(selected, ("reviewer",), route_type)
    elif route_type == "multi_review":
        _require_distinct(selected, ("reviewer", "adversary"), route_type)

    return selected


def _route_type(risk: str, capabilities: set[str], model_count: int) -> str:
    if risk == "disputed":
        return "manual_convergence"
    if risk == "high":
        return "multi_review"
    if risk == "medium":
        return "dual_review"
    if capabilities & _BRANCH_CAPABILITIES or model_count >= 2:
        return "producer_reviewer"
    return "single_model"


def _refs(values: Any, field: str) -> list[str]:
    if values is None:
        return []
    if not isinstance(values, list):
        raise RoutingError(f"task_card.{field} must be a list")
    result: list[str] = []
    for value in values:
        if not isinstance(value, str):
            raise RoutingError(f"task_card.{field} must contain strings")
        if value not in result:
            result.append(value)
    return result


def _rejected_models(models: Iterable[dict[str, Any]], selected: list[dict[str, str]]) -> list[dict[str, str]]:
    selected_refs = {item["model_ref"] for item in selected}
    rejected = []
    for model in models:
        if model["model_ref"] not in selected_refs:
            rejected.append({"model_ref": model["model_ref"], "reason": "Not required by the selected route_type rule."})
    return rejected[:32]


def route(task_card: dict[str, Any]) -> dict[str, Any]:
    """Return a validated ModelRoute record for ``task_card``.

    Expected ``available_models`` shape is a list of objects with
    ``model_ref``, ``role`` or ``roles``, ``capabilities``, and ``invocation``.
    When omitted, a local deterministic default model pool is used.
    """
    if not isinstance(task_card, dict):
        raise RoutingError("task_card must be an object")

    capabilities = _normalize_capabilities(task_card)
    capability_set = set(capabilities)
    models = _normalize_available_models(task_card)
    risk = _risk(task_card, capability_set)
    trigger = _trigger(task_card)
    route_type = _route_type(risk, capability_set, len(models))
    task_id = _task_id(task_card)
    selected = _build_selection(route_type, models, capability_set)

    route_id_seed = f"{task_id}_{route_type}_{risk}"
    record: dict[str, Any] = {
        "route_id": _make_prefixed("route", route_id_seed.removeprefix("task_"), "route"),
        "task_id": task_id,
        "route_type": route_type,
        "trigger": trigger,
        "risk_level": risk,
        "required_capabilities": capabilities,
        "selected_models": selected,
        "rejected_models": _rejected_models(models, selected),
        "run_refs": _refs(task_card.get("run_refs"), "run_refs") or [_make_prefixed("run", f"{task_id}_route", "route")],
        "artifact_refs": _refs(task_card.get("artifact_refs"), "artifact_refs"),
        "source_refs": _refs(task_card.get("source_refs") or task_card.get("sp_h_source_refs"), "source_refs"),
        "status": "selected",
        "rationale": (
            f"Selected {route_type} for risk={risk}; required capabilities="
            f"{', '.join(capabilities)}. Low-risk branching uses producer_reviewer "
            "when coding/review/evidence capabilities or multiple available models are present."
        ),
    }
    if task_card.get("workflow_id") is not None:
        record["workflow_id"] = task_card["workflow_id"]

    try:
        validate_route_record(record, "generated_route.json")
    except ValidationError as exc:
        raise RoutingError(str(exc)) from exc
    return record

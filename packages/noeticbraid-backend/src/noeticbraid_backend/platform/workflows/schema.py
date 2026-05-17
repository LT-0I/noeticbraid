# SPDX-License-Identifier: Apache-2.0
"""Workflow specification schema for the Phase-2 library."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_REQUIRED_WORKFLOW_KEYS = frozenset(
    {
        "id",
        "version",
        "description",
        "selector",
        "inputs",
        "isolation",
        "nodes",
        "edges",
        "termination",
        "capability_honesty",
    }
)
_SELECTOR_KEYS = frozenset(
    {
        "intent_tags",
        "deliverable_types",
        "required_capabilities",
        "excluded_capabilities",
        "requirement_predicates",
    }
)


@dataclass(frozen=True, slots=True)
class WorkflowSelector:
    intent_tags: tuple[str, ...]
    deliverable_types: tuple[str, ...]
    required_capabilities: tuple[str, ...]
    excluded_capabilities: tuple[str, ...]
    requirement_predicates: tuple[str, ...]

    @classmethod
    def from_json_dict(cls, payload: Any) -> "WorkflowSelector":
        if not isinstance(payload, dict):
            raise ValueError("selector must be an object")
        missing = _SELECTOR_KEYS - set(payload)
        if missing:
            raise ValueError(f"selector missing keys: {sorted(missing)}")
        return cls(
            intent_tags=_string_tuple(payload["intent_tags"], field="selector.intent_tags"),
            deliverable_types=_string_tuple(payload["deliverable_types"], field="selector.deliverable_types"),
            required_capabilities=_string_tuple(payload["required_capabilities"], field="selector.required_capabilities"),
            excluded_capabilities=_string_tuple(payload["excluded_capabilities"], field="selector.excluded_capabilities"),
            requirement_predicates=_string_tuple(
                payload["requirement_predicates"], field="selector.requirement_predicates"
            ),
        )

    def to_json_dict(self) -> dict[str, list[str]]:
        return {
            "intent_tags": list(self.intent_tags),
            "deliverable_types": list(self.deliverable_types),
            "required_capabilities": list(self.required_capabilities),
            "excluded_capabilities": list(self.excluded_capabilities),
            "requirement_predicates": list(self.requirement_predicates),
        }


@dataclass(frozen=True, slots=True)
class WorkflowSpec:
    id: str
    version: str
    description: str
    selector: WorkflowSelector
    inputs: tuple[dict[str, Any], ...]
    isolation: dict[str, Any]
    nodes: tuple[dict[str, Any], ...]
    edges: tuple[dict[str, Any], ...]
    termination: dict[str, Any]
    capability_honesty: dict[str, Any]

    @classmethod
    def from_json_dict(cls, payload: Any) -> "WorkflowSpec":
        if not isinstance(payload, dict):
            raise ValueError("workflow file must be an object")
        workflow = payload.get("workflow")
        if not isinstance(workflow, dict):
            raise ValueError("workflow key must be an object")
        missing = _REQUIRED_WORKFLOW_KEYS - set(workflow)
        if missing:
            raise ValueError(f"workflow missing keys: {sorted(missing)}")
        workflow_id = _non_empty_string(workflow["id"], field="workflow.id")
        version = _non_empty_string(workflow["version"], field="workflow.version")
        description = _non_empty_string(workflow["description"], field="workflow.description")
        if len(description) > 1024:
            raise ValueError("workflow.description must be <= 1024 chars")
        selector = WorkflowSelector.from_json_dict(workflow["selector"])
        inputs = _dict_tuple(workflow["inputs"], field="workflow.inputs")
        isolation = _dict_obj(workflow["isolation"], field="workflow.isolation")
        nodes = _dict_tuple(workflow["nodes"], field="workflow.nodes")
        edges = _dict_tuple(workflow["edges"], field="workflow.edges")
        termination = _dict_obj(workflow["termination"], field="workflow.termination")
        capability_honesty = _dict_obj(workflow["capability_honesty"], field="workflow.capability_honesty")
        if not nodes:
            raise ValueError("workflow.nodes must not be empty")
        return cls(
            id=workflow_id,
            version=version,
            description=description,
            selector=selector,
            inputs=inputs,
            isolation=isolation,
            nodes=nodes,
            edges=edges,
            termination=termination,
            capability_honesty=capability_honesty,
        )

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "workflow": {
                "id": self.id,
                "version": self.version,
                "description": self.description,
                "selector": self.selector.to_json_dict(),
                "inputs": list(self.inputs),
                "isolation": dict(self.isolation),
                "nodes": list(self.nodes),
                "edges": list(self.edges),
                "termination": dict(self.termination),
                "capability_honesty": dict(self.capability_honesty),
            }
        }


def _non_empty_string(value: Any, *, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} must be a non-empty string")
    return text


def _string_tuple(value: Any, *, field: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    result: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if not text:
            raise ValueError(f"{field} entries must be non-empty strings")
        result.append(text)
    return tuple(result)


def _dict_tuple(value: Any, *, field: str) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    result: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError(f"{field} entries must be objects")
        result.append(dict(item))
    return tuple(result)


def _dict_obj(value: Any, *, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    return dict(value)


__all__ = ["WorkflowSelector", "WorkflowSpec"]

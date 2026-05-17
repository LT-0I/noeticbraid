# SPDX-License-Identifier: Apache-2.0
"""Node implementations for Phase-2 local execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from noeticbraid_backend.platform.elicitation.capabilities import capability_for
from noeticbraid_backend.platform.elicitation.local_ai import DEFAULT_TIMEOUT_SECONDS, run_local_task

NodeStatus = Literal["succeeded", "failed", "deferred"]


@dataclass(frozen=True, slots=True)
class NodeOutcome:
    status: NodeStatus
    reason: str | None = None
    artifact: dict[str, Any] | None = None
    evidence_node_ids: list[str] = field(default_factory=list)


class LocalExecutionNode:
    def execute(self, spec_node: dict[str, Any], inputs: dict[str, Any], *, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> NodeOutcome:
        result = run_local_task(
            {
                "kind": "fanout",
                "node": spec_node,
                "inputs": inputs,
            },
            timeout=timeout,
        )
        if result.get("ok") is not True:
            return NodeOutcome(status="failed", reason=str(result.get("error") or "local model unavailable"))
        artifact = result.get("artifact") if isinstance(result.get("artifact"), dict) else None
        if artifact is None:
            artifact = {"text": str(result.get("text") or result.get("content") or "").strip()}
        if not any(str(value or "").strip() for value in artifact.values()):
            return NodeOutcome(status="failed", reason="local model produced no artifact")
        return NodeOutcome(status="succeeded", artifact=artifact)


class HubExecutionNode:
    def execute(self, spec_node: dict[str, Any], inputs: dict[str, Any]) -> NodeOutcome:
        del spec_node, inputs
        capability = capability_for("web_ai")
        return NodeOutcome(status="deferred", reason=capability.blocked_reason, evidence_node_ids=[])


__all__ = ["HubExecutionNode", "LocalExecutionNode", "NodeOutcome", "NodeStatus"]

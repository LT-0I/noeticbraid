# SPDX-License-Identifier: Apache-2.0
"""Node implementations for Phase-2 local execution."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from noeticbraid_backend.omc_workspace import web_ai_hub_compat as compat
from noeticbraid_backend.omc_workspace.web_ai_hub_client import (
    CHATGPT_PROFILE,
    check_chatgpt_consumer_health,
    sanitize_error_msg,
)
from noeticbraid_backend.platform.elicitation.capabilities import capability_for
from noeticbraid_backend.platform.elicitation.local_ai import DEFAULT_TIMEOUT_SECONDS, run_local_task
from noeticbraid_backend.platform.orchestration import hub_adapter

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
        from noeticbraid_backend.platform.orchestrate.web_modality_routes import resolve_web_modality

        capability = capability_for("web_ai")
        if (os.environ.get("NOETICBRAID_PLATFORM_HUB_EXEC") or "").strip().lower() not in {"1", "true", "yes", "on"}:
            return NodeOutcome(status="deferred", reason=capability.blocked_reason, evidence_node_ids=[])

        hub_path_raw = os.environ.get(compat.HUB_PATH_ENV)
        if not hub_path_raw or not os.path.isabs(hub_path_raw) or not os.path.isdir(hub_path_raw):
            return NodeOutcome(status="deferred", reason=capability.blocked_reason, evidence_node_ids=[])
        if not compat.read_automation_enabled(os.environ):
            return NodeOutcome(status="deferred", reason=capability.blocked_reason, evidence_node_ids=[])
        hub_path = Path(hub_path_raw)
        digest_status, _digest_detail = compat.digest_matches(hub_path)
        if digest_status != "ok":
            return NodeOutcome(
                status="deferred",
                reason=sanitize_error_msg("web execution is not available", max_chars=256),
                evidence_node_ids=[],
            )

        health = check_chatgpt_consumer_health(hub_path)
        if health.get("ok") is not True:
            reason = sanitize_error_msg(
                str(health.get("message") or health.get("errorCode") or health.get("status") or "web execution unavailable"),
                max_chars=256,
            )
            return NodeOutcome(status="deferred", reason=reason or "web execution unavailable", evidence_node_ids=[])

        requirement = inputs.get("requirement") if isinstance(inputs.get("requirement"), dict) else {}
        route = resolve_web_modality(str(requirement.get("modality") or "text"))
        if route.kind == "blocked":
            return NodeOutcome(status="deferred", reason=route.reason, evidence_node_ids=[])
        prompt = (
            f"{route.prompt_preamble}\n\n"
            "Confirmed requirement:\n"
            f"{str(requirement.get('text') or '').strip()}\n\n"
            "Workflow node:\n"
            f"{json.dumps(dict(spec_node), ensure_ascii=False, sort_keys=True, default=str)}"
        )[: compat.PROMPT_MAX_CHARS]
        if route.param_kind == "textual":
            params = {
                "profile": CHATGPT_PROFILE if route.generator_profile == "chatgpt" else route.generator_profile,
                "prompt": prompt,
                "reuse_conversation": False,
            }
        else:
            params = {"profile": route.generator_profile, "prompt": prompt}
        try:
            result = hub_adapter.dispatch(
                route.generator_op,
                params,
                account=str(inputs["account"]),
                task_id=str(inputs["task_id"]),
            )
        except Exception:
            return NodeOutcome(status="deferred", reason="web execution unavailable", evidence_node_ids=[])

        if result.get("outcome") == "ok":
            payload = result.get("payload") if isinstance(result.get("payload"), dict) else {}
            response_text = str(payload.get("response_text") or "").strip()
            path_ref = str(payload.get("path") or "").strip()
            if route.reviewer_input_kind == "file":
                if not path_ref:
                    return NodeOutcome(status="deferred", reason="web execution produced no artifact", evidence_node_ids=[])
                artifact = {
                    "path": path_ref,
                    "text": response_text or path_ref,
                    "hub": True,
                }
            else:
                if not response_text:
                    return NodeOutcome(status="deferred", reason="web execution produced no artifact", evidence_node_ids=[])
                artifact = {"text": response_text, "hub": True}
            conversation_id = payload.get("conversation_id")
            if isinstance(conversation_id, str) and conversation_id:
                artifact["conversation_id"] = conversation_id
            return NodeOutcome(status="succeeded", artifact=artifact, evidence_node_ids=[])
        if result.get("outcome") == "blocked":
            reason = sanitize_error_msg(str(result.get("reason") or "web execution unavailable"), max_chars=256)
            return NodeOutcome(status="deferred", reason=reason or "web execution unavailable", evidence_node_ids=[])
        return NodeOutcome(status="deferred", reason="web execution unavailable", evidence_node_ids=[])


__all__ = ["HubExecutionNode", "LocalExecutionNode", "NodeOutcome", "NodeStatus"]

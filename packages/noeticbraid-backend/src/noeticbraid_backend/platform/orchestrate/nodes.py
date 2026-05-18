# SPDX-License-Identifier: Apache-2.0
"""Node implementations for Phase-2 local execution."""

from __future__ import annotations

import json
import os
import shutil
import stat
import time
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
        hop_start_ts = time.time()
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
        pre_existing_names: set[str] | None = None
        if route.reviewer_input_kind == "file":
            try:
                from noeticbraid_backend.platform.workspace_paths import resolve_user_path

                art_dir = Path(resolve_user_path(str(inputs["account"]), f"tasks/{str(inputs['task_id'])}/artifacts"))
                if art_dir.is_dir():
                    pre_existing_names = {
                        entry.name for entry in art_dir.iterdir() if entry.name.endswith("." + route.artifact_extension)
                    }
                else:
                    pre_existing_names = set()
            except Exception:
                pre_existing_names = None
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
            raw_reason = str(result.get("reason") or "web execution unavailable")
            if route.reviewer_input_kind == "file" and raw_reason == "artifact path governance violation":
                try:
                    import re

                    from noeticbraid_backend.platform.settings import PlatformSettings
                    from noeticbraid_backend.platform.workspace_paths import resolve_user_path

                    account = str(inputs["account"])
                    task_id = str(inputs["task_id"])
                    data_root = Path(os.path.realpath(PlatformSettings.from_env().data_root))
                    lexical = data_root / "users" / account / "tasks" / task_id / "artifacts"
                    component = data_root
                    for part in lexical.relative_to(data_root).parts:
                        component = component / part
                        mode = os.lstat(component).st_mode
                        if stat.S_ISLNK(mode):
                            raise RuntimeError("artifact path governance violation")
                    resolved_lexical = Path(os.path.realpath(lexical))
                    if resolved_lexical != Path(resolve_user_path(account, f"tasks/{task_id}/artifacts")):
                        raise RuntimeError("artifact path governance violation")
                    if os.path.realpath(lexical) != str(lexical):
                        raise RuntimeError("artifact path governance violation")
                    art_dir = lexical
                    art_real = str(lexical)
                    canonical_suffix = os.sep + os.path.join("tasks", task_id, "artifacts")
                    if (
                        pre_existing_names is not None
                        and art_dir.is_dir()
                        and not os.path.islink(art_dir)
                        and art_real.endswith(canonical_suffix)
                    ):
                        now = time.time()
                        matches = []
                        with os.scandir(art_dir) as entries:
                            for entry in entries:
                                if (
                                    not entry.is_file(follow_symlinks=False)
                                    or entry.is_symlink()
                                    or not entry.name.endswith("." + route.artifact_extension)
                                    or entry.name in pre_existing_names
                                ):
                                    continue
                                entry_real = os.path.realpath(entry.path)
                                if os.path.commonpath([art_real, entry_real]) != art_real:
                                    continue
                                mtime = entry.stat(follow_symlinks=False).st_mtime
                                if hop_start_ts <= mtime <= now:
                                    matches.append(Path(entry.path))
                        if len(matches) == 1:
                            # Same-account/task concurrent generations are serialized; if ever raced, >=2-new honest-defers.
                            src = matches[0]
                            src_fd = os.open(str(src), os.O_RDONLY | os.O_NOFOLLOW)
                            try:
                                src_st = os.fstat(src_fd)
                                if (
                                    not stat.S_ISREG(src_st.st_mode)
                                    or src_st.st_nlink != 1
                                    or not (hop_start_ts <= src_st.st_mtime <= now)
                                ):
                                    os.close(src_fd)
                                    src_fd = -1
                                else:
                                    ext = route.artifact_extension
                                    m = re.sub(r"[^A-Za-z0-9_-]", "", str(route.modality))[:32] or "art"
                                    rid = re.sub(r"[^A-Za-z0-9_-]", "", str((requirement or {}).get("id") or ""))[:48] or "req"
                                    epoch_ms = int(now * 1000)
                                    safe_name = f"web_{m}_{rid}_{epoch_ms}.{ext}"
                                    assert "," not in safe_name and " " not in safe_name and ":" not in safe_name
                                    dst = Path(resolve_user_path(account, f"tasks/{task_id}/artifacts/{safe_name}"))
                                    dst_fd = os.open(
                                        str(dst),
                                        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                        0o600,
                                    )
                                    try:
                                        with os.fdopen(src_fd, "rb") as sf, os.fdopen(dst_fd, "wb") as df:
                                            src_fd = -1
                                            dst_fd = -1
                                            shutil.copyfileobj(sf, df)
                                    finally:
                                        if dst_fd != -1:
                                            os.close(dst_fd)
                                    artifact = {
                                        "path": f"tasks/{task_id}/artifacts/{safe_name}",
                                        "text": f"tasks/{task_id}/artifacts/{safe_name}",
                                        "hub": True,
                                    }
                                    return NodeOutcome(status="succeeded", artifact=artifact, evidence_node_ids=[])
                            finally:
                                if src_fd != -1:
                                    os.close(src_fd)
                except Exception:
                    pass
            reason = sanitize_error_msg(raw_reason, max_chars=256)
            return NodeOutcome(status="deferred", reason=reason or "web execution unavailable", evidence_node_ids=[])
        return NodeOutcome(status="deferred", reason="web execution unavailable", evidence_node_ids=[])


__all__ = ["HubExecutionNode", "LocalExecutionNode", "NodeOutcome", "NodeStatus"]

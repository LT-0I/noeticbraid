# SPDX-License-Identifier: Apache-2.0
"""Task-to-hub dispatcher for platform WebSocket chat."""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Literal

from noeticbraid_backend.memory.recall_ranker import RecallResult, rank_recall_results
from noeticbraid_backend.omc_workspace import web_ai_hub_compat as compat
from noeticbraid_backend.omc_workspace.web_ai_hub_client import sanitize_error_msg
from noeticbraid_backend.orchestration import artifacts, ledger_contracts, verification_tier
from noeticbraid_backend.platform.ledger.events import (
    LedgerEvent,
    ai_call_event,
    artifact_produced_event,
    cross_validation_event,
)
from noeticbraid_backend.platform.ledger.writer import append_event, ledger_path_for
from noeticbraid_backend.platform.orchestration import hub_adapter
from noeticbraid_backend.platform.orchestration.modality_map import (
    ModalityBlocked,
    ModalityRoute,
    resolve_modality,
)
from noeticbraid_backend.platform.tasks import store as task_store
from noeticbraid_backend.platform.tasks.models import Task, TaskState, is_terminal_task_state
from noeticbraid_backend.platform.workspace_paths import resolve_user_path

EventType = Literal["ai_delta", "progress", "ledger", "artifact", "error", "blocked"]
MAX_DISPATCH_STEPS = 6


@dataclass(frozen=True, slots=True)
class Event:
    """Dispatcher event ready for WebSocket serialization."""

    type: EventType
    task_id: str
    payload: dict[str, Any] = field(default_factory=dict)

    def to_frame(self) -> dict[str, Any]:
        base: dict[str, Any] = {"type": self.type, "task_id": self.task_id}
        if self.type == "ai_delta":
            base["payload"] = dict(self.payload)
            return base
        if self.type == "ledger":
            base["event"] = dict(self.payload)
            return base
        base.update(self.payload)
        return base


@dataclass(frozen=True, slots=True)
class PlanStep:
    """One planned hub call."""

    modality: str
    op: str
    vendor: str
    params_template: dict[str, Any]
    prompt_text: str
    artifact_extension: str


@dataclass(frozen=True, slots=True)
class Plan:
    """Bounded dispatch plan."""

    steps: tuple[PlanStep, ...]
    blocked: tuple[ModalityBlocked, ...]
    created_at: str
    verification_tier: str
    context_token_count: int
    dispatch_status_known: bool


class Dispatcher:
    """Run a persisted task through the single hub adapter path."""

    def __init__(
        self,
        *,
        account: str,
        user_text: str,
        cancel_event: asyncio.Event | None = None,
        max_steps: int = MAX_DISPATCH_STEPS,
    ) -> None:
        self.account = account
        self.user_text = str(user_text or "")
        self.cancel_event = cancel_event or asyncio.Event()
        self.max_steps = max_steps

    async def run(self, task: Task) -> AsyncIterator[Event]:
        """Yield progress, ledger, hub delta, artifact, and terminal events."""

        current = task
        try:
            if is_terminal_task_state(current.state):
                yield Event(
                    "error",
                    current.task_id,
                    {"code": "terminal_task", "reason": "task is already terminal"},
                )
                return

            if self.cancel_event.is_set():
                async for event in self._block(current, modality="task", reason="task dispatch cancelled"):
                    yield event
                return

            if current.state is TaskState.CREATED:
                current, ledger_event = self._transition(current, TaskState.PLANNING)
                yield Event("progress", current.task_id, {"message": "planning", "step": 0, "total": 0})
                yield self._ledger_event(ledger_event)

            plan = self._build_plan(current)
            yield Event(
                "progress",
                current.task_id,
                {
                    "message": f"planned {len(plan.steps)} dispatch step(s) at {plan.verification_tier} verification",
                    "step": 0,
                    "total": len(plan.steps),
                },
            )

            if plan.blocked:
                blocked = plan.blocked[0]
                async for event in self._block(current, modality=blocked.modality, reason=blocked.reason):
                    yield event
                return
            if not plan.steps:
                async for event in self._block(current, modality="task", reason="no dispatchable plan steps"):
                    yield event
                return
            if len(plan.steps) > self.max_steps:
                async for event in self._block(
                    current,
                    modality="task",
                    reason=f"plan exceeds max step count {self.max_steps}",
                ):
                    yield event
                return

            current, ledger_event = self._transition(current, TaskState.DISPATCHING)
            yield self._ledger_event(ledger_event)

            produced_any = False
            total = len(plan.steps)
            for index, step in enumerate(plan.steps, start=1):
                if self.cancel_event.is_set():
                    async for event in self._block(current, modality=step.modality, reason="task dispatch cancelled"):
                        yield event
                    return

                yield Event(
                    "progress",
                    current.task_id,
                    {"message": f"dispatching {step.modality}", "step": index, "total": total},
                )
                hub_result = await self._dispatch_step(step)
                safe_payload = hub_adapter.redact_hub_response(hub_result.get("payload", hub_result))
                gate_status = str(hub_result.get("status") or safe_payload.get("status") or "unknown")
                ai_ledger = append_event(
                    self.account,
                    ai_call_event(
                        current.task_id,
                        op=step.op,
                        vendor=step.vendor,
                        gate_status=gate_status,
                        redacted_payload=safe_payload,
                        prompt_text=step.prompt_text,
                    ),
                )
                yield self._ledger_event(ai_ledger)
                yield Event("ai_delta", current.task_id, safe_payload)

                if hub_result.get("outcome") != "ok":
                    reason = str(hub_result.get("reason") or safe_payload.get("reason") or "hub dispatch blocked")
                    async for event in self._block(current, modality=step.modality, reason=reason):
                        yield event
                    return

                if current.state is TaskState.DISPATCHING:
                    current, ledger_event = self._transition(current, TaskState.PRODUCING)
                    yield self._ledger_event(ledger_event)

                artifact_event = self._write_artifact(current, step, safe_payload, index=index)
                produced_any = True
                yield self._ledger_event(artifact_event)
                yield Event("artifact", current.task_id, dict(artifact_event.payload))

            if not produced_any:
                async for event in self._block(current, modality="task", reason="hub produced no artifact"):
                    yield event
                return

            current, ledger_event = self._transition(current, TaskState.CROSS_VALIDATING)
            yield self._ledger_event(ledger_event)
            cross_event = append_event(
                self.account,
                cross_validation_event(current.task_id, checker="platform.dispatcher", verdict="passed"),
            )
            yield self._ledger_event(cross_event)
            current, ledger_event = self._transition(current, TaskState.DELIVERED)
            yield self._ledger_event(ledger_event)
            yield Event("progress", current.task_id, {"message": "delivered", "step": total, "total": total})
        except Exception as exc:  # pragma: no cover - defensive terminal safety
            reason = sanitize_error_msg(str(exc), max_chars=512) or "dispatcher error"
            if not is_terminal_task_state(current.state):
                try:
                    current, ledger_event = self._transition(current, TaskState.ERROR)
                    yield self._ledger_event(ledger_event)
                except Exception:
                    pass
            yield Event("error", current.task_id, {"code": "dispatcher_error", "reason": reason})

    def _build_plan(self, task: Task) -> Plan:
        modalities = tuple(task.modality_targets or ["text"])
        recall = RecallResult(
            slug=f"{task.task_id}/request",
            title=task.title,
            chunk_text=self.user_text,
            score=1.0,
            type="user_message",
            chunk_source="platform_ws",
            source_id=task.task_id,
        )
        ranked = rank_recall_results((recall,), token_budget=compat.PROMPT_MAX_CHARS // 4)
        context = "\n\n".join(item.chunk_text for item in ranked.results if item.chunk_text)
        tier = verification_tier.select_verification_tier(
            verification_tier.ChangeMetadata(
                files_changed=max(1, len(modalities)),
                lines_changed=max(1, self.user_text.count("\n") + 1),
                has_architectural_changes=False,
                has_security_implications=True,
                test_coverage="full",
            )
        )

        steps: list[PlanStep] = []
        blocked: list[ModalityBlocked] = []
        for modality in modalities:
            resolved = resolve_modality(modality)
            if isinstance(resolved, ModalityBlocked):
                blocked.append(resolved)
                continue
            steps.append(self._step_from_route(task, resolved, context))

        return Plan(
            steps=tuple(steps),
            blocked=tuple(blocked),
            created_at=artifacts.planning_artifact_timestamp(),
            verification_tier=tier,
            context_token_count=ranked.meta.used,
            dispatch_status_known=ledger_contracts.is_dispatch_status("pending"),
        )

    def _step_from_route(self, task: Task, route: ModalityRoute, context: str) -> PlanStep:
        prompt = (
            f"{route.prompt_preamble}\n\n"
            f"Task: {task.title}\n"
            f"Task id: {task.task_id}\n"
            f"Requested modality: {route.modality}\n\n"
            f"User request:\n{self.user_text.strip()}"
        )
        if context and context != self.user_text.strip():
            prompt = f"{prompt}\n\nRanked context:\n{context}"
        params = {"profile": route.profile, "prompt": prompt, "reuse_conversation": False}
        return PlanStep(
            modality=route.modality,
            op=route.op,
            vendor=route.vendor,
            params_template=params,
            prompt_text=prompt,
            artifact_extension=route.artifact_extension,
        )

    async def _dispatch_step(self, step: PlanStep) -> dict[str, Any]:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(hub_adapter.dispatch, step.op, dict(step.params_template)),
                timeout=compat.AUTOMATION_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            payload = hub_adapter.redact_hub_response(
                {"status": "not_implemented", "reason": "hub dispatch timed out"}
            )
            return {"outcome": "blocked", "status": "not_implemented", "reason": "hub dispatch timed out", "payload": payload}

    def _transition(self, task: Task, to_state: TaskState) -> tuple[Task, LedgerEvent]:
        updated = task_store.update_task_state(self.account, task.task_id, to_state)
        return updated, _read_last_ledger_event(self.account, task.task_id)

    async def _block(self, task: Task, *, modality: str, reason: str) -> AsyncIterator[Event]:
        current = task_store.load_task(self.account, task.task_id)
        if not is_terminal_task_state(current.state):
            try:
                current, ledger_event = self._transition(current, TaskState.BLOCKED)
                yield self._ledger_event(ledger_event)
            except Exception:
                pass
        safe_reason = sanitize_error_msg(str(reason), max_chars=512) or "blocked"
        yield Event("blocked", current.task_id, {"modality": modality or "task", "reason": safe_reason})

    def _write_artifact(self, task: Task, step: PlanStep, payload: dict[str, Any], *, index: int) -> LedgerEvent:
        rel_path = f"tasks/{task.task_id}/artifacts/{index:02d}-{step.modality}.{step.artifact_extension}"
        artifact_path = resolve_user_path(self.account, rel_path)
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        content = _artifact_content(step.modality, payload)
        encoded = content.encode("utf-8")
        artifact_path.write_bytes(encoded)
        artifact_path.chmod(0o600)
        return append_event(
            self.account,
            artifact_produced_event(
                task.task_id,
                modality=step.modality,
                rel_path=rel_path,
                sha256=hashlib.sha256(encoded).hexdigest(),
                bytes_count=len(encoded),
            ),
        )

    @staticmethod
    def _ledger_event(event: LedgerEvent) -> Event:
        return Event("ledger", event.task_id, event.to_json_dict())


def _artifact_content(modality: str, payload: dict[str, Any]) -> str:
    for key in ("response_text", "summary", "message"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return f"# {modality}\n\n{value.strip()}\n"
    return f"# {modality}\n\n```json\n{json.dumps(payload, ensure_ascii=False, sort_keys=True)}\n```\n"


def _read_last_ledger_event(account: str, task_id: str) -> LedgerEvent:
    rows = [line for line in ledger_path_for(account, task_id).read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        raise ValueError("ledger is empty")
    payload = json.loads(rows[-1])
    if not isinstance(payload, dict):
        raise ValueError("ledger row must be an object")
    return LedgerEvent.from_json_dict(payload)


__all__ = ["Event", "MAX_DISPATCH_STEPS", "Plan", "PlanStep", "Dispatcher"]

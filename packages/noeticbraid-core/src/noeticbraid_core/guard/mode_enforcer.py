"""ModeEnforcer for Phase 1.1 (审批轴模式 / approval axis).

DESIGN_NOTE:
    Phase 1.1 ModeEnforcer 用**审批轴模式**（dry_run / supervised / autonomous）。
    legacy 4 modes（execution / mirror / evaluator / common）是**操作平面轴**，正交。
    Phase 1.2 会叠加操作平面轴；Phase 1.1 不混合两轴。

    审批轴语义：
      - dry_run: 仅允许只读 + 内部 state read，所有外部副作用 / 写动作 deny
      - supervised: 允许常规读写 + ledger append；高风险（删除、CLI、web、外部写、凭证）走 require_approval
      - autonomous: 在 supervised 基础上放宽 delete + LLM CLI；web / subprocess / external_write / use_credential
                    仍然 require_approval（因为 Phase 1.1 没实装真实 approval pipeline）
      - 三个 RED actions（write_user_raw_vault / rewrite_sidenote_existing / cross_account_transfer）
        与 mode 无关，永远 deny。

action 10 vs action 12 边界：
    action 10 invoke_llm_code_cli = CLI-based LLM 工具（codex / claude CLI 等）。
    action 12 invoke_subprocess = 非 LLM shell 命令（git / python script / echo / ls 等）。
    同时属于两类的命令，调用方必须 check 两个 action，两个都通过才执行。
    ModeEnforcer 不做命令名 → action 类型的自动推断；调用方负责正确分类。

require_approval timeout (Phase 1.1 stub):
    - check() returns require_approval with a uuid approval_request_id but does
      not block-wait for human decision.
    - The caller layer is responsible for the actual approval pipeline (queue,
      UI prompt, timeout monitoring). ModeEnforcer only emits the protocol shape
      and exposes APPROVAL_TIMEOUT_DEFAULT_SEC = 86400 (24h).
    - Environment variable NOETICBRAID_APPROVAL_TIMEOUT_SEC overrides the default.
    - When caller observes a timeout, it should treat the final decision as
      Decision(verdict=DENY, reason="approval_timeout"). For convenience,
      approval_timeout_decision() emits that exact protocol shape.
    - Phase 1.2 will add the real wait-for-approval flow.
"""

from __future__ import annotations

import os
import uuid
from typing import Literal, Optional

from .actions import Action
from .cli_runner_registry import CliRunnerRegistry
from .decisions import Decision, DecisionVerdict
from .errors import InvalidContextError, UnknownActionError
from .protocols import LedgerSink, _NoOpLedgerSink


Mode = Literal["dry_run", "supervised", "autonomous"]


APPROVAL_TIMEOUT_DEFAULT_SEC = 86400  # 24h
APPROVAL_TIMEOUT_ENV_VAR = "NOETICBRAID_APPROVAL_TIMEOUT_SEC"


# 16 × 3 decision matrix. Values are derived from the locked Stage 2 design.
_DECISION_MATRIX: dict[Action, dict[Mode, DecisionVerdict]] = {
    Action.READ_LOCAL_FILE: {
        "dry_run": DecisionVerdict.ALLOW,
        "supervised": DecisionVerdict.ALLOW,
        "autonomous": DecisionVerdict.ALLOW,
    },
    Action.WRITE_LOCAL_FILE_NONDESTRUCTIVE: {
        "dry_run": DecisionVerdict.DENY,
        "supervised": DecisionVerdict.ALLOW,
        "autonomous": DecisionVerdict.ALLOW,
    },
    Action.DELETE_LOCAL_FILE: {
        "dry_run": DecisionVerdict.DENY,
        "supervised": DecisionVerdict.REQUIRE_APPROVAL,
        "autonomous": DecisionVerdict.ALLOW,
    },
    Action.READ_STATE: {
        "dry_run": DecisionVerdict.ALLOW,
        "supervised": DecisionVerdict.ALLOW,
        "autonomous": DecisionVerdict.ALLOW,
    },
    Action.APPEND_RUN_LEDGER: {
        "dry_run": DecisionVerdict.DENY,
        "supervised": DecisionVerdict.ALLOW,
        "autonomous": DecisionVerdict.ALLOW,
    },
    Action.READ_SOURCE_INDEX: {
        "dry_run": DecisionVerdict.ALLOW,
        "supervised": DecisionVerdict.ALLOW,
        "autonomous": DecisionVerdict.ALLOW,
    },
    Action.WRITE_SOURCE_INDEX: {
        "dry_run": DecisionVerdict.DENY,
        "supervised": DecisionVerdict.ALLOW,
        "autonomous": DecisionVerdict.ALLOW,
    },
    Action.READ_USER_RAW_VAULT: {
        "dry_run": DecisionVerdict.ALLOW,
        "supervised": DecisionVerdict.ALLOW,
        "autonomous": DecisionVerdict.ALLOW,
    },
    # RED LINE: permanently denied in every mode.
    Action.WRITE_USER_RAW_VAULT: {
        "dry_run": DecisionVerdict.DENY,
        "supervised": DecisionVerdict.DENY,
        "autonomous": DecisionVerdict.DENY,
    },
    Action.INVOKE_LLM_CODE_CLI: {
        "dry_run": DecisionVerdict.DENY,
        "supervised": DecisionVerdict.REQUIRE_APPROVAL,
        "autonomous": DecisionVerdict.ALLOW,
    },
    Action.INVOKE_LLM_WEB: {
        "dry_run": DecisionVerdict.DENY,
        "supervised": DecisionVerdict.REQUIRE_APPROVAL,
        "autonomous": DecisionVerdict.REQUIRE_APPROVAL,
    },
    Action.INVOKE_SUBPROCESS: {
        "dry_run": DecisionVerdict.DENY,
        "supervised": DecisionVerdict.REQUIRE_APPROVAL,
        "autonomous": DecisionVerdict.REQUIRE_APPROVAL,
    },
    Action.EXTERNAL_WRITE: {
        "dry_run": DecisionVerdict.DENY,
        "supervised": DecisionVerdict.REQUIRE_APPROVAL,
        "autonomous": DecisionVerdict.REQUIRE_APPROVAL,
    },
    Action.USE_CREDENTIAL: {
        "dry_run": DecisionVerdict.DENY,
        "supervised": DecisionVerdict.REQUIRE_APPROVAL,
        "autonomous": DecisionVerdict.REQUIRE_APPROVAL,
    },
    # RED LINE: permanently denied in every mode.
    Action.REWRITE_SIDENOTE_EXISTING: {
        "dry_run": DecisionVerdict.DENY,
        "supervised": DecisionVerdict.DENY,
        "autonomous": DecisionVerdict.DENY,
    },
    # RED LINE: permanently denied in every mode.
    Action.CROSS_ACCOUNT_TRANSFER: {
        "dry_run": DecisionVerdict.DENY,
        "supervised": DecisionVerdict.DENY,
        "autonomous": DecisionVerdict.DENY,
    },
}


RED_LINE_ACTIONS: frozenset[Action] = frozenset(
    {
        Action.WRITE_USER_RAW_VAULT,
        Action.REWRITE_SIDENOTE_EXISTING,
        Action.CROSS_ACCOUNT_TRANSFER,
    }
)


class ModeEnforcer:
    """Phase 1.1 ModeEnforcer (approval axis).

    Args:
        mode: One of "dry_run" / "supervised" / "autonomous".
        ledger_sink: Implements LedgerSink Protocol (default: _NoOpLedgerSink).
            Stage 3 integration injects a RunLedger instance.
        approval_timeout_sec: REQUIRE_APPROVAL Decision timeout (default 86400 = 24h).
            Environment variable NOETICBRAID_APPROVAL_TIMEOUT_SEC overrides the
            default; explicit constructor arg overrides env.
        cli_runner_registry: CliRunnerRegistry instance (default: new instance
            with initial "echo" entry). Required for action 12 invoke_subprocess
            context check.
    """

    def __init__(
        self,
        mode: Mode,
        ledger_sink: Optional[LedgerSink] = None,
        approval_timeout_sec: Optional[int] = None,
        cli_runner_registry: Optional[CliRunnerRegistry] = None,
    ) -> None:
        if mode not in ("dry_run", "supervised", "autonomous"):
            raise ValueError(f"invalid mode: {mode!r}")
        self._mode: Mode = mode
        self._ledger_sink: LedgerSink = ledger_sink if ledger_sink is not None else _NoOpLedgerSink()
        self._approval_timeout_sec: int = self._resolve_timeout(approval_timeout_sec)
        self._cli_runner_registry: CliRunnerRegistry = (
            cli_runner_registry if cli_runner_registry is not None else CliRunnerRegistry()
        )

    @staticmethod
    def _resolve_timeout(explicit: Optional[int]) -> int:
        if explicit is not None:
            if explicit <= 0:
                raise ValueError("approval_timeout_sec must be > 0")
            return explicit
        env_value = os.environ.get(APPROVAL_TIMEOUT_ENV_VAR)
        if env_value is not None:
            try:
                parsed = int(env_value)
            except ValueError:
                return APPROVAL_TIMEOUT_DEFAULT_SEC
            if parsed > 0:
                return parsed
        return APPROVAL_TIMEOUT_DEFAULT_SEC

    @property
    def mode(self) -> Mode:
        return self._mode

    @property
    def approval_timeout_sec(self) -> int:
        return self._approval_timeout_sec

    @property
    def ledger_sink(self) -> LedgerSink:
        return self._ledger_sink

    @property
    def cli_runner_registry(self) -> CliRunnerRegistry:
        return self._cli_runner_registry

    def check(self, action: Action | str, context: Optional[dict] = None) -> Decision:
        """Decide whether an action is allowed in the current mode.

        Args:
            action: One of the 16 Action enum values, or a string equal to one
                of those Action values.
            context: Optional dict carrying action-specific keys. For
                Action.INVOKE_SUBPROCESS, must contain a registered "runner_name"
                to proceed to the normal mode matrix.

        Returns:
            Decision with verdict ALLOW / DENY / REQUIRE_APPROVAL. For
            REQUIRE_APPROVAL, approval_request_id is a uuid string.

        Raises:
            UnknownActionError: if action is not one of the 16 Action values.
            InvalidContextError: if context is supplied but is not a dict.
        """
        action_enum = self._coerce_action(action)
        if context is not None and not isinstance(context, dict):
            raise InvalidContextError("context must be a dict when provided")
        ctx = context or {}

        if ctx.get("approval_timed_out") is True:
            return self.approval_timeout_decision()

        # action 12 invoke_subprocess: check runner registry before mode matrix.
        if action_enum == Action.INVOKE_SUBPROCESS:
            runner_name = ctx.get("runner_name")
            if not runner_name or self._cli_runner_registry.lookup(runner_name) is None:
                return Decision(
                    verdict=DecisionVerdict.DENY,
                    reason=f"runner not registered: {runner_name!r}",
                    approval_request_id=None,
                )

        verdict = _DECISION_MATRIX[action_enum][self._mode]

        if action_enum in RED_LINE_ACTIONS:
            assert verdict == DecisionVerdict.DENY  # invariant
            return Decision(
                verdict=DecisionVerdict.DENY,
                reason=f"red line action: {action_enum.value} is permanently denied",
                approval_request_id=None,
            )

        if verdict == DecisionVerdict.REQUIRE_APPROVAL:
            return Decision(
                verdict=DecisionVerdict.REQUIRE_APPROVAL,
                reason=f"action {action_enum.value} requires approval in mode {self._mode}",
                approval_request_id=str(uuid.uuid4()),
            )

        if verdict == DecisionVerdict.DENY:
            return Decision(
                verdict=DecisionVerdict.DENY,
                reason=f"action {action_enum.value} is denied in mode {self._mode}",
                approval_request_id=None,
            )

        return Decision(
            verdict=DecisionVerdict.ALLOW,
            reason=f"action {action_enum.value} allowed in mode {self._mode}",
            approval_request_id=None,
        )

    def with_mode(self, new_mode: Mode) -> "ModeEnforcer":
        """Return a new ModeEnforcer with updated mode; reuse sink, registry, timeout."""
        return ModeEnforcer(
            mode=new_mode,
            ledger_sink=self._ledger_sink,
            approval_timeout_sec=self._approval_timeout_sec,
            cli_runner_registry=self._cli_runner_registry,
        )

    @staticmethod
    def approval_timeout_decision() -> Decision:
        """Return the Phase 1.1 protocol shape for an expired approval request."""
        return Decision(
            verdict=DecisionVerdict.DENY,
            reason="approval_timeout",
            approval_request_id=None,
        )

    @staticmethod
    def _coerce_action(action: Action | str) -> Action:
        if isinstance(action, Action):
            return action
        try:
            return Action(action)
        except (TypeError, ValueError) as exc:
            raise UnknownActionError(f"unknown action: {action!r}") from exc

"""Tests for guard.mode_enforcer.

Covers:
- 48 cells parametrize: 16 actions × 3 modes → expected_verdict
- 3 RED LINE actions (9 / 15 / 16): all 3 modes deny
- action 10 vs action 12 disambiguation: caller checks both
- approval_timeout: default 86400; env var override; timeout decision shape
- LedgerSink Protocol satisfaction (structural subtyping)
- ModeEnforcer.with_mode() returns new instance
- UnknownActionError when action is not one of the 16 actions
- approval_request_id is uuid string when REQUIRE_APPROVAL
"""

from __future__ import annotations

import os
import uuid
from dataclasses import FrozenInstanceError
from unittest.mock import patch

import pytest

from noeticbraid_core.guard import (
    APPROVAL_TIMEOUT_DEFAULT_SEC,
    APPROVAL_TIMEOUT_ENV_VAR,
    RED_LINE_ACTIONS,
    Action,
    Decision,
    DecisionVerdict,
    LedgerSink,
    Mode,
    ModeEnforcer,
    UnknownActionError,
)
from noeticbraid_core.guard.errors import InvalidContextError
from noeticbraid_core.guard.protocols import _NoOpLedgerSink


# ---------- 48-cell decision matrix ----------

# Expected verdicts derived from the locked §2.2.1 design table; do NOT modify.
EXPECTED: dict[tuple[Action, Mode], DecisionVerdict] = {
    # action 1: read_local_file
    (Action.READ_LOCAL_FILE, "dry_run"): DecisionVerdict.ALLOW,
    (Action.READ_LOCAL_FILE, "supervised"): DecisionVerdict.ALLOW,
    (Action.READ_LOCAL_FILE, "autonomous"): DecisionVerdict.ALLOW,
    # action 2: write_local_file_nondestructive
    (Action.WRITE_LOCAL_FILE_NONDESTRUCTIVE, "dry_run"): DecisionVerdict.DENY,
    (Action.WRITE_LOCAL_FILE_NONDESTRUCTIVE, "supervised"): DecisionVerdict.ALLOW,
    (Action.WRITE_LOCAL_FILE_NONDESTRUCTIVE, "autonomous"): DecisionVerdict.ALLOW,
    # action 3: delete_local_file
    (Action.DELETE_LOCAL_FILE, "dry_run"): DecisionVerdict.DENY,
    (Action.DELETE_LOCAL_FILE, "supervised"): DecisionVerdict.REQUIRE_APPROVAL,
    (Action.DELETE_LOCAL_FILE, "autonomous"): DecisionVerdict.ALLOW,
    # action 4: read_state
    (Action.READ_STATE, "dry_run"): DecisionVerdict.ALLOW,
    (Action.READ_STATE, "supervised"): DecisionVerdict.ALLOW,
    (Action.READ_STATE, "autonomous"): DecisionVerdict.ALLOW,
    # action 5: append_run_ledger
    (Action.APPEND_RUN_LEDGER, "dry_run"): DecisionVerdict.DENY,
    (Action.APPEND_RUN_LEDGER, "supervised"): DecisionVerdict.ALLOW,
    (Action.APPEND_RUN_LEDGER, "autonomous"): DecisionVerdict.ALLOW,
    # action 6: read_source_index
    (Action.READ_SOURCE_INDEX, "dry_run"): DecisionVerdict.ALLOW,
    (Action.READ_SOURCE_INDEX, "supervised"): DecisionVerdict.ALLOW,
    (Action.READ_SOURCE_INDEX, "autonomous"): DecisionVerdict.ALLOW,
    # action 7: write_source_index
    (Action.WRITE_SOURCE_INDEX, "dry_run"): DecisionVerdict.DENY,
    (Action.WRITE_SOURCE_INDEX, "supervised"): DecisionVerdict.ALLOW,
    (Action.WRITE_SOURCE_INDEX, "autonomous"): DecisionVerdict.ALLOW,
    # action 8: read_user_raw_vault
    (Action.READ_USER_RAW_VAULT, "dry_run"): DecisionVerdict.ALLOW,
    (Action.READ_USER_RAW_VAULT, "supervised"): DecisionVerdict.ALLOW,
    (Action.READ_USER_RAW_VAULT, "autonomous"): DecisionVerdict.ALLOW,
    # action 9 RED: write_user_raw_vault — deny in ALL modes
    (Action.WRITE_USER_RAW_VAULT, "dry_run"): DecisionVerdict.DENY,
    (Action.WRITE_USER_RAW_VAULT, "supervised"): DecisionVerdict.DENY,
    (Action.WRITE_USER_RAW_VAULT, "autonomous"): DecisionVerdict.DENY,
    # action 10: invoke_llm_code_cli
    (Action.INVOKE_LLM_CODE_CLI, "dry_run"): DecisionVerdict.DENY,
    (Action.INVOKE_LLM_CODE_CLI, "supervised"): DecisionVerdict.REQUIRE_APPROVAL,
    (Action.INVOKE_LLM_CODE_CLI, "autonomous"): DecisionVerdict.ALLOW,
    # action 11: invoke_llm_web
    (Action.INVOKE_LLM_WEB, "dry_run"): DecisionVerdict.DENY,
    (Action.INVOKE_LLM_WEB, "supervised"): DecisionVerdict.REQUIRE_APPROVAL,
    (Action.INVOKE_LLM_WEB, "autonomous"): DecisionVerdict.REQUIRE_APPROVAL,
    # action 12: invoke_subprocess; runner_name=echo avoids registry-deny short-circuit
    (Action.INVOKE_SUBPROCESS, "dry_run"): DecisionVerdict.DENY,
    (Action.INVOKE_SUBPROCESS, "supervised"): DecisionVerdict.REQUIRE_APPROVAL,
    (Action.INVOKE_SUBPROCESS, "autonomous"): DecisionVerdict.REQUIRE_APPROVAL,
    # action 13: external_write
    (Action.EXTERNAL_WRITE, "dry_run"): DecisionVerdict.DENY,
    (Action.EXTERNAL_WRITE, "supervised"): DecisionVerdict.REQUIRE_APPROVAL,
    (Action.EXTERNAL_WRITE, "autonomous"): DecisionVerdict.REQUIRE_APPROVAL,
    # action 14: use_credential
    (Action.USE_CREDENTIAL, "dry_run"): DecisionVerdict.DENY,
    (Action.USE_CREDENTIAL, "supervised"): DecisionVerdict.REQUIRE_APPROVAL,
    (Action.USE_CREDENTIAL, "autonomous"): DecisionVerdict.REQUIRE_APPROVAL,
    # action 15 RED: rewrite_sidenote_existing
    (Action.REWRITE_SIDENOTE_EXISTING, "dry_run"): DecisionVerdict.DENY,
    (Action.REWRITE_SIDENOTE_EXISTING, "supervised"): DecisionVerdict.DENY,
    (Action.REWRITE_SIDENOTE_EXISTING, "autonomous"): DecisionVerdict.DENY,
    # action 16 RED: cross_account_transfer
    (Action.CROSS_ACCOUNT_TRANSFER, "dry_run"): DecisionVerdict.DENY,
    (Action.CROSS_ACCOUNT_TRANSFER, "supervised"): DecisionVerdict.DENY,
    (Action.CROSS_ACCOUNT_TRANSFER, "autonomous"): DecisionVerdict.DENY,
}


@pytest.mark.parametrize(("action", "mode"), list(EXPECTED.keys()))
def test_action_matrix_16x3(action: Action, mode: Mode) -> None:
    """All 48 (action, mode) cells produce the expected verdict."""
    enforcer = ModeEnforcer(mode=mode)
    context = {"runner_name": "echo"} if action == Action.INVOKE_SUBPROCESS else None
    decision = enforcer.check(action, context)
    assert decision.verdict == EXPECTED[(action, mode)], (
        f"({action.value}, {mode}) expected {EXPECTED[(action, mode)]}, "
        f"got {decision.verdict}"
    )
    assert decision.reason
    if decision.verdict == DecisionVerdict.REQUIRE_APPROVAL:
        assert decision.approval_request_id is not None
    else:
        assert decision.approval_request_id is None


def test_matrix_covers_exactly_16_actions_and_48_cells() -> None:
    assert len(Action) == 16
    assert len(EXPECTED) == 48
    assert set(action for action, _mode in EXPECTED) == set(Action)


def test_action_values_match_locked_design() -> None:
    assert [action.value for action in Action] == [
        "read_local_file",
        "write_local_file_nondestructive",
        "delete_local_file",
        "read_state",
        "append_run_ledger",
        "read_source_index",
        "write_source_index",
        "read_user_raw_vault",
        "write_user_raw_vault",
        "invoke_llm_code_cli",
        "invoke_llm_web",
        "invoke_subprocess",
        "external_write",
        "use_credential",
        "rewrite_sidenote_existing",
        "cross_account_transfer",
    ]


# ---------- 3 RED LINE actions ----------


@pytest.mark.parametrize("mode", ["dry_run", "supervised", "autonomous"])
def test_red_line_action_9_always_deny(mode: Mode) -> None:
    enforcer = ModeEnforcer(mode=mode)
    decision = enforcer.check(Action.WRITE_USER_RAW_VAULT)
    assert decision.verdict == DecisionVerdict.DENY
    assert "red line" in decision.reason.lower()


@pytest.mark.parametrize("mode", ["dry_run", "supervised", "autonomous"])
def test_red_line_action_15_always_deny(mode: Mode) -> None:
    enforcer = ModeEnforcer(mode=mode)
    decision = enforcer.check(Action.REWRITE_SIDENOTE_EXISTING)
    assert decision.verdict == DecisionVerdict.DENY
    assert "red line" in decision.reason.lower()


@pytest.mark.parametrize("mode", ["dry_run", "supervised", "autonomous"])
def test_red_line_action_16_always_deny(mode: Mode) -> None:
    enforcer = ModeEnforcer(mode=mode)
    decision = enforcer.check(Action.CROSS_ACCOUNT_TRANSFER)
    assert decision.verdict == DecisionVerdict.DENY
    assert "red line" in decision.reason.lower()


def test_red_line_actions_constant_set() -> None:
    """RED_LINE_ACTIONS frozenset matches the three documented RED actions."""
    assert RED_LINE_ACTIONS == frozenset(
        {
            Action.WRITE_USER_RAW_VAULT,
            Action.REWRITE_SIDENOTE_EXISTING,
            Action.CROSS_ACCOUNT_TRANSFER,
        }
    )


# ---------- action 10 vs 12 disambiguation ----------


def test_action_10_vs_12_disambiguation() -> None:
    """Caller must check both action 10 and action 12 for ambiguous commands.

    Example: a command that is BOTH a CLI-based LLM tool AND a generic shell
    invocation. ModeEnforcer does NOT auto-classify; caller's responsibility.
    """
    enforcer = ModeEnforcer(mode="autonomous")
    # action 10 in autonomous: ALLOW
    d10 = enforcer.check(Action.INVOKE_LLM_CODE_CLI)
    assert d10.verdict == DecisionVerdict.ALLOW
    # action 12 in autonomous (with registered runner): REQUIRE_APPROVAL
    d12 = enforcer.check(Action.INVOKE_SUBPROCESS, {"runner_name": "echo"})
    assert d12.verdict == DecisionVerdict.REQUIRE_APPROVAL
    # Caller logic: BOTH must pass to execute. d12 != ALLOW, so abort.
    both_pass = (d10.verdict == DecisionVerdict.ALLOW) and (d12.verdict == DecisionVerdict.ALLOW)
    assert not both_pass


def test_action_string_value_is_accepted_for_registered_action() -> None:
    enforcer = ModeEnforcer(mode="autonomous")
    decision = enforcer.check("invoke_subprocess", {"runner_name": "echo"})
    assert decision.verdict == DecisionVerdict.REQUIRE_APPROVAL


# ---------- LedgerSink Protocol satisfaction ----------


def test_mode_enforcer_with_no_op_ledger_sink() -> None:
    """Default ledger_sink is _NoOpLedgerSink and satisfies LedgerSink Protocol."""
    enforcer = ModeEnforcer(mode="supervised")
    assert isinstance(enforcer.ledger_sink, _NoOpLedgerSink)
    # structural subtyping: _NoOpLedgerSink satisfies LedgerSink Protocol
    assert isinstance(enforcer.ledger_sink, LedgerSink)


def test_mode_enforcer_ledger_sink_protocol_satisfaction() -> None:
    """A custom class with .append(record) satisfies LedgerSink (structural)."""

    class CustomSink:
        def __init__(self) -> None:
            self.records: list = []

        def append(self, record) -> None:
            self.records.append(record)

    sink = CustomSink()
    assert isinstance(sink, LedgerSink)  # @runtime_checkable structural check
    enforcer = ModeEnforcer(mode="supervised", ledger_sink=sink)
    assert enforcer.ledger_sink is sink


# ---------- approval_timeout ----------


def test_approval_timeout_default_86400() -> None:
    """Default timeout is 86400 (24h)."""
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop(APPROVAL_TIMEOUT_ENV_VAR, None)
        enforcer = ModeEnforcer(mode="supervised")
        assert enforcer.approval_timeout_sec == APPROVAL_TIMEOUT_DEFAULT_SEC == 86400


def test_approval_timeout_env_override() -> None:
    """Env var NOETICBRAID_APPROVAL_TIMEOUT_SEC overrides default."""
    with patch.dict(os.environ, {APPROVAL_TIMEOUT_ENV_VAR: "300"}):
        enforcer = ModeEnforcer(mode="supervised")
        assert enforcer.approval_timeout_sec == 300


def test_approval_timeout_explicit_arg_overrides_env() -> None:
    """Explicit constructor arg takes precedence over env var."""
    with patch.dict(os.environ, {APPROVAL_TIMEOUT_ENV_VAR: "300"}):
        enforcer = ModeEnforcer(mode="supervised", approval_timeout_sec=600)
        assert enforcer.approval_timeout_sec == 600


@pytest.mark.parametrize("env_value", ["not-a-number", "0", "-1"])
def test_approval_timeout_env_invalid_falls_back_to_default(env_value: str) -> None:
    with patch.dict(os.environ, {APPROVAL_TIMEOUT_ENV_VAR: env_value}):
        enforcer = ModeEnforcer(mode="supervised")
        assert enforcer.approval_timeout_sec == APPROVAL_TIMEOUT_DEFAULT_SEC


def test_approval_timeout_explicit_non_positive_rejected() -> None:
    with pytest.raises(ValueError):
        ModeEnforcer(mode="supervised", approval_timeout_sec=0)


def test_approval_timeout_decision_shape() -> None:
    decision = ModeEnforcer.approval_timeout_decision()
    assert decision.verdict == DecisionVerdict.DENY
    assert decision.reason == "approval_timeout"
    assert decision.approval_request_id is None


def test_approval_timeout_context_flag_emits_timeout_decision() -> None:
    enforcer = ModeEnforcer(mode="supervised")
    decision = enforcer.check(Action.DELETE_LOCAL_FILE, {"approval_timed_out": True})
    assert decision.verdict == DecisionVerdict.DENY
    assert decision.reason == "approval_timeout"


# ---------- approval_request_id is uuid ----------


def test_require_approval_decision_carries_uuid() -> None:
    """REQUIRE_APPROVAL decisions carry a uuid string approval_request_id."""
    enforcer = ModeEnforcer(mode="supervised")
    decision = enforcer.check(Action.DELETE_LOCAL_FILE)
    assert decision.verdict == DecisionVerdict.REQUIRE_APPROVAL
    assert decision.approval_request_id is not None
    uuid.UUID(decision.approval_request_id)


def test_allow_decision_has_no_approval_id() -> None:
    enforcer = ModeEnforcer(mode="autonomous")
    decision = enforcer.check(Action.READ_LOCAL_FILE)
    assert decision.verdict == DecisionVerdict.ALLOW
    assert decision.approval_request_id is None


def test_deny_decision_has_no_approval_id() -> None:
    enforcer = ModeEnforcer(mode="dry_run")
    decision = enforcer.check(Action.WRITE_LOCAL_FILE_NONDESTRUCTIVE)
    assert decision.verdict == DecisionVerdict.DENY
    assert decision.approval_request_id is None


def test_decision_requires_uuid_id_for_require_approval() -> None:
    with pytest.raises(ValueError):
        Decision(DecisionVerdict.REQUIRE_APPROVAL, "needs approval")


# ---------- Decision invariants ----------


def test_decision_is_frozen() -> None:
    decision = Decision(DecisionVerdict.ALLOW, "allowed")
    with pytest.raises(FrozenInstanceError):
        decision.reason = "mutated"  # type: ignore[misc]


def test_decision_rejects_empty_reason() -> None:
    with pytest.raises(ValueError):
        Decision(DecisionVerdict.ALLOW, "")


def test_decision_rejects_raw_string_verdict() -> None:
    with pytest.raises(TypeError):
        Decision("allow", "raw string not accepted")  # type: ignore[arg-type]


def test_decision_rejects_approval_id_for_allow_or_deny() -> None:
    with pytest.raises(ValueError):
        Decision(DecisionVerdict.ALLOW, "allowed", approval_request_id="abc")
    with pytest.raises(ValueError):
        Decision(DecisionVerdict.DENY, "denied", approval_request_id="abc")


# ---------- with_mode + UnknownAction + invalid mode/context ----------


def test_with_mode_returns_new_instance() -> None:
    e1 = ModeEnforcer(mode="dry_run")
    e2 = e1.with_mode("autonomous")
    assert e1 is not e2
    assert e1.mode == "dry_run"
    assert e2.mode == "autonomous"
    # ledger_sink + registry + timeout are reused
    assert e1.ledger_sink is e2.ledger_sink
    assert e1.cli_runner_registry is e2.cli_runner_registry
    assert e1.approval_timeout_sec == e2.approval_timeout_sec


def test_invalid_mode_raises() -> None:
    with pytest.raises(ValueError):
        ModeEnforcer(mode="execution")  # type: ignore[arg-type]


def test_unknown_action_raises() -> None:
    enforcer = ModeEnforcer(mode="supervised")
    with pytest.raises(UnknownActionError):
        enforcer.check("not_an_action_enum")


def test_invalid_context_type_raises() -> None:
    enforcer = ModeEnforcer(mode="supervised")
    with pytest.raises(InvalidContextError):
        enforcer.check(Action.READ_LOCAL_FILE, context="not-a-dict")  # type: ignore[arg-type]


# ---------- Stage 2.2 mutable ledger-sink hook ----------


def test_set_ledger_sink_replaces_default_sink() -> None:
    class ReplacementSink:
        def __init__(self) -> None:
            self.records: list = []

        def append(self, record) -> None:
            self.records.append(record)

    enforcer = ModeEnforcer(mode="supervised")
    replacement = ReplacementSink()

    enforcer.set_ledger_sink(replacement)

    assert enforcer.ledger_sink is replacement
    assert isinstance(enforcer.ledger_sink, LedgerSink)


def test_set_ledger_sink_rejects_non_sink_input() -> None:
    enforcer = ModeEnforcer(mode="supervised")

    with pytest.raises(TypeError, match="LedgerSink.append"):
        enforcer.set_ledger_sink(object())  # type: ignore[arg-type]


def test_with_mode_reuses_replaced_ledger_sink() -> None:
    class ReplacementSink:
        def append(self, record) -> None:
            del record

    enforcer = ModeEnforcer(mode="dry_run")
    replacement = ReplacementSink()
    enforcer.set_ledger_sink(replacement)

    updated = enforcer.with_mode("autonomous")

    assert updated.mode == "autonomous"
    assert updated.ledger_sink is replacement


@pytest.mark.parametrize("action", sorted(RED_LINE_ACTIONS, key=lambda item: item.value))
@pytest.mark.parametrize("mode", ["dry_run", "supervised", "autonomous"])
def test_red_line_actions_still_deny_after_ledger_sink_replacement(action: Action, mode: Mode) -> None:
    class ReplacementSink:
        def append(self, record) -> None:
            del record

    enforcer = ModeEnforcer(mode=mode)
    enforcer.set_ledger_sink(ReplacementSink())

    decision = enforcer.check(action)

    assert decision.verdict == DecisionVerdict.DENY
    assert decision.approval_request_id is None
    assert "red line" in decision.reason.lower()

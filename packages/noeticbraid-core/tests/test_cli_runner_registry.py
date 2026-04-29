"""Tests for guard.cli_runner_registry."""

from __future__ import annotations

import pytest

from noeticbraid_core.guard import (
    Action,
    CliRunnerRegistry,
    CliRunnerRegistryError,
    CliRunnerSpec,
    DecisionVerdict,
    ModeEnforcer,
)


def test_cli_runner_registry_initial_echo_present() -> None:
    """Registry is initialized with an 'echo' entry usable by tests."""
    reg = CliRunnerRegistry()
    spec = reg.lookup("echo")
    assert spec is not None
    assert spec.name == "echo"
    assert spec.command == ["echo"]
    assert spec.env == {}
    assert spec.timeout_sec == 5
    assert spec.stdin_allowed is False
    assert "echo" in reg.list_allowed()


def test_cli_runner_registry_register_lookup() -> None:
    reg = CliRunnerRegistry()
    spec = CliRunnerSpec(
        name="git",
        command=["git", "status"],
        env={"GIT_TERMINAL_PROMPT": "0"},
        timeout_sec=30,
        stdin_allowed=False,
    )
    reg.register(spec)
    found = reg.lookup("git")
    assert found is spec
    assert "echo" in reg.list_allowed()
    assert "git" in reg.list_allowed()


def test_cli_runner_registry_unknown_returns_none() -> None:
    reg = CliRunnerRegistry()
    assert reg.lookup("nonexistent") is None


def test_cli_runner_registry_duplicate_register_raises() -> None:
    reg = CliRunnerRegistry()
    with pytest.raises(CliRunnerRegistryError):
        reg.register(CliRunnerSpec(name="echo", command=["echo"], timeout_sec=10))


def test_cli_runner_registry_empty_name_rejected() -> None:
    reg = CliRunnerRegistry()
    with pytest.raises(CliRunnerRegistryError):
        reg.register(CliRunnerSpec(name="", command=["x"], timeout_sec=10))


def test_cli_runner_registry_zero_timeout_rejected() -> None:
    reg = CliRunnerRegistry()
    with pytest.raises(CliRunnerRegistryError):
        reg.register(CliRunnerSpec(name="zero", command=["zero"], timeout_sec=0))


def test_cli_runner_registry_empty_command_rejected() -> None:
    reg = CliRunnerRegistry()
    with pytest.raises(CliRunnerRegistryError):
        reg.register(CliRunnerSpec(name="empty", command=[], timeout_sec=10))


def test_cli_runner_spec_is_frozen() -> None:
    spec = CliRunnerSpec(name="x", command=["x"], timeout_sec=10)
    with pytest.raises(Exception):  # FrozenInstanceError
        spec.name = "y"  # type: ignore[misc]


def test_cli_runner_spec_default_env_is_independent() -> None:
    left = CliRunnerSpec(name="left", command=["left"])
    right = CliRunnerSpec(name="right", command=["right"])
    assert left.env == {}
    assert right.env == {}
    assert left.env is not right.env


def test_cli_runner_registry_unregistered_runner_denied() -> None:
    """ModeEnforcer.check(action 12) denies if runner not registered."""
    enforcer = ModeEnforcer(mode="autonomous")
    decision = enforcer.check(Action.INVOKE_SUBPROCESS, {"runner_name": "nonexistent_runner"})
    assert decision.verdict == DecisionVerdict.DENY
    assert "runner not registered" in decision.reason


def test_cli_runner_registry_no_runner_name_denied() -> None:
    enforcer = ModeEnforcer(mode="autonomous")
    decision = enforcer.check(Action.INVOKE_SUBPROCESS, {})
    assert decision.verdict == DecisionVerdict.DENY
    assert "runner not registered" in decision.reason


def test_cli_runner_registry_registered_runner_passes_mode_check() -> None:
    enforcer = ModeEnforcer(mode="autonomous")
    decision = enforcer.check(Action.INVOKE_SUBPROCESS, {"runner_name": "echo"})
    # autonomous mode still REQUIRE_APPROVAL for action 12 per design table
    assert decision.verdict == DecisionVerdict.REQUIRE_APPROVAL


def test_cli_runner_registry_list_allowed_is_sorted() -> None:
    reg = CliRunnerRegistry()
    reg.register(CliRunnerSpec(name="zzz", command=["zzz"], timeout_sec=10))
    reg.register(CliRunnerSpec(name="aaa", command=["aaa"], timeout_sec=10))
    assert reg.list_allowed() == ["aaa", "echo", "zzz"]

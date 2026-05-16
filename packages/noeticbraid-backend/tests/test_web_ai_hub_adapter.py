# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
for path in (
    REPO_ROOT / "packages" / "noeticbraid-core" / "src",
    REPO_ROOT / "packages" / "noeticbraid-backend" / "src",
):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from noeticbraid_backend.omc_workspace import web_ai_hub_automation as automation  # noqa: E402
from noeticbraid_backend.omc_workspace import web_ai_hub_compat as compat  # noqa: E402


LAUNCH_SAFE_OP = "webai_task_status"
PAGEFUL_OP = "webai_chatgpt_send_prompt"
NON_DISPATCHABLE_PAGEFUL_OP = "browser_read"


class _FakeCdpResponse:
    def __init__(self, *, status: int = 200, body: bytes = b'{"Browser":"Chrome"}') -> None:
        self.status = status
        self._body = body

    def read(self) -> bytes:
        return self._body

    def close(self) -> None:
        return None


def _write_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_hub(root: Path, *, label: str = "hub") -> Path:
    hub = root / label
    _write_file(hub / "dist" / "src" / "cli.js", "console.log('cli');\n")
    _write_file(hub / "dist" / "z.txt", "z\n")
    for dep in compat.ENUMERATED_OFF_DIST_DEPS:
        _write_file(hub / "node_modules" / dep / "package.json", f'{{"name":"{dep}"}}\n')
        _write_file(hub / "node_modules" / dep / "index.js", f"module.exports = '{dep}';\n")
    return hub


def _env(hub: Path | None = None, **overrides: str) -> dict[str, str]:
    environ = {compat.AUTOMATION_ENV: "1"}
    if hub is not None:
        environ[compat.HUB_PATH_ENV] = str(hub)
    environ.update(overrides)
    return environ


def _pin_digest(monkeypatch: pytest.MonkeyPatch, hub: Path) -> str:
    digest = compat.compute_exec_digest(hub)
    assert digest not in {None, "HUB_NOT_BUILT"}
    assert isinstance(digest, str)
    monkeypatch.setattr(compat, "PINNED_HUB_EXEC_DIGEST", digest)
    return digest


def _tools_payload(*names: str) -> dict[str, Any]:
    return {"data": [{"name": name, "description": "", "inputSchema": {}} for name in names]}


def _allow_cdp(monkeypatch: pytest.MonkeyPatch, seen_urls: list[str] | None = None) -> None:
    def fake_urlopen(url, *, timeout):
        assert timeout == compat.CDP_PREFLIGHT_TIMEOUT_SECONDS
        if seen_urls is not None:
            seen_urls.append(url)
        return _FakeCdpResponse(status=200)

    monkeypatch.setattr(automation.urllib.request, "urlopen", fake_urlopen)


def _install_dispatch_spy(
    monkeypatch: pytest.MonkeyPatch,
    *,
    tool_names: tuple[str, ...],
    dispatch_response: Any | None = None,
) -> list[tuple[list[str], dict[str, Any]]]:
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def fake_run(args, **kwargs):
        args_list = list(args)
        calls.append((args_list, kwargs))
        if args_list == ["mcp:tools", "--json"]:
            return _tools_payload(*tool_names)
        if dispatch_response is None:
            return {"ok": True, "status": "ok"}
        if isinstance(dispatch_response, BaseException):
            raise dispatch_response
        return dispatch_response

    monkeypatch.setattr(automation, "run_hub_command", fake_run)
    return calls


def _dispatch_calls(calls: list[tuple[list[str], dict[str, Any]]]) -> list[tuple[list[str], dict[str, Any]]]:
    return [call for call in calls if call[0] != ["mcp:tools", "--json"]]


def test_part_a_empty_dist_precedes_missing_dependency_and_valid_digest_still_matches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    empty_hub = tmp_path / "empty"
    (empty_hub / "dist").mkdir(parents=True)
    assert compat.compute_exec_digest(empty_hub) == "HUB_NOT_BUILT"

    hub = _make_hub(tmp_path, label="normal")
    digest = _pin_digest(monkeypatch, hub)
    assert len(digest) == 64
    assert compat.digest_matches(hub) == ("ok", None)


@pytest.mark.parametrize("pin", ["UNSET", "deadbeef", "Z" * 64, "A" * 64])
def test_part_a_invalid_pin_short_circuits_before_digest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    pin: str,
) -> None:
    calls: list[str] = []

    def forbidden_compute(_hub: Path):
        calls.append("compute")
        pytest.fail("compute_exec_digest must not run for an invalid pin")

    monkeypatch.setattr(compat, "PINNED_HUB_EXEC_DIGEST", pin)
    monkeypatch.setattr(compat, "compute_exec_digest", forbidden_compute)

    assert compat.digest_matches(tmp_path) == ("mismatch", None)
    assert calls == []


def test_part_a_cdp_loopback_allowlist_blocks_nonloopback_without_opt_in(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hub = _make_hub(tmp_path)
    _pin_digest(monkeypatch, hub)
    calls = _install_dispatch_spy(monkeypatch, tool_names=(PAGEFUL_OP,))
    monkeypatch.setattr(automation.urllib.request, "urlopen", lambda *_args, **_kwargs: pytest.fail("CDP must not be probed"))

    result = automation.web_ai_hub_gate(
        PAGEFUL_OP,
        environ=_env(hub, **{compat.CDP_HOST_ENV: "10.0.0.5", compat.CDP_PORT_ENV: "9222"}),
    )

    assert result == {"status": "not_implemented", "reason": "trusted CDP endpoint not configured"}
    assert calls == [(["mcp:tools", "--json"], {"hub_path": hub, "timeout": 15})]

    _allow_cdp(monkeypatch)
    result = automation.web_ai_hub_gate(
        PAGEFUL_OP,
        environ=_env(
            hub,
            **{
                compat.CDP_HOST_ENV: "10.0.0.5",
                compat.CDP_PORT_ENV: "9222",
                compat.CDP_ALLOW_NONLOOPBACK_ENV: "1",
            },
        ),
    )
    assert result["status"] == "ready"


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "::1"])
def test_part_a_cdp_loopback_hosts_do_not_require_nonloopback_opt_in(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    host: str,
) -> None:
    hub = _make_hub(tmp_path)
    _pin_digest(monkeypatch, hub)
    _install_dispatch_spy(monkeypatch, tool_names=(PAGEFUL_OP,))
    _allow_cdp(monkeypatch)

    result = automation.web_ai_hub_gate(
        PAGEFUL_OP,
        environ=_env(hub, **{compat.CDP_HOST_ENV: host, compat.CDP_PORT_ENV: "9222"}),
    )

    assert result["status"] == "ready"
    assert result["cdp_endpoint_verified"] is True


def test_dispatch_gate_failures_and_non_dispatchable_operation_do_not_spawn_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hub = _make_hub(tmp_path)
    _pin_digest(monkeypatch, hub)
    calls = _install_dispatch_spy(monkeypatch, tool_names=(PAGEFUL_OP,))

    assert automation.dispatch_web_ai(LAUNCH_SAFE_OP, {"task_id": "task_x"}, environ={}) == {
        "status": "not_implemented",
        "reason": "web-ai automation opt-in disabled",
    }
    assert calls == []

    result = automation.dispatch_web_ai(PAGEFUL_OP, {"profile": "chatgpt", "prompt": "hi"}, environ=_env(hub))
    assert result == {"status": "not_implemented", "reason": "trusted CDP endpoint not configured"}
    assert _dispatch_calls(calls) == []

    calls.clear()
    monkeypatch.setattr(compat, "PINNED_HUB_EXEC_DIGEST", "0" * 64)
    result = automation.dispatch_web_ai(LAUNCH_SAFE_OP, {"task_id": "task_x"}, environ=_env(hub))
    assert result == {
        "status": "not_implemented",
        "reason": "hub exec closure unpinned/mismatch — manual review & re-pin required",
    }
    assert calls == []

    _pin_digest(monkeypatch, hub)
    calls.clear()
    result = automation.dispatch_web_ai(LAUNCH_SAFE_OP, {"task_id": "task_x"}, environ=_env(hub))
    assert result == {"status": "not_implemented", "reason": "hub capability absent"}
    assert calls == [(["mcp:tools", "--json"], {"hub_path": hub, "timeout": 15})]

    calls.clear()
    calls = _install_dispatch_spy(monkeypatch, tool_names=(NON_DISPATCHABLE_PAGEFUL_OP,))
    _allow_cdp(monkeypatch)
    result = automation.dispatch_web_ai(
        NON_DISPATCHABLE_PAGEFUL_OP,
        {"profile": "chatgpt", "prompt": "hi"},
        environ=_env(hub, **{compat.CDP_PORT_ENV: "9222"}),
    )
    assert result == {"status": "not_implemented", "reason": "operation not dispatchable in D10-02"}
    assert _dispatch_calls(calls) == []


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"profile": "chatgpt"},
        {"prompt": "hi"},
        {"profile": "chatgpt", "prompt": ""},
        {"profile": "chatgpt", "prompt": "--help"},
        {"profile": "chatgpt", "prompt": "--no-redact"},
        {"profile": "chatgpt", "prompt": "--prompt=x"},
        {"profile": "--no-redact", "prompt": "hi"},
        {"profile": "--help", "prompt": "hi"},
        {"profile": "-x", "prompt": "hi"},
        {"profile": "BadProfile", "prompt": "hi"},
        {"profile": "chatgpt", "prompt": "x" * (compat.PROMPT_MAX_CHARS + 1)},
        {"profile": "chatgpt", "prompt": "hi\x00"},
        {"profile": "chatgpt", "prompt": "hi\x1f"},
        {"profile": "chatgpt", "prompt": "hi", "model": "x"},
        {"profile": "chatgpt", "prompt": "hi", "url": "https://example.com"},
        {"profile": "chatgpt", "prompt": "hi", "cdp_port": "9222"},
        {"profile": "chatgpt", "prompt": "hi", "confirmed": True},
        {"profile": "chatgpt", "prompt": "hi", "WAH_FOO": "1"},
        {"profile": "chatgpt", "prompt": "hi", "--no-redact": True},
        {"profile": "chatgpt", "prompt": "hi", "reuse_conversation": "true"},
        {"profile": "chatgpt", "prompt": "hi", "response_timeout_ms": True},
    ],
)
def test_send_prompt_validate_request_rejects_injection_unknowns_and_bad_shapes(params: dict[str, Any]) -> None:
    argv, err = compat.validate_request(PAGEFUL_OP, params)
    assert argv is None
    assert err is not None
    assert err.startswith("request rejected: ")


def test_send_prompt_validate_request_allows_internal_hyphen_and_clamps_timeout() -> None:
    argv, err = compat.validate_request(
        "webai_gemini_send_prompt",
        {
            "profile": "gemini-9225",
            "prompt": "hello\n\tworld",
            "response_timeout_ms": 500,
            "reuse_conversation": True,
        },
    )
    assert err is None
    assert argv == [
        "webai:gemini:send-prompt",
        "--profile",
        "gemini-9225",
        "--prompt",
        "hello\n\tworld",
        "--response-timeout-ms",
        "1000",
        "--reuse-conversation",
        "--output-json",
    ]

    argv, err = compat.validate_request(
        PAGEFUL_OP,
        {"profile": "chatgpt", "prompt": "hi", "response_timeout_ms": 999999},
    )
    assert err is None
    assert argv is not None
    assert argv[-3:] == ["--response-timeout-ms", "180000", "--output-json"]


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"task_id": "bad"},
        {"task_id": "task_"},
        {"task_id": "task_BAD"},
        {"task_id": "task_ok", "prompt": "not allowed"},
    ],
)
def test_task_status_validate_request_rejects_bad_or_extra_params(params: dict[str, Any]) -> None:
    argv, err = compat.validate_request(LAUNCH_SAFE_OP, params)
    assert argv is None
    assert err is not None
    assert err.startswith("request rejected: ")


def test_dispatch_send_prompt_argv_env_and_timeout_are_fixed_list_form(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hub = _make_hub(tmp_path)
    _pin_digest(monkeypatch, hub)
    calls = _install_dispatch_spy(monkeypatch, tool_names=(PAGEFUL_OP,))
    _allow_cdp(monkeypatch)

    result = automation.dispatch_web_ai(
        PAGEFUL_OP,
        {
            "profile": "gemini-9225",
            "prompt": "hello world",
            "response_timeout_ms": 500,
            "reuse_conversation": True,
        },
        environ=_env(
            hub,
            **{
                compat.CDP_HOST_ENV: "127.0.0.1",
                compat.CDP_PORT_ENV: "9222",
                "WAH_BROWSER_EXECUTABLE": "/usr/bin/chrome",
                "WAH_AUTO_CONFIRM": "1",
                "confirmed": "1",
            },
        ),
    )

    assert result == {"ok": True, "status": "ok"}
    dispatch = _dispatch_calls(calls)
    assert len(dispatch) == 1
    argv, kwargs = dispatch[0]
    assert argv == [
        "webai:chatgpt:send-prompt",
        "--profile",
        "gemini-9225",
        "--prompt",
        "hello world",
        "--response-timeout-ms",
        "1000",
        "--reuse-conversation",
        "--output-json",
    ]
    assert argv[argv.index("--prompt") + 1] == "hello world"
    assert argv[-1] == "--output-json"
    assert "--model" not in argv
    assert kwargs["hub_path"] == hub
    assert kwargs["timeout"] == compat.AUTOMATION_TIMEOUT_SECONDS == 200
    assert kwargs["env"]["WAH_CDP_HOST"] == "127.0.0.1"
    assert kwargs["env"]["WAH_CDP_PORT"] == "9222"
    assert "WAH_BROWSER_EXECUTABLE" not in kwargs["env"]
    assert "WAH_AUTO_CONFIRM" not in kwargs["env"]
    assert "confirmed" not in kwargs["env"]


def test_dispatch_task_status_argv_and_launch_safe_env_have_no_cdp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hub = _make_hub(tmp_path)
    _pin_digest(monkeypatch, hub)
    calls = _install_dispatch_spy(monkeypatch, tool_names=(LAUNCH_SAFE_OP,))
    monkeypatch.setattr(automation.urllib.request, "urlopen", lambda *_args, **_kwargs: pytest.fail("CDP should be skipped"))

    result = automation.dispatch_web_ai(
        LAUNCH_SAFE_OP,
        {"task_id": "task_x"},
        environ=_env(hub, **{compat.CDP_HOST_ENV: "127.0.0.1", compat.CDP_PORT_ENV: "9222"}),
    )

    assert result == {"ok": True, "status": "ok"}
    dispatch = _dispatch_calls(calls)
    assert len(dispatch) == 1
    argv, kwargs = dispatch[0]
    assert argv == ["webai:task-status", "--task-id", "task_x", "--output-json"]
    assert "WAH_CDP_HOST" not in kwargs["env"]
    assert "WAH_CDP_PORT" not in kwargs["env"]


def test_dispatch_invalid_request_does_not_spawn_after_ready_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hub = _make_hub(tmp_path)
    _pin_digest(monkeypatch, hub)
    calls = _install_dispatch_spy(monkeypatch, tool_names=(LAUNCH_SAFE_OP,))

    result = automation.dispatch_web_ai(LAUNCH_SAFE_OP, {"task_id": "task_ok", "prompt": "bad"}, environ=_env(hub))

    assert result["status"] == "not_implemented"
    assert result["reason"].startswith("request rejected: ")
    assert _dispatch_calls(calls) == []


def test_redact_hub_response_allowlists_keys_and_strictly_redacts_sensitive_text() -> None:
    dirty = {
        "ok": True,
        "response_text": (
            "sid=abc123456; bearer supersecret api_key=sekret "
            "eyJabc.def.ghi /home/l1u user@example.com"
        ),
        "summary": "x" * (compat.RESPONSE_TEXT_MAX_CHARS + 10),
        "message": "password: hunter2",
        "chat_url": "https://chatgpt.com/share/abc123tokenlong?leak=1#frag",
        "conversation_id": "https://chatgpt.com/c/secret",
        "task_id": "task_ok",
        "error_type": "timeout",
        "__proto__": "polluted",
    }

    result = automation.redact_hub_response(dirty)

    assert set(result) <= compat.RESPONSE_KEY_ALLOWLIST
    assert result["status"] == "ok"
    assert result["task_id"] == "task_ok"
    assert "chat_url" not in result
    assert "conversation_id" not in result
    assert "error_type" not in result
    assert "__proto__" not in result
    assert "supersecret" not in result["response_text"]
    assert "sekret" not in result["response_text"]
    assert "eyJabc" not in result["response_text"]
    assert "/home/l1u" not in result["response_text"]
    assert "user@example.com" not in result["response_text"]
    assert "[redacted]" in result["response_text"]
    assert result["message"] == "password: [redacted]"
    assert result["summary"] == "[omitted]"

    clean = automation.redact_hub_response(
        {
            "ok": True,
            "chat_url": "https://chatgpt.com/c/clean-room?token=drop#fragment",
            "conversation_id": "Conversation_123-abc",
        }
    )
    assert clean["chat_url"] == "https://chatgpt.com/c/clean-room"
    assert clean["conversation_id"] == "Conversation_123-abc"

    assert "chat_url" not in automation.redact_hub_response({"ok": True, "chat_url": "https://evil.com/x"})
    assert "chat_url" not in automation.redact_hub_response(
        {"ok": True, "chat_url": "https://claude.ai/c/abcdef1234567890"}
    )


def test_approval_required_is_transparently_redacted_without_auto_confirm(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hub = _make_hub(tmp_path)
    _pin_digest(monkeypatch, hub)
    calls = _install_dispatch_spy(
        monkeypatch,
        tool_names=(PAGEFUL_OP,),
        dispatch_response={
            "status": "approval_required",
            "errorCode": "POLICY_APPROVAL_REQUIRED",
            "reason": "need confirm",
            "requiredFor": "send",
            "required_for": "send_again",
        },
    )
    _allow_cdp(monkeypatch)

    result = automation.dispatch_web_ai(
        PAGEFUL_OP,
        {"profile": "chatgpt", "prompt": "hi"},
        environ=_env(
            hub,
            **{
                compat.CDP_PORT_ENV: "9222",
                "WAH_AUTO_CONFIRM": "1",
                "confirmed": "1",
            },
        ),
    )

    assert result == {
        "status": "approval_required",
        "errorCode": "POLICY_APPROVAL_REQUIRED",
        "reason": "need confirm",
        "requiredFor": "send",
        "required_for": "send_again",
    }
    dispatch = _dispatch_calls(calls)
    assert len(dispatch) == 1
    assert "WAH_AUTO_CONFIRM" not in dispatch[0][1]["env"]
    assert "confirmed" not in dispatch[0][1]["env"]


def test_dispatch_recomputes_digest_immediately_before_spawn_and_blocks_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hub = _make_hub(tmp_path)
    _pin_digest(monkeypatch, hub)
    calls = _install_dispatch_spy(monkeypatch, tool_names=(LAUNCH_SAFE_OP,))
    digest_calls: list[Path] = []

    def flapping_digest(hub_path: Path):
        digest_calls.append(hub_path)
        if len(digest_calls) == 1:
            return ("ok", None)
        return ("mismatch", None)

    monkeypatch.setattr(compat, "digest_matches", flapping_digest)

    result = automation.dispatch_web_ai(LAUNCH_SAFE_OP, {"task_id": "task_x"}, environ=_env(hub))

    assert result == {
        "status": "not_implemented",
        "reason": "hub exec closure unpinned/mismatch — manual review & re-pin required",
    }
    assert digest_calls == [hub, hub]
    assert calls == [(["mcp:tools", "--json"], {"hub_path": hub, "timeout": 15})]


def test_dispatch_uses_entry_environ_snapshot_for_gate_path_digest_and_env_injection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hub = _make_hub(tmp_path)
    external_env = _env(hub, **{compat.CDP_HOST_ENV: "127.0.0.1", compat.CDP_PORT_ENV: "9222"})
    calls = _install_dispatch_spy(monkeypatch, tool_names=(PAGEFUL_OP,))

    def fake_gate(_operation: str, *, environ):
        assert environ[compat.CDP_PORT_ENV] == "9222"
        external_env[compat.CDP_PORT_ENV] = "9333"
        external_env[compat.HUB_PATH_ENV] = str(tmp_path / "other")
        return {
            "status": "ready",
            "operation": PAGEFUL_OP,
            "classification": "pageful",
            "cdp_endpoint_verified": True,
        }

    monkeypatch.setattr(automation, "web_ai_hub_gate", fake_gate)
    monkeypatch.setattr(compat, "digest_matches", lambda hub_path: ("ok", None) if hub_path == hub else ("mismatch", None))

    result = automation.dispatch_web_ai(PAGEFUL_OP, {"profile": "chatgpt", "prompt": "hi"}, environ=external_env)

    assert result == {"ok": True, "status": "ok"}
    dispatch = _dispatch_calls(calls)
    assert len(dispatch) == 1
    _, kwargs = dispatch[0]
    assert kwargs["hub_path"] == hub
    assert kwargs["env"]["WAH_CDP_PORT"] == "9222"


def test_dispatch_and_redaction_failure_paths_never_raise(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hub = _make_hub(tmp_path)
    _pin_digest(monkeypatch, hub)

    calls = _install_dispatch_spy(
        monkeypatch,
        tool_names=(LAUNCH_SAFE_OP,),
        dispatch_response=RuntimeError("boom /home/l1u token=secret"),
    )
    result = automation.dispatch_web_ai(LAUNCH_SAFE_OP, {"task_id": "task_x"}, environ=_env(hub))
    assert result["status"] == "not_implemented"
    assert "/home/l1u" not in result["reason"]
    assert "secret" not in result["reason"]
    assert len(_dispatch_calls(calls)) == 1

    calls = _install_dispatch_spy(monkeypatch, tool_names=(LAUNCH_SAFE_OP,), dispatch_response=["not", "dict"])
    assert automation.dispatch_web_ai(LAUNCH_SAFE_OP, {"task_id": "task_x"}, environ=_env(hub)) == {
        "status": "not_implemented",
        "reason": "hub response not an object",
    }

    assert automation.redact_hub_response({}) == {"status": "error"}
    assert automation.redact_hub_response({"ok": True}) == {"ok": True, "status": "ok"}
    assert automation.redact_hub_response({"ok": False}) == {"ok": False, "status": "error"}


def test_dispatch_hub_not_built_from_second_digest_returns_hub_not_built(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hub = _make_hub(tmp_path)
    _pin_digest(monkeypatch, hub)
    calls = _install_dispatch_spy(monkeypatch, tool_names=(LAUNCH_SAFE_OP,))
    digest_calls = 0

    def second_not_built(_hub_path: Path):
        nonlocal digest_calls
        digest_calls += 1
        return ("ok", None) if digest_calls == 1 else ("not_built", None)

    monkeypatch.setattr(compat, "digest_matches", second_not_built)

    result = automation.dispatch_web_ai(LAUNCH_SAFE_OP, {"task_id": "task_x"}, environ=_env(hub))

    assert result == {"status": "HUB_NOT_BUILT"}
    assert _dispatch_calls(calls) == []

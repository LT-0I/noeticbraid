# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import os
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


UPLOAD_OP = "webai_chatgpt_upload_and_query"
CLAUDE_UPLOAD_OP = "webai_claude_upload_and_query"
DEEP_RESEARCH_OP = "webai_chatgpt_deep_research"
GEMINI_DEEP_RESEARCH_OP = "webai_gemini_deep_research"
CHATGPT_CONVERSATION_OP = "webai_chatgpt_conversation_manage"
CLAUDE_CONVERSATION_OP = "webai_claude_conversation_manage"
GEMINI_CONVERSATION_OP = "webai_gemini_conversation_manage"
CHATGPT_WORKSPACE_OP = "webai_chatgpt_workspace"
CLAUDE_WORKSPACE_OP = "webai_claude_workspace"
GEMINI_WORKSPACE_OP = "webai_gemini_workspace"
NON_DISPATCHABLE_PAGEFUL_OP = "browser_read"


class _FakeCdpResponse:
    def __init__(self, *, status: int = 200, body: bytes = b'{"Browser":"Chrome"}') -> None:
        self.status = status
        self._body = body

    def read(self) -> bytes:
        return self._body

    def close(self) -> None:
        return None


def _write_file(path: Path, text: str = "x\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


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


def _regular_files(tmp_path: Path, count: int) -> list[str]:
    return [str(_write_file(tmp_path / f"file_{index}.txt")) for index in range(count)]


def _ready_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    op: str,
    params: dict[str, Any],
    *,
    response: Any | None = None,
) -> tuple[dict[str, Any], list[tuple[list[str], dict[str, Any]]], Path]:
    hub = _make_hub(tmp_path)
    _pin_digest(monkeypatch, hub)
    calls = _install_dispatch_spy(monkeypatch, tool_names=(op,), dispatch_response=response)
    _allow_cdp(monkeypatch)
    result = automation.dispatch_web_ai(
        op,
        params,
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
    return result, calls, hub


def test_d10_03_constants_are_closed_and_mapped() -> None:
    assert compat.QUERY_MAX_CHARS == compat.PROMPT_MAX_CHARS
    assert compat.UPLOAD_FILE_MAX_BYTES == 33_554_432
    assert compat.UPLOAD_FILE_MAX_COUNT_CLAUDE == 3
    assert compat.UPLOAD_FILE_MAX_COUNT_DEFAULT == 3
    assert len(compat.DISPATCHABLE_D10_03) == 12
    assert compat.DISPATCHABLE == compat.DISPATCHABLE_D10_02 | compat.DISPATCHABLE_D10_03 | compat.DISPATCHABLE_D12

    assert compat.OP_TO_CLI_COMMAND[UPLOAD_OP] == "webai:chatgpt:upload-and-query"
    assert compat.OP_TO_CLI_COMMAND["webai_claude_deep_research"] == "webai:claude:deep-research"
    assert compat.OP_TO_CLI_COMMAND[CHATGPT_CONVERSATION_OP] == "webai:chatgpt:conversation-manage"
    assert compat.OP_TO_CLI_COMMAND[GEMINI_WORKSPACE_OP] == "webai:gemini:workspace"
    assert compat.CONVERSATION_ACTION_ALLOWLIST_BY_OP[CLAUDE_CONVERSATION_OP] == frozenset(
        {"search", "share"}
    )
    assert "gpts" in compat.WORKSPACE_SURFACE_ALLOWLIST[CHATGPT_WORKSPACE_OP]
    assert "notebooklm.google.com" in compat.CHAT_URL_HOST_ALLOWLIST


def test_gate_failures_and_allowed_but_non_dispatchable_ops_never_spawn_d10_03(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hub = _make_hub(tmp_path)
    _pin_digest(monkeypatch, hub)
    calls = _install_dispatch_spy(monkeypatch, tool_names=(UPLOAD_OP, NON_DISPATCHABLE_PAGEFUL_OP))
    _allow_cdp(monkeypatch)

    assert automation.dispatch_web_ai(UPLOAD_OP, {}, environ={}) == {
        "status": "not_implemented",
        "reason": "web-ai automation opt-in disabled",
    }
    assert calls == []

    result = automation.dispatch_web_ai(
        NON_DISPATCHABLE_PAGEFUL_OP,
        {},
        environ=_env(hub, **{compat.CDP_PORT_ENV: "9222"}),
    )
    assert result == {"status": "not_implemented", "reason": "operation not dispatchable in D10-02"}
    assert _dispatch_calls(calls) == []


def test_upload_and_query_accepts_three_files_with_prompt_flag_and_scrubbed_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    files = _regular_files(tmp_path, 3)
    result, calls, hub = _ready_dispatch(
        tmp_path,
        monkeypatch,
        UPLOAD_OP,
        {
            "profile": "chatgpt",
            "query": "read these",
            "files": files,
            "reuse_conversation": True,
            "response_timeout_ms": 999999,
        },
    )

    assert result == {"ok": True, "status": "ok"}
    dispatch = _dispatch_calls(calls)
    assert len(dispatch) == 1
    argv, kwargs = dispatch[0]
    assert argv == [
        "webai:chatgpt:upload-and-query",
        "--profile",
        "chatgpt",
        "--prompt",
        "read these",
        "--file",
        files[0],
        "--file",
        files[1],
        "--file",
        files[2],
        "--response-timeout-ms",
        "180000",
        "--reuse-conversation",
        "--output-json",
    ]
    assert "--query" not in argv
    assert "--model" not in argv
    assert argv[-1] == "--output-json"
    assert kwargs["hub_path"] == hub
    assert kwargs["timeout"] == compat.AUTOMATION_TIMEOUT_SECONDS == 200
    assert kwargs["env"]["WAH_CDP_HOST"] == "127.0.0.1"
    assert kwargs["env"]["WAH_CDP_PORT"] == "9222"
    assert "WAH_BROWSER_EXECUTABLE" not in kwargs["env"]
    assert "WAH_AUTO_CONFIRM" not in kwargs["env"]
    assert "confirmed" not in kwargs["env"]


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"profile": "chatgpt", "query": "q"},
        {"profile": "chatgpt", "files": []},
        {"profile": "chatgpt", "query": "q", "files": []},
        {"profile": "chatgpt", "query": "q", "files": "not-list"},
        {"profile": "chatgpt", "query": "", "files": ["/tmp/x"]},
        {"profile": "chatgpt", "query": "--help", "files": ["/tmp/x"]},
        {"profile": "chatgpt", "query": "q\x00", "files": ["/tmp/x"]},
        {"profile": "chatgpt", "query": "q\x1f", "files": ["/tmp/x"]},
        {"profile": "chatgpt", "query": "x" * (compat.QUERY_MAX_CHARS + 1), "files": ["/tmp/x"]},
        {"profile": "chatgpt", "query": "q", "files": ["/tmp/x"], "prompt": "bad"},
        {"profile": "chatgpt", "query": "q", "files": ["/tmp/x"], "confirmed": True},
        {"profile": "chatgpt", "query": "q", "files": ["/tmp/x"], "--file": "bad"},
        {"profile": "chatgpt", "query": "q", "files": ["/tmp/x"], "response_timeout_ms": True},
        {"profile": "chatgpt", "query": "q", "files": ["/tmp/x"], "reuse_conversation": "true"},
    ],
)
def test_upload_and_query_rejects_bad_shapes_and_unknowns(params: dict[str, Any]) -> None:
    argv, err = compat.validate_request(UPLOAD_OP, params)
    assert argv is None
    assert err is not None
    assert err.startswith("request rejected: ")


def test_upload_file_path_governance_rejects_adversarial_paths(tmp_path: Path) -> None:
    good = _write_file(tmp_path / "good.txt")
    comma = _write_file(tmp_path / "bad,name.txt")
    non_ascii = _write_file(tmp_path / "café.txt")
    symlink = tmp_path / "link.txt"
    symlink.symlink_to(good)
    directory = tmp_path / "directory"
    directory.mkdir()
    fifo = tmp_path / "fifo"
    os.mkfifo(fifo)
    huge = tmp_path / "huge.bin"
    with huge.open("wb") as handle:
        handle.truncate(compat.UPLOAD_FILE_MAX_BYTES + 1)

    bad_files = [
        "relative.txt",
        "--no-redact",
        str(tmp_path / "missing.txt"),
        str(tmp_path / "a" / ".." / "good.txt"),
        str(symlink),
        str(directory),
        str(fifo),
        str(huge),
        str(comma),
        str(non_ascii),
        str(good) + "\x00",
        str(good) + "\n",
    ]
    for bad in bad_files:
        argv, err = compat.validate_request(
            UPLOAD_OP,
            {"profile": "chatgpt", "query": "q", "files": [bad]},
        )
        assert argv is None, bad
        assert err == "request rejected: invalid files"


def test_upload_file_count_cap_is_three_for_all_providers(tmp_path: Path) -> None:
    files = _regular_files(tmp_path, 4)
    for op in (UPLOAD_OP, CLAUDE_UPLOAD_OP, "webai_gemini_upload_and_query"):
        argv, err = compat.validate_request(op, {"profile": "p", "query": "q", "files": files})
        assert argv is None
        assert err == "request rejected: invalid files"


def test_deep_research_rejects_confirmed_and_uses_prompt_timeout_clamp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    argv, err = compat.validate_request(
        DEEP_RESEARCH_OP,
        {"profile": "chatgpt", "query": "research", "response_timeout_ms": 500},
    )
    assert err is None
    assert argv == [
        "webai:chatgpt:deep-research",
        "--profile",
        "chatgpt",
        "--prompt",
        "research",
        "--response-timeout-ms",
        "1000",
        "--output-json",
    ]

    for extra in ("confirmed", "files", "action"):
        bad_argv, bad_err = compat.validate_request(
            DEEP_RESEARCH_OP,
            {"profile": "chatgpt", "query": "research", extra: True},
        )
        assert bad_argv is None
        assert bad_err == "request rejected: unsupported parameter"

    response = {"task_id": "task_123_ab", "status": "queued"}
    result, calls, _hub = _ready_dispatch(
        tmp_path,
        monkeypatch,
        DEEP_RESEARCH_OP,
        {"profile": "chatgpt", "query": "research", "response_timeout_ms": 999999},
        response=response,
    )
    dispatch = _dispatch_calls(calls)
    assert result == response
    assert dispatch[0][0][-3:] == ["--response-timeout-ms", "180000", "--output-json"]
    assert dispatch[0][1]["timeout"] == 200


def test_gemini_deep_research_sensitive_guard_is_redacted_and_not_auto_confirmed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, calls, _hub = _ready_dispatch(
        tmp_path,
        monkeypatch,
        GEMINI_DEEP_RESEARCH_OP,
        {"profile": "gemini", "query": "sensitive"},
        response={
            "ok": False,
            "status": "sensitiveContentGuard",
            "errorCode": "SENSITIVE_CONTENT_GUARD",
            "message": "confirmed required token=secret /home/l1u",
        },
    )

    assert result["status"] == "sensitiveContentGuard"
    assert result["errorCode"] == "SENSITIVE_CONTENT_GUARD"
    assert "secret" not in result["message"]
    assert "/home/l1u" not in result["message"]
    dispatch = _dispatch_calls(calls)
    assert len(dispatch) == 1
    assert "WAH_AUTO_CONFIRM" not in dispatch[0][1]["env"]
    assert "confirmed" not in dispatch[0][1]["env"]


@pytest.mark.parametrize(
    ("op", "action"),
    [
        (CHATGPT_CONVERSATION_OP, "search"),
        (CHATGPT_CONVERSATION_OP, "menu_enumerate"),
        (CHATGPT_CONVERSATION_OP, "share"),
        (CLAUDE_CONVERSATION_OP, "search"),
        (CLAUDE_CONVERSATION_OP, "share"),
        (GEMINI_CONVERSATION_OP, "search"),
        (GEMINI_CONVERSATION_OP, "menu_enumerate"),
        (GEMINI_CONVERSATION_OP, "share"),
    ],
)
def test_conversation_manage_accepts_only_provider_allowlisted_actions(op: str, action: str) -> None:
    params: dict[str, Any] = {"profile": "p", "action": action}
    if action == "search":
        params["query"] = "needle"
    argv, err = compat.validate_request(op, params)
    assert err is None
    assert argv is not None
    assert argv[:4] == [compat.OP_TO_CLI_COMMAND[op], "--profile", "p", "--action"]
    assert argv[4] == action
    assert "--confirmed" not in argv
    if action == "search":
        assert "--query" in argv
    else:
        assert "--query" not in argv
    assert argv[-1] == "--output-json"


@pytest.mark.parametrize("action", ["delete", "rename", "archive", "sidebar_options", "navigate_settings"])
def test_conversation_manage_rejects_destructive_or_overlapping_actions_before_spawn(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    action: str,
) -> None:
    result, calls, _hub = _ready_dispatch(
        tmp_path,
        monkeypatch,
        CHATGPT_CONVERSATION_OP,
        {"profile": "chatgpt", "action": action},
    )
    assert result == {"status": "not_implemented", "reason": "request rejected: invalid action"}
    assert _dispatch_calls(calls) == []


@pytest.mark.parametrize("action", ["menu_enumerate", "Delete", "de lete", "--x", ""])
def test_conversation_manage_bad_or_provider_unsupported_actions_reject(action: str) -> None:
    argv, err = compat.validate_request(CLAUDE_CONVERSATION_OP, {"profile": "claude", "action": action})
    assert argv is None
    assert err == "request rejected: invalid action"


def test_conversation_manage_query_only_allowed_for_search_and_share_never_confirms(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    argv, err = compat.validate_request(
        CHATGPT_CONVERSATION_OP,
        {"profile": "chatgpt", "action": "share", "query": "bad"},
    )
    assert argv is None
    assert err == "request rejected: unsupported parameter for action"

    result, calls, _hub = _ready_dispatch(
        tmp_path,
        monkeypatch,
        CHATGPT_CONVERSATION_OP,
        {"profile": "chatgpt", "action": "share"},
        response={"dialog_opened": True, "conversationId": "abc123"},
    )
    assert result == {"dialog_opened": True, "conversationId": "abc123", "status": "error"}
    dispatch = _dispatch_calls(calls)
    assert "--confirmed" not in dispatch[0][0]
    assert "WAH_AUTO_CONFIRM" not in dispatch[0][1]["env"]


def test_workspace_accepts_only_provider_surfaces_and_never_emits_action(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for op, surface in (
        (CHATGPT_WORKSPACE_OP, "gpts"),
        (CLAUDE_WORKSPACE_OP, "skills"),
        (GEMINI_WORKSPACE_OP, "gems"),
    ):
        argv, err = compat.validate_request(op, {"profile": "p", "surface": surface})
        assert err is None
        assert argv == [compat.OP_TO_CLI_COMMAND[op], "--profile", "p", "--surface", surface, "--output-json"]
        assert "--action" not in argv

    argv, err = compat.validate_request(CLAUDE_WORKSPACE_OP, {"profile": "p", "surface": "gpts"})
    assert argv is None
    assert err == "request rejected: invalid surface"

    argv, err = compat.validate_request(
        CHATGPT_WORKSPACE_OP,
        {"profile": "p", "surface": "gpts", "action": "read"},
    )
    assert argv is None
    assert err == "request rejected: unsupported parameter"

    result, calls, _hub = _ready_dispatch(
        tmp_path,
        monkeypatch,
        CHATGPT_WORKSPACE_OP,
        {"profile": "chatgpt", "surface": "gpts"},
        response={"surface": "gpts", "url": "https://chatgpt.com/gpts", "summary": "3 GPTs"},
    )
    assert result == {"surface": "gpts", "url": "https://chatgpt.com/gpts", "summary": "3 GPTs", "status": "error"}
    assert "--action" not in _dispatch_calls(calls)[0][0]


def test_url_and_new_response_keys_are_strictly_allowlisted_and_redacted() -> None:
    result = automation.redact_hub_response(
        {
            "ok": True,
            "status": "ok",
            "url": "https://notebooklm.google.com/audio_overview?token=secret#frag",
            "chat_url": "https://claude.ai/new",
            "attachment_names": ["/home/alice/secret.pdf", "report.docx"],
            "files_in_chip": ["ghp" + "_" + "a" * 16],
            "results": ["plain", "AKIA" + "A" * 16],
            "items": ["sessionid=abc123"],
            "files_uploaded_count": 2,
            "results_count": 3,
            "dialog_opened": True,
            "action": "share",
            "surface": "audio_overview",
            "conversationId": "Conversation_123",
            "error_type": "must_drop",
        }
    )

    assert result["status"] == "ok"
    assert result["url"] == "https://notebooklm.google.com/audio_overview"
    assert result["chat_url"] == "https://claude.ai/new"
    assert result["attachment_names"][0] == "[path]"
    assert result["files_in_chip"] == ["[redacted]"]
    assert result["results"] == ["plain", "[redacted]"]
    assert result["items"] == ["sessionid=[redacted]"]
    assert result["files_uploaded_count"] == 2
    assert result["results_count"] == 3
    assert result["dialog_opened"] is True
    assert result["conversationId"] == "Conversation_123"
    assert "error_type" not in result
    assert "url" not in automation.redact_hub_response({"ok": True, "url": "https://evil.com/x"})
    assert "url" not in automation.redact_hub_response({"ok": True, "url": "https://chatgpt.com/share/secret"})
    assert "results" not in automation.redact_hub_response({"ok": True, "results": [{"title": "bad"}]})
    assert "items" not in automation.redact_hub_response({"ok": True, "items": ["x"] * 65})
    assert "dialog_opened" not in automation.redact_hub_response({"ok": True, "dialog_opened": 1})
    assert "files_uploaded_count" not in automation.redact_hub_response({"ok": True, "files_uploaded_count": True})
    assert "conversationId" not in automation.redact_hub_response({"ok": True, "conversationId": "https://x"})


def test_folded_minor_secret_patterns_omit_high_risk_text_and_username_is_word_anchored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider_prefix_values = [
        "AKIA" + "A" * 16,
        "ASIA" + "A" * 16,
        "AIza" + "a" * 35,
        "ghp" + "_" + "a" * 16,
        "sessionid=abc123",
    ]
    for value in provider_prefix_values:
        result = automation.redact_hub_response({"ok": True, "response_text": f"prefix {value} suffix"})
        assert value not in result["response_text"]
        assert "[redacted]" in result["response_text"]

    high_risk_values = [
        "a" * 40,
        "A" * 40,
    ]
    for value in high_risk_values:
        result = automation.redact_hub_response({"ok": True, "response_text": f"prefix {value} suffix"})
        assert result["response_text"] == "[omitted]"

    monkeypatch.setenv("USER", "al")
    assert automation._strict_redact("alpha al pals") == "alpha al pals"

    monkeypatch.setenv("USER", "alice")
    assert automation._strict_redact("alice pals malice") == "[user] pals malice"


def test_second_digest_and_environ_snapshot_apply_to_d10_03_pageful_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hub = _make_hub(tmp_path)
    external_env = _env(hub, **{compat.CDP_HOST_ENV: "127.0.0.1", compat.CDP_PORT_ENV: "9222"})
    calls = _install_dispatch_spy(monkeypatch, tool_names=(UPLOAD_OP,))
    files = _regular_files(tmp_path, 1)

    def fake_gate(_operation: str, *, environ):
        assert environ[compat.CDP_PORT_ENV] == "9222"
        external_env[compat.CDP_PORT_ENV] = "9333"
        external_env[compat.HUB_PATH_ENV] = str(tmp_path / "other")
        return {
            "status": "ready",
            "operation": UPLOAD_OP,
            "classification": "pageful",
            "cdp_endpoint_verified": True,
        }

    monkeypatch.setattr(automation, "web_ai_hub_gate", fake_gate)
    monkeypatch.setattr(compat, "digest_matches", lambda hub_path: ("ok", None) if hub_path == hub else ("mismatch", None))

    result = automation.dispatch_web_ai(
        UPLOAD_OP,
        {"profile": "chatgpt", "query": "q", "files": files},
        environ=external_env,
    )

    assert result == {"ok": True, "status": "ok"}
    dispatch = _dispatch_calls(calls)
    assert len(dispatch) == 1
    assert dispatch[0][1]["hub_path"] == hub
    assert dispatch[0][1]["env"]["WAH_CDP_PORT"] == "9222"

    digest_calls = 0

    def second_mismatch(_hub_path: Path):
        nonlocal digest_calls
        digest_calls += 1
        return ("ok", None) if digest_calls == 1 else ("mismatch", None)

    monkeypatch.setattr(automation, "web_ai_hub_gate", automation._web_ai_hub_gate)
    _pin_digest(monkeypatch, hub)
    monkeypatch.setattr(compat, "digest_matches", second_mismatch)
    _allow_cdp(monkeypatch)
    result = automation.dispatch_web_ai(
        UPLOAD_OP,
        {"profile": "chatgpt", "query": "q", "files": files},
        environ=_env(hub, **{compat.CDP_PORT_ENV: "9222"}),
    )
    assert result == {
        "status": "not_implemented",
        "reason": "hub exec closure unpinned/mismatch — manual review & re-pin required",
    }
    assert len(_dispatch_calls(calls)) == 1


def test_dispatch_and_redaction_failure_paths_never_raise_for_d10_03(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result, calls, _hub = _ready_dispatch(
        tmp_path,
        monkeypatch,
        DEEP_RESEARCH_OP,
        {"profile": "chatgpt", "query": "q"},
        response=RuntimeError("boom /home/l1u token=secret"),
    )
    assert result["status"] == "not_implemented"
    assert "/home/l1u" not in result["reason"]
    assert "secret" not in result["reason"]
    assert len(_dispatch_calls(calls)) == 1

    assert automation.redact_hub_response({"ok": True, "results": [object()]}) == {"ok": True, "status": "error"}

# SPDX-License-Identifier: Apache-2.0
"""Fail-closed compatibility constants and pure helpers for web-ai hub automation."""

from __future__ import annotations

import hashlib
import os
import re
import stat
from pathlib import Path

# Diagnostic reference only: git HEAD does not cover gitignored dist/ execution bytes.
PINNED_HUB_HEAD = "a641357"
# Diagnostic reference only: hub version strings are not trusted as a security gate.
MIN_HUB_PACKAGE_VERSION = "0.6.0"
PINNED_HUB_EXEC_DIGEST: str = "44da637f22dfbc578494bde43657267b42bf92585f44add06c82f8cd77ed9410"
ENUMERATED_OFF_DIST_DEPS = ("better-sqlite3", "playwright", "pino")

AUTOMATION_ENV = "NOETICBRAID_WEB_AI_HUB_AUTOMATION"
HUB_PATH_ENV = "NOETICBRAID_WEB_AI_HUB_PATH"
CDP_HOST_ENV = "NOETICBRAID_WEB_AI_HUB_CDP_HOST"
CDP_PORT_ENV = "NOETICBRAID_WEB_AI_HUB_CDP_PORT"
CDP_ALLOW_NONLOOPBACK_ENV = "NOETICBRAID_WEB_AI_HUB_CDP_ALLOW_NONLOOPBACK"
CDP_HOST_DEFAULT = "127.0.0.1"
CDP_LOOPBACK_HOSTS: frozenset[str] = frozenset({"127.0.0.1", "::1", "localhost"})
CDP_PREFLIGHT_TIMEOUT_SECONDS = 2.0

AUTOMATION_TIMEOUT_SECONDS = 200
GENERATE_AUTOMATION_TIMEOUT_SECONDS = 300
AUTOMATION_TIMEOUT_OVERRIDES: dict[str, int] = {
    "webai_chatgpt_generate_image": GENERATE_AUTOMATION_TIMEOUT_SECONDS,
    "webai_gemini_generate_image": GENERATE_AUTOMATION_TIMEOUT_SECONDS,
}
PROMPT_MAX_CHARS = 8192
QUERY_MAX_CHARS = PROMPT_MAX_CHARS
UPLOAD_FILE_MAX_BYTES = 33_554_432
UPLOAD_FILE_MAX_COUNT_CLAUDE = 3
UPLOAD_FILE_MAX_COUNT_DEFAULT = 3
ARTIFACT_FILE_MAX_BYTES = 268_435_456
RESPONSE_TEXT_MAX_CHARS = 16384
SCALAR_MAX_CHARS = 512

PROFILE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
TASK_ID_RE = re.compile(r"^task_[a-z0-9_]{1,128}$")
CHAT_URL_HOST_ALLOWLIST: frozenset[str] = frozenset(
    {"chatgpt.com", "claude.ai", "gemini.google.com", "notebooklm.google.com"}
)
RESPONSE_KEY_ALLOWLIST: frozenset[str] = frozenset(
    {
        "ok",
        "status",
        "errorCode",
        "error_code",
        "reason",
        "requiredFor",
        "required_for",
        "response_text",
        "completion_detected",
        "elapsed_ms",
        "wait_ms",
        "conversation_id",
        "chat_url",
        "model_used",
        "task_id",
        "progress_label",
        "reuse_conversation",
        "message",
        "summary",
        "dialog_opened",
        "files_uploaded_count",
        "results_count",
        "action",
        "surface",
        "url",
        "attachment_names",
        "files_in_chip",
        "results",
        "items",
        "conversationId",
        "path",
        "download_filename",
        "sha256",
        "size_bytes",
        "dimensions",
        "conversation_url",
    }
)

DISPATCHABLE_D10_02: frozenset[str] = frozenset(
    {
        "webai_chatgpt_send_prompt",
        "webai_claude_send_prompt",
        "webai_gemini_send_prompt",
        "webai_task_status",
    }
)
DISPATCHABLE_D10_03: frozenset[str] = frozenset(
    {
        "webai_chatgpt_upload_and_query",
        "webai_claude_upload_and_query",
        "webai_gemini_upload_and_query",
        "webai_chatgpt_deep_research",
        "webai_claude_deep_research",
        "webai_gemini_deep_research",
        "webai_chatgpt_conversation_manage",
        "webai_claude_conversation_manage",
        "webai_gemini_conversation_manage",
        "webai_chatgpt_workspace",
        "webai_claude_workspace",
        "webai_gemini_workspace",
    }
)
DISPATCHABLE_D12: frozenset[str] = frozenset(
    {
        "webai_chatgpt_generate_image",
        "webai_gemini_generate_image",
        "webai_gemini_generate_video",
        "webai_gemini_music_generate",
    }
)
DISPATCHABLE: frozenset[str] = DISPATCHABLE_D10_02 | DISPATCHABLE_D10_03 | DISPATCHABLE_D12
OP_TO_CLI_COMMAND: dict[str, str] = {
    "webai_chatgpt_send_prompt": "webai:chatgpt:send-prompt",
    "webai_claude_send_prompt": "webai:claude:send-prompt",
    "webai_gemini_send_prompt": "webai:gemini:send-prompt",
    "webai_task_status": "webai:task-status",
    "webai_chatgpt_upload_and_query": "webai:chatgpt:upload-and-query",
    "webai_claude_upload_and_query": "webai:claude:upload-and-query",
    "webai_gemini_upload_and_query": "webai:gemini:upload-and-query",
    "webai_chatgpt_deep_research": "webai:chatgpt:deep-research",
    "webai_claude_deep_research": "webai:claude:deep-research",
    "webai_gemini_deep_research": "webai:gemini:deep-research",
    "webai_chatgpt_conversation_manage": "webai:chatgpt:conversation-manage",
    "webai_claude_conversation_manage": "webai:claude:conversation-manage",
    "webai_gemini_conversation_manage": "webai:gemini:conversation-manage",
    "webai_chatgpt_workspace": "webai:chatgpt:workspace",
    "webai_claude_workspace": "webai:claude:workspace",
    "webai_gemini_workspace": "webai:gemini:workspace",
    "webai_chatgpt_generate_image": "webai:chatgpt:generate-image",
    "webai_gemini_generate_image": "webai:gemini:generate-image",
    "webai_gemini_generate_video": "webai:gemini:generate-video",
    "webai_gemini_music_generate": "webai:gemini:music:generate",
}

LAUNCH_SAFE_OPERATIONS: frozenset[str] = frozenset(
    {"webai_task_status", "browser_status", "browser_pages"}
)
PAGEFUL_OPERATIONS: frozenset[str] = frozenset(
    {
        "webai_chatgpt_send_prompt",
        "webai_claude_send_prompt",
        "webai_gemini_send_prompt",
        "webai_chatgpt_upload_and_query",
        "webai_claude_upload_and_query",
        "webai_gemini_upload_and_query",
        "webai_chatgpt_deep_research",
        "webai_claude_deep_research",
        "webai_gemini_deep_research",
        "webai_chatgpt_conversation_manage",
        "webai_claude_conversation_manage",
        "webai_gemini_conversation_manage",
        "webai_chatgpt_workspace",
        "webai_claude_workspace",
        "webai_gemini_workspace",
        "webai_chatgpt_generate_image",
        "webai_gemini_generate_image",
        "webai_gemini_generate_video",
        "webai_gemini_music_generate",
        "browser_read",
    }
)
ALLOWED_OPERATIONS: frozenset[str] = LAUNCH_SAFE_OPERATIONS | PAGEFUL_OPERATIONS

HARD_EXCLUDED_PREFIXES: frozenset[str] = frozenset(
    {
        "research_",
        "site_registry_",
        "capability_",
        "workflow_",
        "webai_chatgpt_generate_",
        "webai_claude_generate_",
        "webai_claude_design_",
        "webai_gemini_generate_",
        "webai_chatgpt_canvas",
        "webai_gemini_canvas",
        "webai_chatgpt_pulse",
    }
)
HARD_EXCLUDED_NAMES: frozenset[str] = frozenset(
    {
        "browser_launch",
        "browser_click",
        "browser_type",
        "browser_select",
        "browser_press",
        "browser_upload",
        "browser_run_recipe",
        "site_capture_map",
        "browser_capture_site_map",
        "browser_update_adapter_notes",
        "webai_gemini_music_download_track",
        "webai_gemini_music_task_status",
    }
)

_HUB_NOT_BUILT = "HUB_NOT_BUILT"
_PIN_FORMAT_RE = re.compile(r"^[0-9a-f]{64}$")
_SEND_PROMPT_KEYS = frozenset({"profile", "prompt", "reuse_conversation", "response_timeout_ms"})
_TASK_STATUS_KEYS = frozenset({"task_id"})
UPLOAD_FILE_KEYS = frozenset({"profile", "query", "files", "reuse_conversation", "response_timeout_ms"})
DEEP_RESEARCH_KEYS = frozenset({"profile", "query", "response_timeout_ms"})
CONVERSATION_MANAGE_KEYS = frozenset({"profile", "action", "query"})
WORKSPACE_KEYS = frozenset({"profile", "surface"})
GENERATE_ARTIFACT_KEYS = frozenset({"profile", "prompt"})
MUSIC_GENERATE_KEYS = frozenset({"profile", "prompt"})
CONVERSATION_ACTION_ALLOWLIST_BY_OP: dict[str, frozenset[str]] = {
    "webai_chatgpt_conversation_manage": frozenset({"search", "menu_enumerate", "share"}),
    "webai_claude_conversation_manage": frozenset({"search", "share"}),
    "webai_gemini_conversation_manage": frozenset({"search", "menu_enumerate", "share"}),
}
WORKSPACE_SURFACE_ALLOWLIST: dict[str, frozenset[str]] = {
    "webai_chatgpt_workspace": frozenset(
        {"projects", "gpts", "tasks", "apps", "memory", "personalization", "data_controls"}
    ),
    "webai_claude_workspace": frozenset({"projects", "appearance", "integrations", "skills", "style_presets"}),
    "webai_gemini_workspace": frozenset(
        {"gems", "scheduled", "study", "audio_overview", "workspace_integration", "connected_apps", "personalization"}
    ),
}
UPLOAD_PATH_RE = re.compile(r"^/[\x20-\x7E]+$")
ACTION_RE = re.compile(r"^[a-z][a-z_]{0,31}$")
SURFACE_RE = re.compile(r"^[a-z][a-z_]{0,31}$")
_COOKIE_PAIR_RE = re.compile(r"(?i)\b([A-Za-z0-9_.-]{1,64})=((?!\[redacted\];)[^\s;=]+);")
_BEARER_SECRET_RE = re.compile(r"(?i)\b(bearer)\s+(?!\[redacted\])[^\s,;]+")
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(token|api[_-]?key|password|credential|secret|authorization|auth)(\s*[:=]\s*)"
    r"(?!\[redacted\])[^\s,;]+"
)
_OAUTH_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(code|session|access_token|refresh_token)(\s*[:=]\s*)(?!\[redacted\])[^\s,;&]+"
)
_PROVIDER_PREFIX_TOKEN_RE = re.compile(
    r"(?i)\b(?:(?:sk|pk|rk|ghp|gho|github_pat|xox[baprs])[-_][A-Za-z0-9_-]{16,}|"
    r"(?:AKIA|ASIA)[A-Z0-9]{16}|AIza[0-9A-Za-z_-]{35})\b"
)
_LONG_B64_RUN_RE = re.compile(r"\b[A-Za-z0-9+/]{40,}={0,2}\b")
_LONG_HEX_RUN_RE = re.compile(r"\b[0-9a-fA-F]{40,}\b")
_COOKIE_NOSEMI_RE = re.compile(r"(?i)\b(sessionid|session_id|sid|auth_token|csrftoken)=(?!\[redacted\])[^\s;]+")
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")
_POSIX_ABSOLUTE_PATH_RE = re.compile(r"(?<![\w.-])/(?:[^\s\"'`<>|;:]+)")
_WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"[A-Za-z]:\\[^\s\"'`<>|;:]+")
_EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_CHAT_URL_FORBIDDEN_PATH_SEGMENT_RE = re.compile(r"(?i)(share|code|session|token|[0-9a-f]{16,}|access|auth)")
_CONVERSATION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def parse_opt_in(raw: str | None) -> bool:
    """Return True only for D9-style explicit automation opt-in values."""

    return (raw or "").strip().lower() in {"1", "true"}


def read_automation_enabled(environ) -> bool:
    """Read the web-ai automation opt-in from an environ-like mapping."""

    return parse_opt_in(environ.get(AUTOMATION_ENV))


def automation_timeout_for(op: str | None) -> int:
    """Return the bounded automation timeout for one operation."""

    return AUTOMATION_TIMEOUT_OVERRIDES.get(str(op or ""), AUTOMATION_TIMEOUT_SECONDS)


def compute_exec_digest(hub_root: Path) -> str | None:
    """Compute the deterministic hub execution-closure digest, or fail closed."""

    root = Path(hub_root)
    dist_dir = root / "dist"
    try:
        dist_stat = os.lstat(dist_dir)
    except FileNotFoundError:
        return _HUB_NOT_BUILT
    except OSError:
        return None
    if stat.S_ISLNK(dist_stat.st_mode) or not stat.S_ISDIR(dist_stat.st_mode):
        return None

    dist_files = _collect_regular_files(root, dist_dir)
    if dist_files is None:
        return None
    if not dist_files:
        return _HUB_NOT_BUILT

    dep_roots = []
    for dep_name in ENUMERATED_OFF_DIST_DEPS:
        dep_root = root / "node_modules" / dep_name
        if not _root_is_real_directory(dep_root):
            return None
        dep_roots.append(dep_root)

    all_relpaths = list(dist_files)
    for dep_root in dep_roots:
        dep_files = _collect_regular_files(root, dep_root)
        if dep_files is None:
            return None
        all_relpaths.extend(dep_files)

    try:
        hexdigests = []
        for relpath in sorted(all_relpaths):
            content = (root / relpath).read_bytes()
            file_hash = hashlib.sha256(relpath.encode() + b"\x00" + content).hexdigest()
            hexdigests.append(file_hash)
    except OSError:
        return None
    return hashlib.sha256("".join(hexdigests).encode()).hexdigest()


def digest_matches(hub_root: Path) -> tuple[str, str | None]:
    """Return a coarse fail-closed digest status for the hub root."""

    if not _PIN_FORMAT_RE.fullmatch(PINNED_HUB_EXEC_DIGEST):
        return ("mismatch", None)
    digest = compute_exec_digest(hub_root)
    if digest == _HUB_NOT_BUILT:
        return ("not_built", None)
    if digest is None:
        return ("uncomputable", None)
    if digest != PINNED_HUB_EXEC_DIGEST:
        return ("mismatch", None)
    return ("ok", None)


def is_allowed_operation(op) -> bool:
    """Return whether the operation is in the closed D10-01 allowlist."""

    return str(op or "") in ALLOWED_OPERATIONS


def is_pageful(op) -> bool:
    """Return whether the operation requires a trusted CDP preflight."""

    return str(op or "") in PAGEFUL_OPERATIONS


def is_launch_safe(op) -> bool:
    """Return whether the operation is launch-safe and skips CDP preflight."""

    return str(op or "") in LAUNCH_SAFE_OPERATIONS


def is_hard_excluded(op) -> bool:
    """Return whether the operation is explicitly hard-excluded by design."""

    value = str(op or "")
    return value not in DISPATCHABLE and (
        value in HARD_EXCLUDED_NAMES or any(value.startswith(prefix) for prefix in HARD_EXCLUDED_PREFIXES)
    )


def validate_request(op, params, *, download_dir: str | None = None) -> tuple[list[str] | None, str | None]:
    """Validate D10-02/D10-03 dispatch params and return a hub CLI argv tail."""

    operation = str(op or "")
    if operation not in DISPATCHABLE:
        return (None, "request rejected: operation not dispatchable")
    command = OP_TO_CLI_COMMAND.get(operation)
    if command is None:
        return (None, "request rejected: operation not dispatchable")
    if not isinstance(params, dict):
        return (None, "request rejected: params must be an object")

    if operation.endswith("_generate_image") or operation == "webai_gemini_generate_video":
        return _validate_generate_artifact(command, params, download_dir)
    if operation == "webai_gemini_music_generate":
        return _validate_music_generate(command, params)
    if operation == "webai_task_status":
        return _validate_task_status(command, params)
    if operation.endswith("_upload_and_query"):
        return _validate_upload_and_query(operation, command, params)
    if operation.endswith("_deep_research"):
        return _validate_deep_research(command, params)
    if operation.endswith("_conversation_manage"):
        return _validate_conversation_manage(operation, command, params)
    if operation.endswith("_workspace"):
        return _validate_workspace(operation, command, params)
    return _validate_send_prompt(command, params)


def _root_is_real_directory(path: Path) -> bool:
    try:
        path_stat = os.lstat(path)
    except OSError:
        return False
    return not stat.S_ISLNK(path_stat.st_mode) and stat.S_ISDIR(path_stat.st_mode)


def _collect_regular_files(hub_root: Path, root: Path) -> list[str] | None:
    relpaths: list[str] = []
    try:
        for current_dir, dirnames, filenames in os.walk(root, followlinks=False, onerror=_raise_walk_error):
            current_path = Path(current_dir)
            for dirname in dirnames:
                entry = current_path / dirname
                entry_stat = os.lstat(entry)
                if stat.S_ISLNK(entry_stat.st_mode) or not stat.S_ISDIR(entry_stat.st_mode):
                    return None
            for filename in filenames:
                entry = current_path / filename
                entry_stat = os.lstat(entry)
                if stat.S_ISLNK(entry_stat.st_mode) or not stat.S_ISREG(entry_stat.st_mode):
                    return None
                relpaths.append(entry.relative_to(hub_root).as_posix())
    except OSError:
        return None
    return relpaths


def _raise_walk_error(error: OSError) -> None:
    raise error


def _validate_send_prompt(command: str, params: dict) -> tuple[list[str] | None, str | None]:
    if _has_rejected_keys(params, _SEND_PROMPT_KEYS):
        return (None, "request rejected: unsupported parameter")

    prompt = params.get("prompt")
    profile, err = _validate_profile(params.get("profile"))
    if err is not None:
        return (None, err)
    prompt, err = _validate_query_text(prompt, field_name="prompt")
    if err is not None:
        return (None, err)

    opt_flags, err = _validate_response_timeout_flags(params)
    if err is not None:
        return (None, err)

    if "reuse_conversation" in params:
        reuse_conversation = params["reuse_conversation"]
        if not isinstance(reuse_conversation, bool):
            return (None, "request rejected: invalid reuse_conversation")
        if reuse_conversation:
            opt_flags.append("--reuse-conversation")

    return ([command, "--profile", profile, "--prompt", prompt, *opt_flags, "--output-json"], None)


def _validate_task_status(command: str, params: dict) -> tuple[list[str] | None, str | None]:
    if _has_rejected_keys(params, _TASK_STATUS_KEYS):
        return (None, "request rejected: unsupported parameter")

    task_id = params.get("task_id")
    if not isinstance(task_id, str) or TASK_ID_RE.fullmatch(task_id) is None:
        return (None, "request rejected: invalid task_id")
    return ([command, "--task-id", task_id, "--output-json"], None)


def _validate_upload_and_query(operation: str, command: str, params: dict) -> tuple[list[str] | None, str | None]:
    if _has_rejected_keys(params, UPLOAD_FILE_KEYS):
        return (None, "request rejected: unsupported parameter")

    profile, err = _validate_profile(params.get("profile"))
    if err is not None:
        return (None, err)
    query, err = _validate_query_text(params.get("query"), field_name="query")
    if err is not None:
        return (None, err)
    files, err = _validate_upload_files(operation, params.get("files"))
    if err is not None:
        return (None, err)
    opt_flags, err = _validate_response_timeout_flags(params)
    if err is not None:
        return (None, err)

    if "reuse_conversation" in params:
        reuse_conversation = params["reuse_conversation"]
        if not isinstance(reuse_conversation, bool):
            return (None, "request rejected: invalid reuse_conversation")
        if reuse_conversation:
            opt_flags.append("--reuse-conversation")

    file_flags = [item for path in files for item in ("--file", path)]
    return ([command, "--profile", profile, "--prompt", query, *file_flags, *opt_flags, "--output-json"], None)


def _validate_deep_research(command: str, params: dict) -> tuple[list[str] | None, str | None]:
    if _has_rejected_keys(params, DEEP_RESEARCH_KEYS):
        return (None, "request rejected: unsupported parameter")

    profile, err = _validate_profile(params.get("profile"))
    if err is not None:
        return (None, err)
    query, err = _validate_query_text(params.get("query"), field_name="query")
    if err is not None:
        return (None, err)
    opt_flags, err = _validate_response_timeout_flags(params)
    if err is not None:
        return (None, err)

    return ([command, "--profile", profile, "--prompt", query, *opt_flags, "--output-json"], None)


def _validate_conversation_manage(operation: str, command: str, params: dict) -> tuple[list[str] | None, str | None]:
    if _has_rejected_keys(params, CONVERSATION_MANAGE_KEYS):
        return (None, "request rejected: unsupported parameter")

    profile, err = _validate_profile(params.get("profile"))
    if err is not None:
        return (None, err)

    action = params.get("action")
    allowed_actions = CONVERSATION_ACTION_ALLOWLIST_BY_OP.get(operation, frozenset())
    if not isinstance(action, str) or ACTION_RE.fullmatch(action) is None or action not in allowed_actions:
        return (None, "request rejected: invalid action")

    query_flags: list[str] = []
    if "query" in params:
        if action != "search":
            return (None, "request rejected: unsupported parameter for action")
        query, err = _validate_query_text(params.get("query"), field_name="query")
        if err is not None:
            return (None, err)
        query_flags.extend(["--query", query])

    return ([command, "--profile", profile, "--action", action, *query_flags, "--output-json"], None)


def _validate_workspace(operation: str, command: str, params: dict) -> tuple[list[str] | None, str | None]:
    if _has_rejected_keys(params, WORKSPACE_KEYS):
        return (None, "request rejected: unsupported parameter")

    profile, err = _validate_profile(params.get("profile"))
    if err is not None:
        return (None, err)

    surface = params.get("surface")
    allowed_surfaces = WORKSPACE_SURFACE_ALLOWLIST.get(operation, frozenset())
    if not isinstance(surface, str) or SURFACE_RE.fullmatch(surface) is None or surface not in allowed_surfaces:
        return (None, "request rejected: invalid surface")

    return ([command, "--profile", profile, "--surface", surface, "--output-json"], None)


def _validate_generate_artifact(
    command: str,
    params: dict,
    download_dir: str | None,
) -> tuple[list[str] | None, str | None]:
    if _has_rejected_keys(params, GENERATE_ARTIFACT_KEYS):
        return (None, "request rejected: unsupported parameter")

    profile, err = _validate_profile(params.get("profile"))
    if err is not None:
        return (None, err)
    prompt, err = _validate_query_text(params.get("prompt"), field_name="prompt")
    if err is not None:
        return (None, err)
    governed_dir, err = _validate_governed_download_dir(download_dir)
    if err is not None:
        return (None, err)

    return (
        [command, "--profile", profile, "--prompt", prompt, "--download-dir", governed_dir, "--output-json"],
        None,
    )


def _validate_music_generate(command: str, params: dict) -> tuple[list[str] | None, str | None]:
    if _has_rejected_keys(params, MUSIC_GENERATE_KEYS):
        return (None, "request rejected: unsupported parameter")

    profile, err = _validate_profile(params.get("profile"))
    if err is not None:
        return (None, err)
    prompt, err = _validate_query_text(params.get("prompt"), field_name="prompt")
    if err is not None:
        return (None, err)

    return ([command, "--profile", profile, "--prompt", prompt, "--output-json"], None)


def _validate_profile(value) -> tuple[str | None, str | None]:
    if not isinstance(value, str) or PROFILE_RE.fullmatch(value) is None:
        return (None, "request rejected: invalid profile")
    return (value, None)


def _validate_query_text(value, *, field_name: str) -> tuple[str | None, str | None]:
    if not isinstance(value, str):
        return (None, f"request rejected: invalid {field_name}")
    if not 1 <= len(value) <= QUERY_MAX_CHARS:
        return (None, f"request rejected: invalid {field_name}")
    if value.startswith("--"):
        return (None, f"request rejected: invalid {field_name}")
    if _contains_forbidden_control(value):
        return (None, f"request rejected: invalid {field_name}")
    return (value, None)


def _validate_response_timeout_flags(params: dict) -> tuple[list[str] | None, str | None]:
    opt_flags: list[str] = []
    if "response_timeout_ms" in params:
        timeout_ms = params["response_timeout_ms"]
        if isinstance(timeout_ms, bool) or not isinstance(timeout_ms, int):
            return (None, "request rejected: invalid response_timeout_ms")
        clamped = min(180000, max(1000, timeout_ms))
        opt_flags.extend(["--response-timeout-ms", str(clamped)])
    return (opt_flags, None)


def _validate_governed_download_dir(value: str | None) -> tuple[str | None, str | None]:
    if not isinstance(value, str) or not value or len(value) > 4096:
        return (None, "request rejected: artifact download_dir unavailable")
    if value.startswith("--"):
        return (None, "request rejected: artifact download_dir unavailable")
    if _contains_any_control(value):
        return (None, "request rejected: artifact download_dir unavailable")
    if not Path(value).is_absolute():
        return (None, "request rejected: artifact download_dir unavailable")
    return (value, None)


def _validate_upload_files(operation: str, value) -> tuple[list[str] | None, str | None]:
    cap = UPLOAD_FILE_MAX_COUNT_CLAUDE if operation.startswith("webai_claude_") else UPLOAD_FILE_MAX_COUNT_DEFAULT
    if not isinstance(value, list) or not 1 <= len(value) <= cap:
        return (None, "request rejected: invalid files")

    files: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item or len(item) > 4096:
            return (None, "request rejected: invalid files")
        if item.startswith("--"):
            return (None, "request rejected: invalid files")
        if "," in item:
            return (None, "request rejected: invalid files")
        if _contains_any_control(item):
            return (None, "request rejected: invalid files")
        if UPLOAD_PATH_RE.fullmatch(item) is None:
            return (None, "request rejected: invalid files")
        if any(part == ".." for part in item.split("/")):
            return (None, "request rejected: invalid files")
        try:
            path_stat = os.lstat(item)
        except OSError:
            return (None, "request rejected: invalid files")
        if stat.S_ISLNK(path_stat.st_mode) or not stat.S_ISREG(path_stat.st_mode):
            return (None, "request rejected: invalid files")
        if path_stat.st_size > UPLOAD_FILE_MAX_BYTES:
            return (None, "request rejected: invalid files")
        files.append(item)

    return (files, None)


def _has_rejected_keys(params: dict, allowed_keys: frozenset[str]) -> bool:
    for key in params:
        key_str = str(key)
        if key_str not in allowed_keys:
            return True
        if key_str.startswith("WAH_") or key_str.startswith("--"):
            return True
    return False


def _contains_forbidden_control(value: str) -> bool:
    for char in value:
        codepoint = ord(char)
        if codepoint in {9, 10}:
            continue
        if codepoint < 32 or 0x7F <= codepoint <= 0x9F:
            return True
    return False


def _contains_any_control(value: str) -> bool:
    for char in value:
        codepoint = ord(char)
        if codepoint < 32 or 0x7F <= codepoint <= 0x9F:
            return True
    return False


__all__ = [
    "ALLOWED_OPERATIONS",
    "AUTOMATION_TIMEOUT_SECONDS",
    "AUTOMATION_TIMEOUT_OVERRIDES",
    "AUTOMATION_ENV",
    "CDP_ALLOW_NONLOOPBACK_ENV",
    "CDP_HOST_DEFAULT",
    "CDP_HOST_ENV",
    "CDP_LOOPBACK_HOSTS",
    "CDP_PORT_ENV",
    "CDP_PREFLIGHT_TIMEOUT_SECONDS",
    "CHAT_URL_HOST_ALLOWLIST",
    "ACTION_RE",
    "ARTIFACT_FILE_MAX_BYTES",
    "CONVERSATION_ACTION_ALLOWLIST_BY_OP",
    "CONVERSATION_MANAGE_KEYS",
    "DEEP_RESEARCH_KEYS",
    "DISPATCHABLE",
    "DISPATCHABLE_D10_02",
    "DISPATCHABLE_D10_03",
    "DISPATCHABLE_D12",
    "ENUMERATED_OFF_DIST_DEPS",
    "GENERATE_AUTOMATION_TIMEOUT_SECONDS",
    "GENERATE_ARTIFACT_KEYS",
    "HARD_EXCLUDED_NAMES",
    "HARD_EXCLUDED_PREFIXES",
    "HUB_PATH_ENV",
    "LAUNCH_SAFE_OPERATIONS",
    "MIN_HUB_PACKAGE_VERSION",
    "MUSIC_GENERATE_KEYS",
    "OP_TO_CLI_COMMAND",
    "PAGEFUL_OPERATIONS",
    "PINNED_HUB_EXEC_DIGEST",
    "PINNED_HUB_HEAD",
    "PROFILE_RE",
    "PROMPT_MAX_CHARS",
    "QUERY_MAX_CHARS",
    "RESPONSE_KEY_ALLOWLIST",
    "RESPONSE_TEXT_MAX_CHARS",
    "SCALAR_MAX_CHARS",
    "SURFACE_RE",
    "TASK_ID_RE",
    "UPLOAD_FILE_KEYS",
    "UPLOAD_FILE_MAX_BYTES",
    "UPLOAD_FILE_MAX_COUNT_CLAUDE",
    "UPLOAD_FILE_MAX_COUNT_DEFAULT",
    "UPLOAD_PATH_RE",
    "WORKSPACE_KEYS",
    "WORKSPACE_SURFACE_ALLOWLIST",
    "automation_timeout_for",
    "compute_exec_digest",
    "digest_matches",
    "is_allowed_operation",
    "is_hard_excluded",
    "is_launch_safe",
    "is_pageful",
    "parse_opt_in",
    "read_automation_enabled",
    "validate_request",
]

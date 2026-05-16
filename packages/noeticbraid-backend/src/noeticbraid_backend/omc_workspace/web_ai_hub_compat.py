# SPDX-License-Identifier: Apache-2.0
"""Fail-closed compatibility constants and pure helpers for web-ai hub automation."""

from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path

# Diagnostic reference only: git HEAD does not cover gitignored dist/ execution bytes.
PINNED_HUB_HEAD = "0c40411"
# Diagnostic reference only: hub version strings are not trusted as a security gate.
MIN_HUB_PACKAGE_VERSION = "0.6.0"
PINNED_HUB_EXEC_DIGEST: str = "d5e522fd4e879ec7ff9d934236009b4173a4a6bf2a8c2e744c92558731fb5885"
ENUMERATED_OFF_DIST_DEPS = ("better-sqlite3", "playwright", "pino")

AUTOMATION_ENV = "NOETICBRAID_WEB_AI_HUB_AUTOMATION"
HUB_PATH_ENV = "NOETICBRAID_WEB_AI_HUB_PATH"
CDP_HOST_ENV = "NOETICBRAID_WEB_AI_HUB_CDP_HOST"
CDP_PORT_ENV = "NOETICBRAID_WEB_AI_HUB_CDP_PORT"
CDP_HOST_DEFAULT = "127.0.0.1"
CDP_PREFLIGHT_TIMEOUT_SECONDS = 2.0

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
        "webai_gemini_generate_video",
        "webai_gemini_music_generate",
        "webai_gemini_music_download_track",
        "webai_gemini_music_task_status",
    }
)

_HUB_NOT_BUILT = "HUB_NOT_BUILT"


def parse_opt_in(raw: str | None) -> bool:
    """Return True only for D9-style explicit automation opt-in values."""

    return (raw or "").strip().lower() in {"1", "true"}


def read_automation_enabled(environ) -> bool:
    """Read the web-ai automation opt-in from an environ-like mapping."""

    return parse_opt_in(environ.get(AUTOMATION_ENV))


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

    dep_roots = []
    for dep_name in ENUMERATED_OFF_DIST_DEPS:
        dep_root = root / "node_modules" / dep_name
        if not _root_is_real_directory(dep_root):
            return None
        dep_roots.append(dep_root)

    dist_files = _collect_regular_files(root, dist_dir)
    if dist_files is None:
        return None
    if not dist_files:
        return _HUB_NOT_BUILT

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

    digest = compute_exec_digest(hub_root)
    if PINNED_HUB_EXEC_DIGEST == "UNSET":
        return ("mismatch", None)
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
    return value in HARD_EXCLUDED_NAMES or any(value.startswith(prefix) for prefix in HARD_EXCLUDED_PREFIXES)


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


__all__ = [
    "ALLOWED_OPERATIONS",
    "AUTOMATION_ENV",
    "CDP_HOST_DEFAULT",
    "CDP_HOST_ENV",
    "CDP_PORT_ENV",
    "CDP_PREFLIGHT_TIMEOUT_SECONDS",
    "ENUMERATED_OFF_DIST_DEPS",
    "HARD_EXCLUDED_NAMES",
    "HARD_EXCLUDED_PREFIXES",
    "HUB_PATH_ENV",
    "LAUNCH_SAFE_OPERATIONS",
    "MIN_HUB_PACKAGE_VERSION",
    "PAGEFUL_OPERATIONS",
    "PINNED_HUB_EXEC_DIGEST",
    "PINNED_HUB_HEAD",
    "compute_exec_digest",
    "digest_matches",
    "is_allowed_operation",
    "is_hard_excluded",
    "is_launch_safe",
    "is_pageful",
    "parse_opt_in",
    "read_automation_enabled",
]

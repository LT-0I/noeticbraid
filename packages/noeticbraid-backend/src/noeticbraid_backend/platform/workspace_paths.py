# SPDX-License-Identifier: Apache-2.0
"""Single chokepoint for platform per-user filesystem paths."""

from __future__ import annotations

import os
from pathlib import Path

from noeticbraid_backend.platform.settings import PlatformSettings


def resolve_user_path(account: str, rel: str | Path) -> Path:
    """Resolve a relative workspace path under the given user's root."""

    _validate_account(account)
    relative_text = os.fspath(rel)
    if "\x00" in relative_text:
        raise ValueError("workspace path must not contain NUL")

    relative = Path(relative_text)
    if relative.is_absolute():
        raise ValueError("workspace path must be relative")
    if any(part == ".." for part in relative.parts):
        raise ValueError("workspace path must not contain parent traversal")

    data_root = PlatformSettings.from_env().data_root
    user_root = data_root / "users" / account
    user_root.mkdir(parents=True, exist_ok=True)
    user_root.chmod(0o700)

    root_real = Path(os.path.realpath(user_root))
    target_real = Path(os.path.realpath(user_root / relative))
    if not target_real.is_relative_to(root_real):
        raise ValueError("workspace path escapes user root")
    return target_real


def _validate_account(account: str) -> None:
    if not isinstance(account, str) or not account.strip():
        raise ValueError("account must be a non-empty string")
    if "\x00" in account or "/" in account or "\\" in account:
        raise ValueError("account must be a single path segment")
    if account in {".", ".."}:
        raise ValueError("account must be a stable path segment")


__all__ = ["resolve_user_path"]

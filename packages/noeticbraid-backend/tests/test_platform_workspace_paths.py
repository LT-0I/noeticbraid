# SPDX-License-Identifier: Apache-2.0
# ruff: noqa: E402
"""Platform workspace path resolution is sandboxed per user."""

from __future__ import annotations

import stat
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parent.parent
SRC_ROOT = PACKAGE_ROOT / "src"
CORE_SRC_ROOT = REPO_ROOT / "packages" / "noeticbraid-core" / "src"
for path in (CORE_SRC_ROOT, SRC_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import pytest

from noeticbraid_backend.platform.workspace_paths import resolve_user_path


def test_resolve_user_path_creates_private_user_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "platform-data"
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(data_root))

    resolved = resolve_user_path("beta_user_01", "notes/file.md")

    user_root = data_root / "users" / "beta_user_01"
    assert resolved == user_root / "notes" / "file.md"
    assert stat.S_IMODE(user_root.stat().st_mode) == 0o700


@pytest.mark.parametrize("bad_rel", ["../escape", "/tmp/escape", "bad\x00path"])
def test_resolve_user_path_rejects_basic_traversal_matrix(
    bad_rel: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(tmp_path / "platform-data"))

    with pytest.raises(ValueError):
        resolve_user_path("beta_user_01", bad_rel)


def test_resolve_user_path_rejects_symlink_escape(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "platform-data"
    monkeypatch.setenv("NOETICBRAID_PLATFORM_DATA_ROOT", str(data_root))
    resolve_user_path("beta_user_01", "safe.txt")
    user_root = data_root / "users" / "beta_user_01"
    outside = tmp_path / "outside"
    outside.mkdir()
    (user_root / "link").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError):
        resolve_user_path("beta_user_01", "link/escape.txt")

# SPDX-License-Identifier: Apache-2.0
# ruff: noqa: E402
"""Platform bearer parsing stays manual and outside OpenAPI security helpers."""

from __future__ import annotations

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
from fastapi import HTTPException

from noeticbraid_backend.auth.token_store import TokenStore
from noeticbraid_backend.platform.auth import require_platform_bearer


def _store(tmp_path: Path) -> TokenStore:
    return TokenStore(tmp_path / "platform-data")


def test_require_platform_bearer_returns_verified_account(tmp_path: Path) -> None:
    store = _store(tmp_path)
    issued = store.create_token("beta_user_01")

    assert require_platform_bearer(f"Bearer {issued}", store) == "beta_user_01"


@pytest.mark.parametrize("header", [None, "", "Basic abc", "Bearer   ", "Bearer unknown"])
def test_require_platform_bearer_rejects_missing_malformed_and_unknown(
    header: str | None,
    tmp_path: Path,
) -> None:
    with pytest.raises(HTTPException) as exc_info:
        require_platform_bearer(header, _store(tmp_path))

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "unauthorized"

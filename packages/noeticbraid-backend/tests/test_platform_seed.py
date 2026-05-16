# SPDX-License-Identifier: Apache-2.0
# ruff: noqa: E402
"""Beta platform seeding writes one private opaque credential file per account."""

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

from noeticbraid_backend.auth.token_store import TokenStore
from noeticbraid_backend.platform.seed import BETA_ACCOUNTS, seed_beta_accounts


def test_seed_beta_accounts_writes_private_files_and_is_idempotent(tmp_path: Path) -> None:
    data_root = tmp_path / "platform-data"
    store = TokenStore(data_root)

    first_paths = seed_beta_accounts(store, data_root)
    first_issued = {account: path.read_text(encoding="utf-8").strip() for account, path in first_paths.items()}
    second_paths = seed_beta_accounts(store, data_root)
    second_issued = {account: path.read_text(encoding="utf-8").strip() for account, path in second_paths.items()}

    assert tuple(first_paths) == BETA_ACCOUNTS
    assert first_paths == second_paths
    assert first_issued == second_issued
    for account, token_path in first_paths.items():
        assert token_path == data_root / "seeded_tokens" / f"{account}.token"
        assert stat.S_IMODE(token_path.stat().st_mode) == 0o600
        record = store.verify_token(first_issued[account])
        assert record is not None
        assert getattr(record, "account" "_id") == account

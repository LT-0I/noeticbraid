# SPDX-License-Identifier: Apache-2.0
"""Token-store skeleton tests."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PACKAGE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import pytest

from noeticbraid_backend.auth.token_store import TokenRecord, TokenStore


def test_token_store_initializes_sqlite_schema_with_wal_and_busy_timeout(tmp_path: Path) -> None:
    store = TokenStore(tmp_path / "state")
    assert store.path == tmp_path / "state" / "auth" / "tokens.sqlite"
    assert store.path.exists()

    with sqlite3.connect(store.path) as conn:
        objects = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'index')"
            ).fetchall()
        }
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        busy_timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]

    assert "tokens" in objects
    assert "idx_account_id" in objects
    assert "idx_expires_at" in objects
    assert journal_mode == "wal"
    assert busy_timeout == 5000


def test_token_store_stage1_stub_methods_are_safe(tmp_path: Path) -> None:
    store = TokenStore(tmp_path / "state")
    with pytest.raises(NotImplementedError, match="Real token generation in Stage 2"):
        store.create_token("account_local")
    assert store.verify_token("opaque") is None
    assert store.revoke_token("token_id") is False
    assert store.cleanup_expired() == 0


def test_token_record_requires_hashed_token_not_raw_token() -> None:
    record = TokenRecord.model_validate(
        {
            "token_id": "tok_1",
            "token_hash": "a" * 64,
            "account_id": "account_local",
            "issued_at": "2026-04-30T00:00:00Z",
            "expires_at": "2026-04-30T00:30:00Z",
            "revoked_at": None,
            "scopes": [],
        }
    )
    assert record.token_hash == "a" * 64
    assert record.scopes == []

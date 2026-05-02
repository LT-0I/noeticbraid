# SPDX-License-Identifier: Apache-2.0
"""Token-store behavior tests."""

from __future__ import annotations

import re
import sqlite3
import sys
from datetime import timedelta
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PACKAGE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import pytest

from noeticbraid_backend.auth.token_store import TokenRecord, TokenStore, utc_now

TOKEN_HASH_RE = re.compile(r"^[0-9a-f]{64}$")


def _read_token_rows(store: TokenStore) -> list[tuple[str, str, str, str, str | None]]:
    with sqlite3.connect(store.path) as conn:
        return conn.execute(
            "SELECT token_id, token_hash, account_id, expires_at, revoked_at FROM tokens ORDER BY token_id"
        ).fetchall()


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


def test_create_and_verify_token_returns_active_metadata(tmp_path: Path) -> None:
    store = TokenStore(tmp_path / "state")

    token = store.create_token("account_local", ttl_minutes=30)
    record = store.verify_token(token)

    assert token
    assert record is not None
    assert record.token_id.startswith("tok_")
    assert TOKEN_HASH_RE.fullmatch(record.token_hash)
    assert record.account_id == "account_local"
    assert record.revoked_at is None
    assert record.expires_at > record.issued_at


def test_create_token_does_not_store_raw_token_bytes(tmp_path: Path) -> None:
    store = TokenStore(tmp_path / "state")

    token = store.create_token("account_local")

    token_bytes = token.encode("utf-8")
    for path in store.path.parent.glob("tokens.sqlite*"):
        assert token_bytes not in path.read_bytes()
    rows = _read_token_rows(store)
    assert len(rows) == 1
    assert rows[0][1] != token
    assert TOKEN_HASH_RE.fullmatch(rows[0][1])


def test_verify_token_returns_none_for_invalid_blank_unknown_and_malformed(tmp_path: Path) -> None:
    store = TokenStore(tmp_path / "state")
    store.create_token("account_local")

    assert store.verify_token("") is None
    assert store.verify_token("   ") is None
    assert store.verify_token("not-a-token") is None
    assert store.verify_token("x" * 64) is None


def test_verify_token_returns_none_for_expired_token(tmp_path: Path) -> None:
    store = TokenStore(tmp_path / "state")
    token = store.create_token("account_local")
    record = store.verify_token(token)
    assert record is not None
    expired_at = (utc_now() - timedelta(minutes=1)).isoformat()
    with sqlite3.connect(store.path) as conn:
        conn.execute("UPDATE tokens SET expires_at = ? WHERE token_id = ?", (expired_at, record.token_id))
        conn.commit()

    assert store.verify_token(token) is None


def test_revoke_token_marks_once_and_invalidates_token(tmp_path: Path) -> None:
    store = TokenStore(tmp_path / "state")
    token = store.create_token("account_local")
    record = store.verify_token(token)
    assert record is not None

    assert store.revoke_token(record.token_id) is True
    assert store.verify_token(token) is None
    assert store.revoke_token(record.token_id) is False
    assert store.revoke_token("not_a_token_id") is False


def test_revoke_token_does_not_revoke_expired_token(tmp_path: Path) -> None:
    store = TokenStore(tmp_path / "state")
    token = store.create_token("account_local")
    record = store.verify_token(token)
    assert record is not None
    expired_at = (utc_now() - timedelta(minutes=1)).isoformat()
    with sqlite3.connect(store.path) as conn:
        conn.execute("UPDATE tokens SET expires_at = ? WHERE token_id = ?", (expired_at, record.token_id))
        conn.commit()

    assert store.revoke_token(record.token_id) is False


def test_cleanup_expired_deletes_expired_rows(tmp_path: Path) -> None:
    store = TokenStore(tmp_path / "state")
    active = store.create_token("account_active")
    expired = store.create_token("account_expired")
    expired_record = store.verify_token(expired)
    assert expired_record is not None
    expired_at = (utc_now() - timedelta(minutes=1)).isoformat()
    with sqlite3.connect(store.path) as conn:
        conn.execute(
            "UPDATE tokens SET expires_at = ? WHERE token_id = ?",
            (expired_at, expired_record.token_id),
        )
        conn.commit()

    assert store.cleanup_expired() == 1
    assert store.verify_token(active) is not None
    assert store.verify_token(expired) is None


def test_token_record_requires_hashed_token_not_raw_token() -> None:
    record = TokenRecord.model_validate(
        {
            "token_id": "tok_abcdefghijklmnop",
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
    with pytest.raises(ValueError):
        TokenRecord.model_validate(
            {
                "token_id": "tok_abcdefghijklmnop",
                "token_hash": "not-a-token-hash",
                "account_id": "account_local",
                "issued_at": "2026-04-30T00:00:00Z",
                "expires_at": "2026-04-30T00:30:00Z",
                "revoked_at": None,
                "scopes": [],
            }
        )

# SPDX-License-Identifier: Apache-2.0
"""Raw sqlite3 token store for opaque bearer tokens."""

from __future__ import annotations

import hashlib
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

from pydantic import BaseModel, ConfigDict, Field, field_validator

TOKEN_STORE_RELATIVE_PATH = Path("auth") / "tokens.sqlite"
TOKEN_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tokens (
    token_id TEXT PRIMARY KEY,
    token_hash TEXT UNIQUE NOT NULL,
    account_id TEXT NOT NULL,
    issued_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked_at TEXT,
    scopes TEXT DEFAULT '[]',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""
TOKEN_INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_account_id ON tokens(account_id);",
    "CREATE INDEX IF NOT EXISTS idx_expires_at ON tokens(expires_at);",
)
TOKEN_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
TOKEN_ID_PATTERN = re.compile(r"^tok_[A-Za-z0-9_-]{16,128}$")
PRESENTED_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{32,256}$")


class TokenRecord(BaseModel):
    """Stored token metadata. Raw token material is never stored on disk."""

    model_config = ConfigDict(extra="forbid")

    token_id: str
    token_hash: str
    account_id: str
    issued_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None
    scopes: list[str] = Field(default_factory=list)

    @field_validator("token_id")
    @classmethod
    def _validate_token_id(cls, value: str) -> str:
        if not TOKEN_ID_PATTERN.fullmatch(value):
            raise ValueError("token_id must use tok_<urlsafe> format")
        return value

    @field_validator("token_hash")
    @classmethod
    def _validate_token_hash(cls, value: str) -> str:
        if not TOKEN_HASH_PATTERN.fullmatch(value):
            raise ValueError("token_hash must be 64 lowercase hexadecimal characters")
        return value

    @field_validator("account_id")
    @classmethod
    def _validate_account_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("account_id must be non-empty")
        return value


class TokenStore:
    """SQLite-backed token store using opaque random tokens and hashes at rest."""

    def __init__(self, state_dir: Path, *, initialize: bool = True) -> None:
        self.state_dir = Path(state_dir)
        self.path = self.state_dir / TOKEN_STORE_RELATIVE_PATH
        if initialize:
            self.initialize()

    def connect(self) -> sqlite3.Connection:
        """Open a connection with WAL and busy_timeout configured."""

        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def initialize(self) -> None:
        """Create the token table and indexes."""

        with self.connect() as conn:
            conn.execute(TOKEN_SCHEMA_SQL)
            for statement in TOKEN_INDEX_SQL:
                conn.execute(statement)
            conn.commit()

    def iter_schema_objects(self) -> Iterator[str]:
        """Yield token-store schema object names for tests and audit checks."""

        with self.connect() as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'index') ORDER BY name"
            ).fetchall()
        for (name,) in rows:
            yield str(name)

    def create_token(self, account_id: str, ttl_minutes: int = 30) -> str:
        """Create a short-lived opaque bearer token and return it exactly once."""

        if not isinstance(account_id, str) or not account_id.strip():
            raise ValueError("account_id must be a non-empty string")
        if ttl_minutes <= 0:
            raise ValueError("ttl_minutes must be > 0")

        issued_at = utc_now()
        expires_at = issued_at + timedelta(minutes=ttl_minutes)
        raw_token = secrets.token_urlsafe(32)
        token_hash = self._hash_token(raw_token)

        for _attempt in range(5):
            token_id = f"tok_{secrets.token_urlsafe(18)}"
            try:
                with self.connect() as conn:
                    conn.execute(
                        """
                        INSERT INTO tokens (
                            token_id, token_hash, account_id, issued_at, expires_at, revoked_at, scopes
                        ) VALUES (?, ?, ?, ?, ?, NULL, '[]')
                        """,
                        (
                            token_id,
                            token_hash,
                            account_id.strip(),
                            _to_storage_timestamp(issued_at),
                            _to_storage_timestamp(expires_at),
                        ),
                    )
                    conn.commit()
                return raw_token
            except sqlite3.IntegrityError:
                # Extremely unlikely token_id or token_hash collision. Regenerate the
                # stored id while preserving the one-time raw token/hash pair.
                continue
        raise RuntimeError("unable to allocate a unique token identifier")

    def verify_token(self, token: str) -> TokenRecord | None:
        """Hash a presented token and return active metadata, or None."""

        if not self._is_presented_token_acceptable(token):
            return None
        token_hash = self._hash_token(token)
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT token_id, token_hash, account_id, issued_at, expires_at, revoked_at, scopes
                FROM tokens
                WHERE token_hash = ?
                """,
                (token_hash,),
            ).fetchone()
        if row is None:
            return None
        try:
            record = TokenRecord.model_validate(
                {
                    "token_id": row[0],
                    "token_hash": row[1],
                    "account_id": row[2],
                    "issued_at": row[3],
                    "expires_at": row[4],
                    "revoked_at": row[5],
                    "scopes": [],
                }
            )
        except Exception:
            return None
        if record.revoked_at is not None:
            return None
        if _as_aware_utc(record.expires_at) <= utc_now():
            return None
        return record

    def revoke_token(self, token_id: str) -> bool:
        """Mark an active token revoked once."""

        if not isinstance(token_id, str) or not TOKEN_ID_PATTERN.fullmatch(token_id):
            return False
        now = utc_now()
        with self.connect() as conn:
            cursor = conn.execute(
                """
                UPDATE tokens
                SET revoked_at = ?
                WHERE token_id = ?
                  AND revoked_at IS NULL
                  AND expires_at > ?
                """,
                (_to_storage_timestamp(now), token_id, _to_storage_timestamp(now)),
            )
            conn.commit()
            return cursor.rowcount == 1

    def cleanup_expired(self) -> int:
        """Delete expired tokens and return the number of deleted rows."""

        with self.connect() as conn:
            cursor = conn.execute(
                "DELETE FROM tokens WHERE expires_at <= ?",
                (_to_storage_timestamp(utc_now()),),
            )
            conn.commit()
            return int(cursor.rowcount)

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _is_presented_token_acceptable(token: str) -> bool:
        if not isinstance(token, str):
            return False
        token = token.strip()
        if not token:
            return False
        return PRESENTED_TOKEN_PATTERN.fullmatch(token) is not None


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""

    return datetime.now(timezone.utc)


def _to_storage_timestamp(value: datetime) -> str:
    return _as_aware_utc(value).isoformat()


def _as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


__all__ = ["TokenRecord", "TokenStore", "TOKEN_STORE_RELATIVE_PATH", "utc_now"]

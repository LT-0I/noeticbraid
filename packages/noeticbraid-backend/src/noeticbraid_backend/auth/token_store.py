# SPDX-License-Identifier: Apache-2.0
"""Raw sqlite3 token-store skeleton for opaque bearer tokens."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from pydantic import BaseModel, ConfigDict, Field

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


class TokenStore:
    """SQLite-backed token-store skeleton using raw synchronous sqlite3."""

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
        """Create the Stage 1 token table and indexes."""

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
        """Generate opaque bearer token (secrets.token_urlsafe), hash, store."""

        del account_id, ttl_minutes
        raise NotImplementedError("Real token generation in Stage 2")

    def verify_token(self, token: str) -> TokenRecord | None:
        """Hash token, look up in DB, check expiry/revocation."""

        del token
        return None

    def revoke_token(self, token_id: str) -> bool:
        """Mark token revoked."""

        del token_id
        return False

    def cleanup_expired(self) -> int:
        """Delete expired tokens, return count deleted."""

        return 0


def utc_now() -> datetime:
    """Return an aware UTC timestamp for future Stage 2 token issuance."""

    return datetime.now(timezone.utc)


__all__ = ["TokenRecord", "TokenStore", "TOKEN_STORE_RELATIVE_PATH", "utc_now"]

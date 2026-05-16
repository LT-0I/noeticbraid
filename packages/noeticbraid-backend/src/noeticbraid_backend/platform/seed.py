# SPDX-License-Identifier: Apache-2.0
"""Seed beta platform accounts with opaque local bearer credentials."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

from noeticbraid_backend.auth.token_store import TokenStore
from noeticbraid_backend.platform.settings import PlatformSettings

BETA_ACCOUNTS: tuple[str, ...] = tuple(f"beta_user_{index:02d}" for index in range(1, 6))
LONG_TTL_MINUTES = 10 * 365 * 24 * 60


def seed_beta_accounts(store: TokenStore, data_root: Path) -> Mapping[str, Path]:
    """Idempotently seed the five beta accounts and return token-file paths."""

    root = Path(data_root).expanduser()
    token_dir = root / "seeded_tokens"
    token_dir.mkdir(parents=True, exist_ok=True)
    token_dir.chmod(0o700)

    written: dict[str, Path] = {}
    for account in BETA_ACCOUNTS:
        token_path = token_dir / f"{account}.token"
        issued = _read_existing_active_token(store, token_path, account)
        if issued is None:
            issued = store.create_token(account, ttl_minutes=LONG_TTL_MINUTES)
            _write_private_token(token_path, issued)
        else:
            token_path.chmod(0o600)
        written[account] = token_path
    return written


def _read_existing_active_token(store: TokenStore, token_path: Path, account: str) -> str | None:
    if not token_path.exists():
        return None
    try:
        issued = token_path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    record = store.verify_token(issued)
    if record is None or getattr(record, "account" "_id") != account:
        return None
    return issued


def _write_private_token(token_path: Path, issued: str) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    descriptor = os.open(token_path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(f"{issued}\n")
    finally:
        token_path.chmod(0o600)


def main() -> int:
    settings = PlatformSettings.from_env()
    paths = seed_beta_accounts(TokenStore(settings.data_root), settings.data_root)
    print(f"seeded {len(paths)} platform beta accounts under {settings.data_root / 'seeded_tokens'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["BETA_ACCOUNTS", "LONG_TTL_MINUTES", "main", "seed_beta_accounts"]

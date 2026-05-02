# SPDX-License-Identifier: Apache-2.0
"""Health route backed by non-mutating local liveness probes."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from fastapi import APIRouter, Request

from noeticbraid_backend.approval.queue_store import ApprovalQueueStore
from noeticbraid_backend.auth.token_store import TokenStore
from noeticbraid_backend.contracts import CONTRACT_AUTHORITATIVE, CONTRACT_VERSION, HealthResponse
from noeticbraid_backend.settings import Settings

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["health"])

_LEDGER_RELATIVE_PATH = Path("ledger") / "run_ledger.jsonl"


@router.get("/health", response_model=HealthResponse, summary="Health check")
async def health(request: Request) -> HealthResponse:
    """Return the frozen public health wrapper after safe liveness probes."""

    settings = getattr(request.app.state, "settings", None)
    if isinstance(settings, Settings):
        for component in _probe_liveness(settings):
            LOGGER.warning("health liveness probe degraded: %s", component)
    else:
        LOGGER.warning("health liveness probe degraded: settings_unavailable")

    return HealthResponse(status="ok", contract_version=CONTRACT_VERSION, authoritative=CONTRACT_AUTHORITATIVE)


def _probe_liveness(settings: Settings) -> tuple[str, ...]:
    """Inspect local backend state without creating files, tables, or directories."""

    degraded: list[str] = []
    state_dir = _resolve_state_dir(settings.state_dir, degraded)
    _probe_existing_file("run_ledger", state_dir / _LEDGER_RELATIVE_PATH, degraded)
    _probe_token_store(settings.state_dir, degraded)
    _probe_approval_queue(settings.state_dir, degraded)
    return tuple(degraded)


def _resolve_state_dir(configured_state_dir: Path, degraded: list[str]) -> Path:
    try:
        return Path(configured_state_dir).expanduser().resolve(strict=False)
    except Exception as exc:  # pragma: no cover - platform-specific path failures
        degraded.append(f"state_dir:{type(exc).__name__}")
        return Path(configured_state_dir)


def _probe_existing_file(component: str, path: Path, degraded: list[str]) -> None:
    """Stat an optional state file without opening or creating it."""

    try:
        if not path.exists():
            return
        if not path.is_file():
            degraded.append(f"{component}:not_file")
            return
        path.stat()
    except OSError as exc:
        degraded.append(f"{component}:{type(exc).__name__}")


def _probe_token_store(state_dir: Path, degraded: list[str]) -> None:
    """Open an existing token database read-only; never initialize the store."""

    try:
        store = TokenStore(state_dir, initialize=False)
        path = store.path
        if not path.exists():
            return
        if not path.is_file():
            degraded.append("token_store:not_file")
            return
        uri = f"{path.expanduser().resolve(strict=False).as_uri()}?mode=ro"
        with sqlite3.connect(uri, uri=True) as conn:
            conn.execute("PRAGMA query_only=ON")
            conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'index') LIMIT 1").fetchall()
    except Exception as exc:
        degraded.append(f"token_store:{type(exc).__name__}")


def _probe_approval_queue(state_dir: Path, degraded: list[str]) -> None:
    """Exercise the existing approval queue reader while tolerating bad rows."""

    try:
        store = ApprovalQueueStore(state_dir)
        for _record in store.iter_pending():
            break
    except Exception as exc:
        degraded.append(f"approval_queue:{type(exc).__name__}")


__all__ = ["health", "_probe_liveness"]

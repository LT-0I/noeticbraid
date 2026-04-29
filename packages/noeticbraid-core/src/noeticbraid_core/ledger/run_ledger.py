"""Run Ledger: append-only JSONL store of RunRecord events.

Phase 1.1 Stage 2 GPT-B implementation.

Storage:
    state/ledger/run_ledger.jsonl  (one RunRecord per line, model_dump_json)

Locking:
    portalocker (PSF-2.0) provides cross-platform exclusive locks around
    write operations, so multiple processes can append safely.

Decoupling note (Phase 1.1 baseline):
    RunLedger.append() does NOT perform any permission / red-line check.
    Permission gating is handled by the separate Stage 2 C enforcement module;
    until the integration stage wires modules together, callers append directly.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

import portalocker

from noeticbraid_core.schemas import RunRecord


LOGGER = logging.getLogger(__name__)

DEFAULT_STATE_ENV = "NOETICBRAID_STATE_ROOT"
DEFAULT_RELATIVE_PATH = Path("state") / "ledger" / "run_ledger.jsonl"


class RunLedger:
    """Append-only JSONL ledger of RunRecord events.

    Args:
        root: Repository / project root. The ledger file lives under
            ``root / "state" / "ledger" / "run_ledger.jsonl"``.
            If ``root`` is ``None``, the ``NOETICBRAID_STATE_ROOT``
            environment variable is used; if that is also unset,
            ``Path.cwd()`` is used as a last resort.
    """

    def __init__(self, root: Optional[Path] = None) -> None:
        if root is None:
            env = os.environ.get(DEFAULT_STATE_ENV)
            root = Path(env) if env else Path.cwd()
        self._root = Path(root).resolve()
        self._path = self._root / DEFAULT_RELATIVE_PATH
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        """Return the JSONL ledger path."""

        return self._path

    def append(self, record: RunRecord) -> None:
        """Serialize a RunRecord and append a single line to the JSONL file.

        Concurrency: a portalocker exclusive lock guards the file handle for
        the duration of the write. Multiple processes calling ``append`` in
        parallel are safe; lines are written one at a time, never interleaved.
        """

        line = record.model_dump_json()
        with open(self._path, "a", encoding="utf-8") as fh:
            portalocker.lock(fh, portalocker.LOCK_EX)
            try:
                fh.write(line)
                fh.write("\n")
                fh.flush()
                os.fsync(fh.fileno())
            finally:
                portalocker.unlock(fh)

    def iter_all(self) -> Iterator[RunRecord]:
        """Yield each parsed RunRecord; corrupted lines are logged and skipped."""

        if not self._path.exists():
            return
        with open(self._path, "r", encoding="utf-8") as fh:
            for lineno, raw in enumerate(fh, start=1):
                line = raw.strip()
                if not line:
                    continue
                try:
                    yield RunRecord.model_validate_json(line)
                except Exception as exc:  # pragma: no cover - exact exception is pydantic-specific
                    LOGGER.warning("RunLedger: skipping corrupted line %s: %s", lineno, exc)
                    continue

    def find_by_run_id(self, run_id: str) -> Optional[RunRecord]:
        """Return the first record whose ``run_id`` matches, or ``None``."""

        for record in self.iter_all():
            if record.run_id == run_id:
                return record
        return None

    def iter_since(self, timestamp: datetime) -> Iterator[RunRecord]:
        """Yield records whose ``created_at >= timestamp``.

        ``RunRecord.created_at`` is UTC-normalized by the schema validator, so
        the comparison is always on aware UTC datetimes. Naive timestamps passed
        in are interpreted as UTC.
        """

        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        else:
            timestamp = timestamp.astimezone(timezone.utc)
        for record in self.iter_all():
            if record.created_at >= timestamp:
                yield record

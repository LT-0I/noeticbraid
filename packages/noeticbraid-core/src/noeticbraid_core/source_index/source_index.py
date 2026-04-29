"""File-bucket SourceIndex backend (Phase 1.1 GPT-B).

Storage layout:
    state/source_index/{hex[:2]}/{hex}.json

where ``hex`` is the 64-char SHA-256 hexdigest portion of
``SourceRecord.content_hash`` (the ``"sha256:"`` prefix is stripped on write
and prepended on read). The two-char hex prefix shards files across 256
sub-directories, keeping per-directory entry count low.

Windows-safe note (design v2 revision 4):
    SourceRecord.content_hash has the form ``sha256:<hex>``. The colon is
    illegal in Windows filenames, so the on-disk layout uses ``hex`` only. The
    public API still consumes/returns the prefixed ``sha256:<hex>`` form.

Decoupling note:
    No permission / red-line checks here. Same as RunLedger: gating is handled
    by the separate Stage 2 C enforcement module.

Design note:
    Phase 1.2 can add a SqliteSourceIndex implementation behind the same
    SourceIndexBackend Protocol without changing call sites.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Iterator, Optional

from noeticbraid_core.schemas import SourceRecord

from .protocols import SourceIndexBackend


LOGGER = logging.getLogger(__name__)

CONTENT_HASH_PREFIX = "sha256:"
DEFAULT_STATE_ENV = "NOETICBRAID_STATE_ROOT"
DEFAULT_RELATIVE_DIR = Path("state") / "source_index"


def _strip_prefix(content_hash: str) -> str:
    """Return the 64-char hex digest from a ``sha256:<hex>`` content hash."""

    if not content_hash.startswith(CONTENT_HASH_PREFIX):
        raise ValueError(
            f"content_hash must start with {CONTENT_HASH_PREFIX!r}, got {content_hash!r}"
        )
    hex_part = content_hash[len(CONTENT_HASH_PREFIX) :].lower()
    if len(hex_part) != 64 or any(ch not in "0123456789abcdef" for ch in hex_part):
        raise ValueError("content_hash must contain a 64-character SHA-256 hex digest")
    return hex_part


class FileBucketSourceIndex(SourceIndexBackend):
    """File-bucket implementation of SourceIndexBackend.

    Args:
        root: Repository / project root. Defaults to the
            ``NOETICBRAID_STATE_ROOT`` environment variable, falling back to
            ``Path.cwd()``.
    """

    def __init__(self, root: Optional[Path] = None) -> None:
        if root is None:
            env = os.environ.get(DEFAULT_STATE_ENV)
            root = Path(env) if env else Path.cwd()
        self._root = Path(root).resolve()
        self._dir = self._root / DEFAULT_RELATIVE_DIR
        self._dir.mkdir(parents=True, exist_ok=True)

    @property
    def directory(self) -> Path:
        """Return the root directory for bucketed source records."""

        return self._dir

    def _bucket_path(self, content_hash: str) -> Path:
        hex_part = _strip_prefix(content_hash)
        bucket = hex_part[:2]
        return self._dir / bucket / f"{hex_part}.json"

    def put(self, record: SourceRecord) -> None:
        """Atomically write a SourceRecord into its hash bucket."""

        path = self._bucket_path(record.content_hash)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(record.model_dump_json(), encoding="utf-8")
        os.replace(tmp, path)

    def get(self, content_hash: str) -> Optional[SourceRecord]:
        """Return the SourceRecord for ``content_hash``, if present and valid."""

        path = self._bucket_path(content_hash)
        if not path.exists():
            return None
        try:
            return SourceRecord.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - exact exception is pydantic-specific
            LOGGER.warning("SourceIndex: corrupted record %s: %s", path, exc)
            return None

    def find_by_url(self, url: str) -> Iterator[SourceRecord]:
        """Linearly scan bucket files for records whose canonical_url matches."""

        if not self._dir.exists():
            return
        for bucket in sorted(self._dir.iterdir()):
            if not bucket.is_dir():
                continue
            for entry in sorted(bucket.iterdir()):
                if entry.suffix != ".json":
                    continue
                try:
                    record = SourceRecord.model_validate_json(entry.read_text(encoding="utf-8"))
                except Exception as exc:  # pragma: no cover - exact exception is pydantic-specific
                    LOGGER.warning("SourceIndex.find_by_url: skipping %s: %s", entry, exc)
                    continue
                if record.canonical_url == url:
                    yield record

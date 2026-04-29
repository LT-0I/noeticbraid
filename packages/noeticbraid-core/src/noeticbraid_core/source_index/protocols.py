"""SourceIndex Protocol (Phase 1.1 Stage 2 GPT-B).

Phase 1.2 will add a SQLite backend without changing call sites.
"""

from __future__ import annotations

from typing import Iterator, Optional, Protocol, runtime_checkable

from noeticbraid_core.schemas import SourceRecord


@runtime_checkable
class SourceIndexBackend(Protocol):
    """Storage backend for SourceRecord lookup.

    Implementations:
        - FileBucketSourceIndex (Phase 1.1, file-bucket layout)
        - SqliteSourceIndex (Phase 1.2, planned)
    """

    def put(self, record: SourceRecord) -> None: ...

    def get(self, content_hash: str) -> Optional[SourceRecord]: ...

    def find_by_url(self, url: str) -> Iterator[SourceRecord]: ...

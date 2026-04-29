"""NoeticBraid Core source_index module (Stage 2 GPT-B)."""

from __future__ import annotations

from .protocols import SourceIndexBackend
from .source_index import FileBucketSourceIndex

__all__ = ["SourceIndexBackend", "FileBucketSourceIndex"]

# SPDX-License-Identifier: Apache-2.0
"""Credential-vault skeleton for DPAPI startup-token blobs."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from noeticbraid_backend.auth.dpapi import DpapiBlob
from noeticbraid_backend.settings import DPAPI_BLOB_PATH_ENV, PRIVATE_DPAPI_BLOB_PATH

LOGGER = logging.getLogger(__name__)


class CredentialVault:
    """Resolve a DPAPI blob path without reading or writing real secrets in Stage 1."""

    def __init__(self, blob_path: Path | None = None) -> None:
        self.blob_path = blob_path if blob_path is not None else self._resolve_default_path()

    def _resolve_default_path(self) -> Path | None:
        """Resolve env override or private-fork default; return None if unset."""

        explicit = os.environ.get(DPAPI_BLOB_PATH_ENV)
        if explicit:
            return Path(explicit)
        if Path("private").exists():
            return PRIVATE_DPAPI_BLOB_PATH
        return None

    def load_credential(self) -> DpapiBlob | None:
        """Load DPAPI blob from disk. Stage 1 returns None."""

        if self.blob_path and self.blob_path.exists():
            LOGGER.info("DPAPI blob path is present but real vault load is deferred to Stage 2")
        return None

    def store_credential(self, blob: DpapiBlob) -> None:
        """Store DPAPI blob. Stage 1 is a no-op."""

        del blob
        LOGGER.info("DPAPI blob store is deferred to Stage 2")


__all__ = ["CredentialVault"]

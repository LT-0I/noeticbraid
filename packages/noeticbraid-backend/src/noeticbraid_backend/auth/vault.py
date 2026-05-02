# SPDX-License-Identifier: Apache-2.0
"""Credential-vault boundary for DPAPI startup-token blobs."""

from __future__ import annotations

from pathlib import Path

from noeticbraid_backend.auth.dpapi import DpapiBlob


class CredentialVault:
    """Resolve and load a configured DPAPI blob path without exposing secrets."""

    def __init__(self, blob_path: Path | None = None) -> None:
        # Settings.from_env() is the only environment reader. A None vault path
        # means no configured startup credential blob for this app instance.
        self.blob_path = blob_path

    def load_credential(self) -> DpapiBlob | None:
        """Load a configured DPAPI ciphertext blob, or None when unavailable."""

        if self.blob_path is None:
            return None
        try:
            ciphertext = Path(self.blob_path).read_bytes()
        except OSError:
            return None
        if not ciphertext:
            return None
        return DpapiBlob(ciphertext=ciphertext)

    def store_credential(self, blob: DpapiBlob) -> None:
        """Store an opaque DPAPI blob at the explicitly configured path."""

        if self.blob_path is None:
            raise ValueError("blob_path must be configured before storing credentials")
        if not isinstance(blob, DpapiBlob):
            raise TypeError("blob must be a DpapiBlob")
        path = Path(self.blob_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(blob.ciphertext)


__all__ = ["CredentialVault"]

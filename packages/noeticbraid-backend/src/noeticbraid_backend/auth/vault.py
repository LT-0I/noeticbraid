# SPDX-License-Identifier: Apache-2.0
"""Credential-vault boundary for DPAPI startup-token blobs."""

from __future__ import annotations

import os
import secrets
import stat
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


def load_or_create_local_startup_secret(secret_path: Path) -> bytes | None:
    """Load or create a fail-closed portable startup secret."""

    create_fd: int | None = None
    load_fd: int | None = None
    try:
        path = Path(secret_path)
        parent = path.parent
        try:
            parent_stat = os.stat(parent)
        except FileNotFoundError:
            os.makedirs(parent, mode=0o700, exist_ok=True)
            os.chmod(parent, 0o700)
            parent_stat = os.stat(parent)
        if not stat.S_ISDIR(parent_stat.st_mode):
            return None
        if parent_stat.st_uid != os.geteuid():
            return None
        if stat.S_IMODE(parent_stat.st_mode) & 0o022 != 0:
            return None

        try:
            create_fd = os.open(
                path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
                0o600,
            )
            secret = secrets.token_urlsafe(32).encode()
            os.write(create_fd, secret)
            os.fchmod(create_fd, 0o600)
        except FileExistsError:
            pass
        finally:
            if create_fd is not None:
                try:
                    os.close(create_fd)
                finally:
                    create_fd = None

        load_fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
        secret_stat = os.fstat(load_fd)
        if not stat.S_ISREG(secret_stat.st_mode):
            return None
        if stat.S_IMODE(secret_stat.st_mode) & 0o077 != 0:
            return None
        if secret_stat.st_uid != os.geteuid():
            return None

        chunks: list[bytes] = []
        while True:
            chunk = os.read(load_fd, 4096)
            if not chunk:
                break
            chunks.append(chunk)
        secret = b"".join(chunks)
        if not secret.strip():
            return None
        return secret
    except Exception:
        return None
    finally:
        if create_fd is not None:
            try:
                os.close(create_fd)
            except OSError:
                pass
        if load_fd is not None:
            try:
                os.close(load_fd)
            except OSError:
                pass


__all__ = ["CredentialVault", "load_or_create_local_startup_secret"]

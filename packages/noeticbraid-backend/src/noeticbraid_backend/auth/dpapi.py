# SPDX-License-Identifier: Apache-2.0
"""ctypes-only DPAPI boundary skeleton.

Risk register for the deferred Stage 2 implementation:

- Buffer memory leak: always call LocalFree in a finally block for DPAPI output.
- Wrong DATA_BLOB lifetime: keep Python buffers alive while crypt32 uses them.
- GUI prompt deadlock: always pass CRYPTPROTECT_UI_FORBIDDEN.
- Non-Windows CI failure: tests exercise the NotImplementedError guard.
- Secret blob leak: use an env-controlled path and keep public repos blob-free.
- Error ambiguity: map GetLastError values to DpapiError with context.
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from dataclasses import dataclass


class DpapiError(RuntimeError):
    """Raised when a DPAPI call fails in the real Stage 2 implementation."""


@dataclass(frozen=True)
class DpapiBlob:
    """Opaque DPAPI ciphertext blob."""

    ciphertext: bytes


class DATA_BLOB(ctypes.Structure):
    """Windows CRYPTOAPI_BLOB shape; declared but not instantiated in Stage 1."""

    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_byte)),
    ]


CRYPTPROTECT_UI_FORBIDDEN = 0x1


def is_dpapi_available() -> bool:
    """Return True only on Windows, where DPAPI is available."""

    return sys.platform == "win32"


def _raise_stage1_not_implemented() -> None:
    """Raise the correct Stage 1 boundary error for the current platform."""

    if not is_dpapi_available():
        raise NotImplementedError(
            "DPAPI is Windows-only; non-Windows fallback deferred to Phase 1.3"
        )
    raise NotImplementedError("Real DPAPI ctypes implementation deferred to Stage 2 Lane A")


def protect_secret(plaintext: bytes, *, entropy: bytes | None = None) -> DpapiBlob:
    """Protect plaintext with DPAPI in Stage 2; Stage 1 raises NotImplementedError."""

    del plaintext, entropy
    _raise_stage1_not_implemented()


def unprotect_secret(blob: DpapiBlob, *, entropy: bytes | None = None) -> bytes:
    """Unprotect a DPAPI blob in Stage 2; Stage 1 raises NotImplementedError."""

    del blob, entropy
    _raise_stage1_not_implemented()

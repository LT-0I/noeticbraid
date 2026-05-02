# SPDX-License-Identifier: Apache-2.0
"""ctypes-only DPAPI boundary.

Risk controls:

- Buffer memory leak: LocalFree is called in a finally block for DPAPI output.
- DATA_BLOB lifetime: Python buffers stay live until crypt32 returns.
- GUI prompt deadlock: CRYPTPROTECT_UI_FORBIDDEN is always passed.
- Non-Windows CI safety: public tests use NotImplementedError or mocks only.
- Secret blob leak: callers supply explicit paths and this module never logs blobs.
- Error ambiguity: Windows failures are mapped to DpapiError with GetLastError.
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from dataclasses import dataclass


class DpapiError(RuntimeError):
    """Raised when a DPAPI call fails."""


@dataclass(frozen=True)
class DpapiBlob:
    """Opaque DPAPI ciphertext blob."""

    ciphertext: bytes


class DATA_BLOB(ctypes.Structure):
    """Windows CRYPTOAPI_BLOB shape used by CryptProtectData."""

    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_byte)),
    ]


CRYPTPROTECT_UI_FORBIDDEN = 0x1


def is_dpapi_available() -> bool:
    """Return True only on Windows, where DPAPI is available."""

    return sys.platform == "win32"


def protect_secret(plaintext: bytes, *, entropy: bytes | None = None) -> DpapiBlob:
    """Protect plaintext with Windows DPAPI."""

    _require_windows_dpapi()
    plaintext_bytes = _coerce_bytes(plaintext, "plaintext")
    entropy_blob, entropy_buffer = _optional_blob_from_bytes(entropy)
    input_blob, input_buffer = _blob_from_bytes(plaintext_bytes)
    output_blob = DATA_BLOB()
    crypt32, kernel32 = _windows_libraries()

    # Keep input_buffer and entropy_buffer referenced until after the crypt32 call.
    keep_alive = (input_buffer, entropy_buffer)
    try:
        ok = crypt32.CryptProtectData(
            ctypes.byref(input_blob),
            None,
            ctypes.byref(entropy_blob) if entropy_blob is not None else None,
            None,
            None,
            CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(output_blob),
        )
        if not ok:
            raise DpapiError(f"CryptProtectData failed; GetLastError={_get_last_error()}")
        return DpapiBlob(ciphertext=_copy_output_blob(output_blob))
    finally:
        del keep_alive
        _local_free(kernel32, output_blob)


def unprotect_secret(blob: DpapiBlob, *, entropy: bytes | None = None) -> bytes:
    """Unprotect a Windows DPAPI blob."""

    _require_windows_dpapi()
    if not isinstance(blob, DpapiBlob):
        raise TypeError("blob must be a DpapiBlob")
    ciphertext = _coerce_bytes(blob.ciphertext, "blob.ciphertext")
    entropy_blob, entropy_buffer = _optional_blob_from_bytes(entropy)
    input_blob, input_buffer = _blob_from_bytes(ciphertext)
    output_blob = DATA_BLOB()
    crypt32, kernel32 = _windows_libraries()

    keep_alive = (input_buffer, entropy_buffer)
    try:
        ok = crypt32.CryptUnprotectData(
            ctypes.byref(input_blob),
            None,
            ctypes.byref(entropy_blob) if entropy_blob is not None else None,
            None,
            None,
            CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(output_blob),
        )
        if not ok:
            raise DpapiError(f"CryptUnprotectData failed; GetLastError={_get_last_error()}")
        return _copy_output_blob(output_blob)
    finally:
        del keep_alive
        _local_free(kernel32, output_blob)


def _require_windows_dpapi() -> None:
    if not is_dpapi_available():
        raise NotImplementedError("DPAPI is Windows-only; non-Windows fallback is not available")


def _coerce_bytes(value: bytes, name: str) -> bytes:
    if not isinstance(value, (bytes, bytearray)):
        raise TypeError(f"{name} must be bytes")
    return bytes(value)


def _blob_from_bytes(data: bytes) -> tuple[DATA_BLOB, ctypes.Array[ctypes.c_char]]:
    buffer = ctypes.create_string_buffer(data if data else b"\0")
    return DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))), buffer


def _optional_blob_from_bytes(data: bytes | None) -> tuple[DATA_BLOB | None, object | None]:
    if data is None:
        return None, None
    coerced = _coerce_bytes(data, "entropy")
    return _blob_from_bytes(coerced)


def _windows_libraries() -> tuple[object, object]:
    win_dll = getattr(ctypes, "WinDLL", None)
    if win_dll is None:
        raise DpapiError("ctypes.WinDLL is unavailable; DPAPI requires Windows")
    crypt32 = win_dll("crypt32", use_last_error=True)
    kernel32 = win_dll("kernel32", use_last_error=True)
    return crypt32, kernel32


def _get_last_error() -> int:
    getter = getattr(ctypes, "get_last_error", None)
    if callable(getter):
        return int(getter())
    return 0


def _copy_output_blob(blob: DATA_BLOB) -> bytes:
    if not blob.pbData or blob.cbData == 0:
        return b""
    return bytes(ctypes.string_at(blob.pbData, int(blob.cbData)))


def _local_free(kernel32: object, blob: DATA_BLOB) -> None:
    if blob.pbData:
        kernel32.LocalFree(ctypes.cast(blob.pbData, ctypes.c_void_p))


__all__ = [
    "CRYPTPROTECT_UI_FORBIDDEN",
    "DATA_BLOB",
    "DpapiBlob",
    "DpapiError",
    "is_dpapi_available",
    "protect_secret",
    "unprotect_secret",
]

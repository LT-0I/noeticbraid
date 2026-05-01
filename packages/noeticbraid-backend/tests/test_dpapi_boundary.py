# SPDX-License-Identifier: Apache-2.0
"""DPAPI boundary skeleton tests."""

from __future__ import annotations

import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PACKAGE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import pytest

from noeticbraid_backend.auth import dpapi
from noeticbraid_backend.auth.dpapi import DATA_BLOB, DpapiBlob, DpapiError


def test_dpapi_availability_matches_platform() -> None:
    assert dpapi.is_dpapi_available() is (sys.platform == "win32")


def test_dpapi_blob_is_frozen() -> None:
    blob = DpapiBlob(ciphertext=b"cipher")
    assert blob.ciphertext == b"cipher"
    with pytest.raises(FrozenInstanceError):
        blob.ciphertext = b"other"  # type: ignore[misc]


def test_data_blob_shape_is_declared_but_not_used() -> None:
    assert DATA_BLOB._fields_[0][0] == "cbData"
    assert DATA_BLOB._fields_[1][0] == "pbData"
    assert issubclass(DpapiError, RuntimeError)


def test_stage1_dpapi_functions_raise_clear_not_implemented() -> None:
    message = (
        "Real DPAPI ctypes implementation deferred to Stage 2 Lane A"
        if sys.platform == "win32"
        else "DPAPI is Windows-only; non-Windows fallback deferred to Phase 1.3"
    )
    with pytest.raises(NotImplementedError, match=message):
        dpapi.protect_secret(b"plaintext")
    with pytest.raises(NotImplementedError, match=message):
        dpapi.unprotect_secret(DpapiBlob(ciphertext=b"cipher"))

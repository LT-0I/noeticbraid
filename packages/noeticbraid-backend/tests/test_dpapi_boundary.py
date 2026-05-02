# SPDX-License-Identifier: Apache-2.0
"""DPAPI boundary tests using non-Windows guards and ctypes mocks."""

from __future__ import annotations

import ctypes
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import SimpleNamespace

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PACKAGE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import pytest

from noeticbraid_backend.auth import dpapi
from noeticbraid_backend.auth.dpapi import (
    CRYPTPROTECT_UI_FORBIDDEN,
    DATA_BLOB,
    DpapiBlob,
    DpapiError,
)


def test_dpapi_availability_matches_platform() -> None:
    assert dpapi.is_dpapi_available() is (sys.platform == "win32")


def test_dpapi_blob_is_frozen() -> None:
    blob = DpapiBlob(ciphertext=b"cipher")
    assert blob.ciphertext == b"cipher"
    with pytest.raises(FrozenInstanceError):
        blob.ciphertext = b"other"  # type: ignore[misc]


def test_data_blob_shape_is_declared_for_windows_cryptoapi() -> None:
    assert DATA_BLOB._fields_[0][0] == "cbData"
    assert DATA_BLOB._fields_[1][0] == "pbData"
    assert CRYPTPROTECT_UI_FORBIDDEN == 0x1
    assert issubclass(DpapiError, RuntimeError)


def test_non_windows_dpapi_functions_raise_clear_not_implemented(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dpapi.sys, "platform", "linux")

    with pytest.raises(NotImplementedError, match="DPAPI is Windows-only"):
        dpapi.protect_secret(b"plaintext")
    with pytest.raises(NotImplementedError, match="DPAPI is Windows-only"):
        dpapi.unprotect_secret(DpapiBlob(ciphertext=b"cipher"))


def _fake_windll_for_success(output: bytes, *, protect: bool = True):
    output_buffer = ctypes.create_string_buffer(output)
    output_pointer = ctypes.cast(output_buffer, ctypes.POINTER(ctypes.c_byte))
    calls: list[tuple[str, int]] = []
    frees: list[ctypes.c_void_p] = []

    def _set_output(out_blob_ptr) -> None:
        out_blob = out_blob_ptr._obj
        out_blob.cbData = len(output)
        out_blob.pbData = output_pointer

    def crypt_protect(input_blob_ptr, description, entropy_ptr, reserved, prompt, flags, output_blob_ptr):
        del input_blob_ptr, description, entropy_ptr, reserved, prompt
        calls.append(("protect", flags))
        _set_output(output_blob_ptr)
        return 1

    def crypt_unprotect(input_blob_ptr, description_ptr, entropy_ptr, reserved, prompt, flags, output_blob_ptr):
        del input_blob_ptr, description_ptr, entropy_ptr, reserved, prompt
        calls.append(("unprotect", flags))
        _set_output(output_blob_ptr)
        return 1

    def local_free(pointer):
        frees.append(pointer)
        return None

    crypt32 = SimpleNamespace(
        CryptProtectData=crypt_protect if protect else (lambda *args: 0),
        CryptUnprotectData=crypt_unprotect,
    )
    kernel32 = SimpleNamespace(LocalFree=local_free)
    return SimpleNamespace(crypt32=crypt32, kernel32=kernel32), calls, frees, output_buffer


def _install_fake_windows_libraries(monkeypatch: pytest.MonkeyPatch, windll) -> None:
    def win_dll(name: str, *, use_last_error: bool = False):
        del use_last_error
        return getattr(windll, name)

    monkeypatch.setattr(dpapi.ctypes, "windll", windll, raising=False)
    monkeypatch.setattr(dpapi.ctypes, "WinDLL", win_dll, raising=False)


def test_windows_libraries_load_with_use_last_error(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, bool]] = []

    def win_dll(name: str, *, use_last_error: bool = False):
        calls.append((name, use_last_error))
        return name

    monkeypatch.setattr(
        dpapi.ctypes,
        "windll",
        SimpleNamespace(crypt32=object(), kernel32=object()),
        raising=False,
    )
    monkeypatch.setattr(dpapi.ctypes, "WinDLL", win_dll, raising=False)

    crypt32, kernel32 = dpapi._windows_libraries()

    assert (crypt32, kernel32) == ("crypt32", "kernel32")
    assert calls == [("crypt32", True), ("kernel32", True)]


def test_windows_protect_secret_uses_cryptprotectdata_and_localfree(monkeypatch: pytest.MonkeyPatch) -> None:
    windll, calls, frees, _buffer = _fake_windll_for_success(b"ciphertext")
    monkeypatch.setattr(dpapi.sys, "platform", "win32")
    _install_fake_windows_libraries(monkeypatch, windll)

    blob = dpapi.protect_secret(b"plaintext")

    assert blob == DpapiBlob(ciphertext=b"ciphertext")
    assert calls == [("protect", CRYPTPROTECT_UI_FORBIDDEN)]
    assert len(frees) == 1


def test_windows_unprotect_secret_uses_cryptunprotectdata_and_localfree(monkeypatch: pytest.MonkeyPatch) -> None:
    windll, calls, frees, _buffer = _fake_windll_for_success(b"plaintext")
    monkeypatch.setattr(dpapi.sys, "platform", "win32")
    _install_fake_windows_libraries(monkeypatch, windll)

    plaintext = dpapi.unprotect_secret(DpapiBlob(ciphertext=b"ciphertext"))

    assert plaintext == b"plaintext"
    assert calls == [("unprotect", CRYPTPROTECT_UI_FORBIDDEN)]
    assert len(frees) == 1


def test_windows_dpapi_failure_maps_to_dpapi_error_with_last_error(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    def crypt_protect(*args):
        calls.append(args[-2])
        return 0

    windll = SimpleNamespace(
        crypt32=SimpleNamespace(CryptProtectData=crypt_protect),
        kernel32=SimpleNamespace(LocalFree=lambda pointer: None),
    )
    monkeypatch.setattr(dpapi.sys, "platform", "win32")
    _install_fake_windows_libraries(monkeypatch, windll)
    monkeypatch.setattr(dpapi.ctypes, "get_last_error", lambda: 1234, raising=False)

    with pytest.raises(DpapiError, match="CryptProtectData failed; GetLastError=1234"):
        dpapi.protect_secret(b"plaintext")

    assert calls == [CRYPTPROTECT_UI_FORBIDDEN]

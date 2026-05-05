"""Byte-equal regression checks for frozen contract 1.2.0 artifacts."""

from __future__ import annotations

import hashlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
CONTRACT_DIR = REPO_ROOT / "docs" / "contracts"


def _sha256_upper(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def test_phase1_2_openapi_byte_equal() -> None:
    assert (
        _sha256_upper(CONTRACT_DIR / "phase1_2_openapi.yaml")
        == "96CE4BAC5E3C9F1C976E21BC68D32FF2BA02C5EF9FE16BB8189EB3FBFBF839B7"
    )


def test_vault_layout_byte_equal() -> None:
    assert (
        _sha256_upper(CONTRACT_DIR / "vault_layout.yaml")
        == "CCB2D878A8200E13267DF0FDCDF25844084E4F517F711EC47858F8FBCF533D91"
    )

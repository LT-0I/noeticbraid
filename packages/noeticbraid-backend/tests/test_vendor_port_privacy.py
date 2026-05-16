# SPDX-License-Identifier: Apache-2.0
# ruff: noqa: E402
"""Parity tests for additive privacy vendor-port adapters."""

from __future__ import annotations

import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parent.parent
SRC_ROOT = PACKAGE_ROOT / "src"
CORE_SRC_ROOT = REPO_ROOT / "packages" / "noeticbraid-core" / "src"
for path in (CORE_SRC_ROOT, SRC_ROOT, REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from noeticbraid_backend.privacy.scrub import REDACTED, luhn_ok, scrub_pii


def test_scrub_pii_redacts_upstream_regex_families() -> None:
    jwt = "eyJabcdefgh.abcdefghijk.klmnopqrst"
    text = (
        "Email a.person@example.com or call +1 415-555-1212. "
        "SSN 123-45-6789. Card 4111 1111 1111 1111. "
        f"Authorization: Bearer abcdefghijklmnop. JWT {jwt}."
    )

    scrubbed = scrub_pii(text)

    assert "a.person@example.com" not in scrubbed
    assert "+1 415-555-1212" not in scrubbed
    assert "123-45-6789" not in scrubbed
    assert "4111 1111 1111 1111" not in scrubbed
    assert jwt not in scrubbed
    assert f"Bearer {REDACTED}" in scrubbed
    assert scrubbed.count(REDACTED) >= 6


def test_luhn_guard_leaves_invalid_card_shaped_numbers() -> None:
    assert luhn_ok("4111111111111111")
    assert not luhn_ok("4111111111111112")
    assert "4111 1111 1111 1112" in scrub_pii("Order 4111 1111 1111 1112")

# SPDX-License-Identifier: Apache-2.0
"""PII scrubber ported from gbrain eval-capture-scrub."""

from __future__ import annotations

import re

REDACTED = "[REDACTED]"
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(
    r"(?<!\d)(?:\+\d{1,3}[\s.-]?)?(?:\(\d{3}\)\s?|\d{3}[\s.-])\d{3}[\s.-]?\d{4}(?!\d)"
)
SSN_RE = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")
JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")
BEARER_RE = re.compile(r"\b(?:bearer|Bearer)\s+[A-Za-z0-9._~+/-]{10,}=*")
CC_RE = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")


def luhn_ok(digits: str) -> bool:
    """Return true when the digit sequence passes Luhn mod-10."""

    total = 0
    parity = len(digits) % 2
    for index, char in enumerate(digits):
        number = ord(char) - 48
        if number < 0 or number > 9:
            return False
        if index % 2 == parity:
            number *= 2
            if number > 9:
                number -= 9
        total += number
    return total % 10 == 0


def _redact_card(match: re.Match[str]) -> str:
    digits_only = re.sub(r"\D", "", match.group(0))
    if len(digits_only) < 13 or len(digits_only) > 19:
        return match.group(0)
    return REDACTED if luhn_ok(digits_only) else match.group(0)


def scrub_pii(input_text: str) -> str:
    """Redact obvious PII from captured query text."""

    if not input_text:
        return input_text
    out = EMAIL_RE.sub(REDACTED, input_text)
    out = PHONE_RE.sub(REDACTED, out)
    out = SSN_RE.sub(REDACTED, out)
    out = JWT_RE.sub(REDACTED, out)
    out = BEARER_RE.sub(f"Bearer {REDACTED}", out)
    return CC_RE.sub(_redact_card, out)


__all__ = [
    "BEARER_RE",
    "CC_RE",
    "EMAIL_RE",
    "JWT_RE",
    "PHONE_RE",
    "REDACTED",
    "SSN_RE",
    "luhn_ok",
    "scrub_pii",
]

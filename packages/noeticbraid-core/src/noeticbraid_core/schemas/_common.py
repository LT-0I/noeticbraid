"""Shared schema helpers for NoeticBraid Phase 1.1 Stage 1 candidates."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional

from pydantic import ConfigDict

COMMON_MODEL_CONFIG = ConfigDict(
    extra="forbid",
    frozen=False,
    str_strip_whitespace=True,
    validate_assignment=True,
)


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


def ensure_utc_datetime(value: datetime) -> datetime:
    """Normalize datetimes to timezone-aware UTC.

    Naive datetimes are treated as UTC because Phase 1.1 local ledgers need a
    stable default without silently rejecting user-entered timestamps.
    """

    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def ensure_optional_utc_datetime(value: Optional[datetime]) -> Optional[datetime]:
    """Normalize an optional datetime to timezone-aware UTC."""

    if value is None:
        return None
    return ensure_utc_datetime(value)


def empty_str_to_none(value: object) -> object:
    """Convert blank optional string inputs to None while preserving other values."""

    if isinstance(value, str) and value.strip() == "":
        return None
    return value


def validate_prefixed_identifier(value: str, *, prefix: str, field_name: str) -> str:
    """Validate a stable identifier prefix and conservative character set."""

    pattern = rf"^{re.escape(prefix)}[A-Za-z0-9_]+$"
    if not re.fullmatch(pattern, value):
        raise ValueError(f"{field_name} must match {pattern}")
    return value


def validate_optional_prefixed_identifier(
    value: Optional[str], *, prefix: str, field_name: str
) -> Optional[str]:
    """Validate an optional stable identifier if it is present."""

    if value is None:
        return None
    return validate_prefixed_identifier(value, prefix=prefix, field_name=field_name)


def validate_ref_list(values: list[str], *, prefix: str, field_name: str) -> list[str]:
    """Validate a list of prefixed references and reject duplicate entries."""

    seen: set[str] = set()
    for item in values:
        validate_prefixed_identifier(item, prefix=prefix, field_name=field_name)
        if item in seen:
            raise ValueError(f"{field_name} must not contain duplicate references")
        seen.add(item)
    return values

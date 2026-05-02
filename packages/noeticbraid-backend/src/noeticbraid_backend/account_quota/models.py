# SPDX-License-Identifier: Apache-2.0
"""Private account/quota models and sanitized public summaries."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

AccountStatus = Literal["available", "quota_low", "cooldown", "login_required", "disabled", "unknown"]
RemainingEstimate = Literal["high", "medium", "low", "exhausted", "unknown"]
QuotaEventType = Literal["usage_recorded", "quota_signal", "state_updated"]

_LEGACY_ALIAS_KEY = "account" + "_id"
_LEGACY_BROWSER_LABEL_KEY = "profile_directory"
_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")
_SAFE_TEXT_RE = re.compile(r"[^A-Za-z0-9_.: -]+")


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""

    return datetime.now(timezone.utc)


class AccountRegistryRecord(BaseModel):
    """Private account registry record loaded from local runtime state."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    alias: str = Field(..., min_length=1, max_length=128, validation_alias=AliasChoices("alias", _LEGACY_ALIAS_KEY))
    provider: str = Field(..., min_length=1, max_length=64)
    enabled: bool = True
    priority: int = Field(default=0, ge=0)
    capabilities: list[str] = Field(default_factory=list)
    notes: str | None = Field(default=None, max_length=512)
    browser_profile_label: str | None = Field(
        default=None,
        max_length=128,
        validation_alias=AliasChoices("browser_profile_label", _LEGACY_BROWSER_LABEL_KEY),
    )

    @field_validator("alias", "provider")
    @classmethod
    def _validate_safe_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must be non-empty")
        if not _SAFE_NAME_RE.fullmatch(value):
            raise ValueError("value must contain only safe label characters")
        return value

    @field_validator("capabilities")
    @classmethod
    def _normalize_capabilities(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            if not isinstance(item, str):
                raise ValueError("capabilities must be strings")
            capability = item.strip()
            if not capability:
                raise ValueError("capabilities must be non-empty strings")
            if not _SAFE_NAME_RE.fullmatch(capability):
                raise ValueError("capabilities must contain only safe label characters")
            if capability not in seen:
                normalized.append(capability)
                seen.add(capability)
        return normalized

    @field_validator("notes")
    @classmethod
    def _normalize_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("browser_profile_label")
    @classmethod
    def _validate_browser_profile_label(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        if "/" in value or "\\" in value or ":" in value:
            raise ValueError("browser profile label must not be a filesystem path")
        return value


class QuotaStateRecord(BaseModel):
    """Private latest quota state for one alias."""

    model_config = ConfigDict(extra="forbid")

    status: AccountStatus = "unknown"
    remaining_estimate: RemainingEstimate = "unknown"
    cooldown_until: datetime | None = None
    last_signal: str | None = Field(default=None, max_length=128)
    last_checked_at: datetime | None = None
    last_used_at: datetime | None = None
    usage_count: int = Field(default=0, ge=0)
    usage_window_started_at: datetime | None = None
    usage_limit_estimate: int | None = Field(default=None, ge=0)

    @field_validator("cooldown_until", "last_checked_at", "last_used_at", "usage_window_started_at")
    @classmethod
    def _ensure_aware_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @field_validator("last_signal")
    @classmethod
    def _sanitize_last_signal(cls, value: str | None) -> str | None:
        return sanitize_reason(value)


class QuotaEventRecord(BaseModel):
    """Append-only private quota event."""

    model_config = ConfigDict(extra="forbid")

    alias: str = Field(..., min_length=1, max_length=128)
    event_type: QuotaEventType
    source: str = Field(..., min_length=1, max_length=64)
    run_id: str | None = Field(default=None, max_length=128)
    created_at: datetime = Field(default_factory=utc_now)
    observed_text_hash: str | None = Field(default=None, min_length=64, max_length=64)
    sanitized_reason: str | None = Field(default=None, max_length=160)

    @field_validator("alias", "source")
    @classmethod
    def _validate_safe_name(cls, value: str) -> str:
        value = value.strip()
        if not value or not _SAFE_NAME_RE.fullmatch(value):
            raise ValueError("value must contain only safe label characters")
        return value

    @field_validator("run_id")
    @classmethod
    def _normalize_run_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        if not _SAFE_NAME_RE.fullmatch(value):
            raise ValueError("run_id must contain only safe label characters")
        return value

    @field_validator("created_at")
    @classmethod
    def _ensure_created_at_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @field_validator("observed_text_hash")
    @classmethod
    def _validate_observed_text_hash(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().lower()
        if not re.fullmatch(r"[0-9a-f]{64}", value):
            raise ValueError("observed_text_hash must be a SHA-256 hex digest")
        return value

    @field_validator("sanitized_reason")
    @classmethod
    def _sanitize_reason_field(cls, value: str | None) -> str | None:
        return sanitize_reason(value)


class PublicProfileSummary(BaseModel):
    """Sanitized profile summary suitable for AccountPoolDraft.profiles."""

    model_config = ConfigDict(extra="forbid")

    alias: str
    provider: str
    status: AccountStatus
    remaining_estimate: RemainingEstimate
    cooldown_until: datetime | None = None
    capabilities: list[str] = Field(default_factory=list)
    last_used_at: datetime | None = None



def observed_text_digest(observed_text: str | None) -> str | None:
    """Hash observed UI/error text without persisting raw text."""

    if observed_text is None:
        return None
    return hashlib.sha256(observed_text.encode("utf-8")).hexdigest()


def sanitize_reason(value: str | None) -> str | None:
    """Return a compact non-secret reason label."""

    if value is None:
        return None
    value = _SAFE_TEXT_RE.sub("_", value.strip())
    value = " ".join(value.split())
    if not value:
        return None
    return value[:160]


def public_summary_from(account: AccountRegistryRecord, state: QuotaStateRecord | None) -> PublicProfileSummary:
    """Build a sanitized public summary from private registry and state."""

    effective_state = state or QuotaStateRecord()
    status: AccountStatus = effective_state.status
    if not account.enabled:
        status = "disabled"
    return PublicProfileSummary(
        alias=account.alias,
        provider=account.provider,
        status=status,
        remaining_estimate=effective_state.remaining_estimate,
        cooldown_until=effective_state.cooldown_until,
        capabilities=list(account.capabilities),
        last_used_at=effective_state.last_used_at,
    )


__all__ = [
    "AccountRegistryRecord",
    "AccountStatus",
    "PublicProfileSummary",
    "QuotaEventRecord",
    "QuotaEventType",
    "QuotaStateRecord",
    "RemainingEstimate",
    "observed_text_digest",
    "public_summary_from",
    "sanitize_reason",
    "utc_now",
]

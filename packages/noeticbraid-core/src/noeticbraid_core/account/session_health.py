# SPDX-License-Identifier: Apache-2.0
"""Session-health probe protocol and recording helpers.

SP-C1 does not start browsers, read cookies, or inspect browser profiles. A caller may
provide a probe that returns sanitized observations; this module validates those
observations, hashes raw text when supplied, and records only module-local quota state.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from noeticbraid_core.account.models import (
    AccountRegistryRecord,
    AccountStatus,
    QuotaEventRecord,
    QuotaStateRecord,
    RemainingEstimate,
    _aware_utc as _as_aware_utc,
    observed_text_digest,
    sanitize_reason,
    utc_now,
)
from noeticbraid_core.account.store import AccountQuotaStore


class SessionHealthRecord(BaseModel):
    """Module-local health record for one account session.

    `observed_text` is accepted only as an input convenience. It is excluded from
    serialization and converted to `observed_text_hash` so raw UI/session text is not
    persisted or returned through public adapters.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    alias: str = Field(..., min_length=1, max_length=128)
    status: AccountStatus
    checked_at: datetime = Field(default_factory=utc_now)
    source: str = Field(..., min_length=1, max_length=64)
    sanitized_reason: str | None = Field(default=None, max_length=160)
    observed_text_hash: str | None = Field(default=None, min_length=64, max_length=64)
    cooldown_until: datetime | None = None
    observed_text: str | None = Field(default=None, exclude=True, repr=False)

    @field_validator("checked_at", "cooldown_until")
    @classmethod
    def _ensure_aware_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return _as_aware_utc(value)

    @field_validator("sanitized_reason")
    @classmethod
    def _sanitize_reason(cls, value: str | None) -> str | None:
        return sanitize_reason(value)

    @model_validator(mode="before")
    @classmethod
    def _hash_observed_text(cls, data: object) -> object:
        if isinstance(data, dict) and data.get("observed_text") and data.get("observed_text_hash") is None:
            payload = dict(data)
            payload["observed_text_hash"] = observed_text_digest(str(payload["observed_text"]))
            return payload
        return data


class SessionHealthProbe(Protocol):
    """Protocol for caller-owned session checks.

    Implementations must not expose cookies, credentials, browser profile paths, or raw
    account artifacts. Return `SessionHealthRecord` with sanitized fields only.
    """

    def check(self, account: AccountRegistryRecord) -> SessionHealthRecord:
        """Return a health record for `account`."""


def check_session_health(
    account: AccountRegistryRecord,
    probe: SessionHealthProbe,
    *,
    now_fn: Callable[[], datetime] = utc_now,
) -> SessionHealthRecord:
    """Run a caller-provided probe and validate the sanitized result.

    The probe is intentionally injected. SP-C1 never launches or controls browser/C2
    runtime components.
    """

    raw = probe.check(account)
    if isinstance(raw, SessionHealthRecord):
        record = raw
    else:
        payload = dict(raw)
        payload.setdefault("checked_at", _as_aware_utc(now_fn()))
        record = SessionHealthRecord.model_validate(payload)
    if record.alias != account.alias:
        raise ValueError(f"probe returned alias {record.alias!r} for account {account.alias!r}")
    return record


def record_session_health(
    store: AccountQuotaStore,
    record: SessionHealthRecord,
    *,
    run_id: str | None = None,
) -> QuotaStateRecord:
    """Persist a health record as quota state plus a quota_signal event."""

    aliases = {account.alias for account in store.load_registry()}
    if record.alias not in aliases:
        raise ValueError(f"unknown account alias {record.alias}")

    signal = record.sanitized_reason or record.status

    def _updater(state: dict[str, QuotaStateRecord]) -> None:
        current = state.get(record.alias, QuotaStateRecord())
        remaining_estimate = _estimate_for_health(record, current.remaining_estimate)
        state[record.alias] = current.model_copy(
            update={
                "status": record.status,
                "remaining_estimate": remaining_estimate,
                "cooldown_until": record.cooldown_until if record.cooldown_until is not None else current.cooldown_until,
                "last_signal": signal,
                "last_checked_at": record.checked_at,
            }
        )

    state_after = store.update_state(_updater)
    updated = state_after[record.alias]
    store.append_event(
        QuotaEventRecord(
            alias=record.alias,
            event_type="quota_signal",
            source=record.source,
            run_id=run_id,
            created_at=record.checked_at,
            observed_text_hash=record.observed_text_hash,
            sanitized_reason=signal,
        )
    )
    return updated


def _estimate_for_health(record: SessionHealthRecord, current: RemainingEstimate) -> RemainingEstimate:
    reason = (record.sanitized_reason or "").lower()
    if record.status == "available":
        return current if current != "unknown" else "high"
    if record.status == "quota_low":
        return "exhausted" if "exhaust" in reason else "low"
    if record.status == "cooldown":
        return "low"
    return current


__all__ = [
    "SessionHealthProbe",
    "SessionHealthRecord",
    "check_session_health",
    "record_session_health",
]

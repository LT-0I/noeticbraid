# SPDX-License-Identifier: Apache-2.0
"""Deterministic account selection and quota enforcement helpers."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timezone

from noeticbraid_backend.account_quota.models import (
    AccountRegistryRecord,
    AccountStatus,
    QuotaEventRecord,
    QuotaStateRecord,
    RemainingEstimate,
    observed_text_digest,
    sanitize_reason,
    utc_now,
)
from noeticbraid_backend.account_quota.store import AccountQuotaStore


class AccountQuotaEnforcementError(Exception):
    """Base exception for account/quota enforcement decisions."""


class NoAvailableAccountError(AccountQuotaEnforcementError):
    """Raised when no private account can satisfy the requested work."""


class UnknownAccountError(AccountQuotaEnforcementError):
    """Raised when quota usage is recorded for an alias outside the registry."""


class QuotaLimitExceeded(AccountQuotaEnforcementError):
    """Raised when a preflight usage estimate would exceed the local limit."""


@dataclass(frozen=True)
class AccountSelection:
    """Sanitized account selection returned to future adapters."""

    alias: str
    provider: str
    status: AccountStatus
    remaining_estimate: RemainingEstimate
    capabilities: tuple[str, ...]
    reason: str


class AccountQuotaEnforcer:
    """Select accounts and mutate quota state through AccountQuotaStore only."""

    def __init__(self, store: AccountQuotaStore, *, now_fn: Callable[[], datetime] = utc_now) -> None:
        self.store = store
        self._now_fn = now_fn

    def select_account(
        self,
        required_capabilities: Iterable[str] | None = None,
        *,
        planned_increment: int = 1,
    ) -> AccountSelection:
        """Return the best available account or fail closed with a typed error."""

        required = _normalize_required_capabilities(required_capabilities)
        _validate_increment(planned_increment)
        registry = self.store.load_registry()
        state_by_alias = self.store.load_state()
        now = self._now()
        candidates: list[tuple[tuple[object, ...], AccountRegistryRecord, QuotaStateRecord]] = []
        for account in registry:
            state = state_by_alias.get(account.alias, QuotaStateRecord())
            if not account.enabled or state.status == "disabled":
                continue
            if state.status == "login_required":
                continue
            if _active_cooldown(state, now):
                continue
            if state.remaining_estimate == "exhausted":
                continue
            if not required.issubset(set(account.capabilities)):
                continue
            if _would_limit_state(state, planned_increment):
                continue
            candidates.append((self._selection_key(account, state, required), account, state))
        if not candidates:
            raise NoAvailableAccountError("no available account satisfies quota and capability constraints")
        _key, account, state = sorted(candidates, key=lambda item: item[0])[0]
        return AccountSelection(
            alias=account.alias,
            provider=account.provider,
            status=state.status,
            remaining_estimate=state.remaining_estimate,
            capabilities=tuple(account.capabilities),
            reason="selected_by_health_capability_priority_quota_recency",
        )

    def would_limit(self, alias: str, *, planned_increment: int = 1) -> bool:
        """Return True when usage_count + planned_increment would exceed the limit estimate."""

        _validate_increment(planned_increment)
        state = self.store.load_state().get(alias, QuotaStateRecord())
        return _would_limit_state(state, planned_increment)

    def preflight_usage(self, alias: str, *, planned_increment: int = 1) -> None:
        """Fail before work begins if the local usage limit estimate would be exceeded."""

        self._require_registered_alias(alias)
        if self.would_limit(alias, planned_increment=planned_increment):
            raise QuotaLimitExceeded(f"usage limit estimate would be exceeded for alias {alias}")

    def record_usage(
        self,
        alias: str,
        *,
        source: str,
        run_id: str | None = None,
        planned_increment: int = 1,
    ) -> QuotaStateRecord:
        """Increment per-alias usage state and append an event."""

        self.preflight_usage(alias, planned_increment=planned_increment)
        now = self._now()
        state = self.store.load_state()
        current = state.get(alias, QuotaStateRecord())
        usage_count = current.usage_count + planned_increment
        usage_window_started_at = current.usage_window_started_at or now
        remaining_estimate = _estimate_after_usage(usage_count, current.usage_limit_estimate, current.remaining_estimate)
        updated = current.model_copy(
            update={
                "status": _status_after_usage(current.status, remaining_estimate),
                "remaining_estimate": remaining_estimate,
                "last_signal": "usage_recorded",
                "last_checked_at": now,
                "last_used_at": now,
                "usage_count": usage_count,
                "usage_window_started_at": usage_window_started_at,
            }
        )
        state[alias] = updated
        self.store.write_state(state)
        self.store.append_event(
            QuotaEventRecord(
                alias=alias,
                event_type="usage_recorded",
                source=source,
                run_id=run_id,
                created_at=now,
                sanitized_reason="usage_recorded",
            )
        )
        return updated

    def record_quota_signal(
        self,
        alias: str,
        *,
        signal: str,
        source: str,
        run_id: str | None = None,
        observed_text: str | None = None,
        cooldown_until: datetime | None = None,
    ) -> QuotaStateRecord:
        """Record a quota signal without persisting raw observed text."""

        self._require_registered_alias(alias)
        now = self._now()
        normalized_signal = sanitize_reason(signal) or "unknown"
        observed_hash = observed_text_digest(observed_text)
        state = self.store.load_state()
        current = state.get(alias, QuotaStateRecord())
        status, remaining_estimate = _classify_signal(normalized_signal, cooldown_until, current.remaining_estimate)
        updated = current.model_copy(
            update={
                "status": status,
                "remaining_estimate": remaining_estimate,
                "cooldown_until": _as_aware_utc(cooldown_until) if cooldown_until is not None else current.cooldown_until,
                "last_signal": normalized_signal,
                "last_checked_at": now,
            }
        )
        state[alias] = updated
        self.store.write_state(state)
        self.store.append_event(
            QuotaEventRecord(
                alias=alias,
                event_type="quota_signal",
                source=source,
                run_id=run_id,
                created_at=now,
                observed_text_hash=observed_hash,
                sanitized_reason=normalized_signal,
            )
        )
        return updated

    def _selection_key(
        self,
        account: AccountRegistryRecord,
        state: QuotaStateRecord,
        required: frozenset[str],
    ) -> tuple[object, ...]:
        capability_match_score = len(required.intersection(account.capabilities))
        return (
            _health_rank(state.status),
            -capability_match_score,
            -account.priority,
            _estimate_rank(state.remaining_estimate),
            _recency_rank(state.last_used_at),
            account.alias,
        )

    def _require_registered_alias(self, alias: str) -> None:
        aliases = {account.alias for account in self.store.load_registry()}
        if alias not in aliases:
            raise UnknownAccountError(f"unknown account alias {alias}")

    def _now(self) -> datetime:
        return _as_aware_utc(self._now_fn())


def _normalize_required_capabilities(required_capabilities: Iterable[str] | None) -> frozenset[str]:
    if required_capabilities is None:
        return frozenset()
    required: set[str] = set()
    for item in required_capabilities:
        capability = item.strip()
        if capability:
            required.add(capability)
    return frozenset(required)


def _validate_increment(planned_increment: int) -> None:
    if planned_increment <= 0:
        raise ValueError("planned_increment must be positive")


def _would_limit_state(state: QuotaStateRecord, planned_increment: int) -> bool:
    if state.usage_limit_estimate is None:
        return False
    return state.usage_count + planned_increment > state.usage_limit_estimate


def _active_cooldown(state: QuotaStateRecord, now: datetime) -> bool:
    if state.status != "cooldown":
        return False
    if state.cooldown_until is None:
        return True
    return _as_aware_utc(state.cooldown_until) > now


def _health_rank(status: AccountStatus) -> int:
    return {
        "available": 0,
        "quota_low": 1,
        "unknown": 2,
        "cooldown": 3,
        "login_required": 9,
        "disabled": 9,
    }[status]


def _estimate_rank(estimate: RemainingEstimate) -> int:
    return {
        "high": 0,
        "medium": 1,
        "low": 2,
        "unknown": 3,
        "exhausted": 4,
    }[estimate]


def _recency_rank(last_used_at: datetime | None) -> datetime:
    if last_used_at is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    return _as_aware_utc(last_used_at)


def _estimate_after_usage(
    usage_count: int,
    usage_limit_estimate: int | None,
    current: RemainingEstimate,
) -> RemainingEstimate:
    if usage_limit_estimate is None or usage_limit_estimate == 0:
        return current if current != "unknown" else "unknown"
    remaining = usage_limit_estimate - usage_count
    if remaining <= 0:
        return "exhausted"
    ratio = remaining / usage_limit_estimate
    if ratio <= 0.2:
        return "low"
    if ratio <= 0.5:
        return "medium"
    return "high"


def _status_after_usage(status: AccountStatus, estimate: RemainingEstimate) -> AccountStatus:
    if status in {"disabled", "login_required", "cooldown"}:
        return status
    if estimate in {"low", "exhausted"}:
        return "quota_low"
    return "available"


def _classify_signal(
    signal: str,
    cooldown_until: datetime | None,
    current_estimate: RemainingEstimate,
) -> tuple[AccountStatus, RemainingEstimate]:
    lowered = signal.lower()
    if "login" in lowered or "session" in lowered:
        return "login_required", current_estimate
    if cooldown_until is not None or "cooldown" in lowered:
        return "cooldown", "low"
    if "exhaust" in lowered:
        return "quota_low", "exhausted"
    if "quota" in lowered or "limit" in lowered or "rate" in lowered:
        return "quota_low", "low"
    if "available" in lowered or "manual_ok" in lowered:
        return "available", current_estimate
    return "unknown", current_estimate


def _as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


__all__ = [
    "AccountQuotaEnforcer",
    "AccountQuotaEnforcementError",
    "AccountSelection",
    "NoAvailableAccountError",
    "QuotaLimitExceeded",
    "UnknownAccountError",
]

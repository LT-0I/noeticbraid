# SPDX-License-Identifier: Apache-2.0
"""Tests for deterministic account quota enforcement."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from noeticbraid_backend.account_quota.enforcer import (
    AccountQuotaEnforcer,
    NoAvailableAccountError,
    QuotaLimitExceeded,
)
from noeticbraid_backend.account_quota.models import QuotaStateRecord
from noeticbraid_backend.account_quota.store import AccountQuotaStore
from noeticbraid_backend.settings import Settings

NOW = datetime(2026, 5, 2, 20, 0, tzinfo=timezone.utc)


def _store(tmp_path: Path) -> AccountQuotaStore:
    settings = Settings(state_dir=tmp_path / "state", dpapi_blob_path=None)
    return AccountQuotaStore.from_settings(settings)


def _write_registry(store: AccountQuotaStore, accounts: list[dict[str, object]]) -> None:
    store.accounts_path.parent.mkdir(parents=True, exist_ok=True)
    store.accounts_path.write_text(json.dumps({"accounts": accounts}), encoding="utf-8")


def _account(alias: str, *, enabled: bool = True, priority: int = 0, capabilities: list[str] | None = None) -> dict[str, object]:
    return {
        "alias": alias,
        "provider": "chatgpt_web",
        "enabled": enabled,
        "priority": priority,
        "capabilities": capabilities if capabilities is not None else ["web_ui"],
    }


def _enforcer(store: AccountQuotaStore) -> AccountQuotaEnforcer:
    return AccountQuotaEnforcer(store, now_fn=lambda: NOW)


def test_selection_filters_disabled_cooldown_and_capability_mismatch(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _write_registry(
        store,
        [
            _account("disabled_alias", enabled=False, priority=100),
            _account("cooldown_alias", priority=90),
            _account("code_only", priority=80, capabilities=["codex_cli"]),
            _account("available_alias", priority=10),
        ],
    )
    store.write_state(
        {
            "cooldown_alias": QuotaStateRecord(
                status="cooldown",
                remaining_estimate="low",
                cooldown_until=NOW + timedelta(minutes=30),
            )
        }
    )

    selection = _enforcer(store).select_account(required_capabilities={"web_ui"})

    assert selection.alias == "available_alias"


def test_selection_order_is_health_then_capability_then_priority_then_quota_then_recency(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _write_registry(
        store,
        [
            _account("quota_low_high_priority", priority=100),
            _account("healthy_lower_priority", priority=1),
            _account("healthy_preferred_low_estimate", priority=20),
            _account("healthy_less_preferred_high_estimate", priority=10),
            _account("healthy_same_priority_recent", priority=5),
            _account("healthy_same_priority_old", priority=5),
        ],
    )
    store.write_state(
        {
            "quota_low_high_priority": QuotaStateRecord(status="quota_low", remaining_estimate="high"),
            "healthy_lower_priority": QuotaStateRecord(status="available", remaining_estimate="medium"),
            "healthy_preferred_low_estimate": QuotaStateRecord(status="available", remaining_estimate="low"),
            "healthy_less_preferred_high_estimate": QuotaStateRecord(status="available", remaining_estimate="high"),
            "healthy_same_priority_recent": QuotaStateRecord(
                status="available",
                remaining_estimate="high",
                last_used_at=NOW - timedelta(minutes=1),
            ),
            "healthy_same_priority_old": QuotaStateRecord(
                status="available",
                remaining_estimate="high",
                last_used_at=NOW - timedelta(hours=2),
            ),
        }
    )

    selection = _enforcer(store).select_account(required_capabilities={"web_ui"})

    assert selection.alias == "healthy_preferred_low_estimate"

    _write_registry(
        store,
        [
            _account("same_priority_low", priority=5),
            _account("same_priority_high", priority=5),
        ],
    )
    store.write_state(
        {
            "same_priority_low": QuotaStateRecord(status="available", remaining_estimate="low"),
            "same_priority_high": QuotaStateRecord(status="available", remaining_estimate="high"),
        }
    )
    assert _enforcer(store).select_account(required_capabilities={"web_ui"}).alias == "same_priority_high"

    _write_registry(
        store,
        [
            _account("recent", priority=5),
            _account("older", priority=5),
        ],
    )
    store.write_state(
        {
            "recent": QuotaStateRecord(
                status="available",
                remaining_estimate="high",
                last_used_at=NOW - timedelta(minutes=1),
            ),
            "older": QuotaStateRecord(
                status="available",
                remaining_estimate="high",
                last_used_at=NOW - timedelta(hours=2),
            ),
        }
    )
    assert _enforcer(store).select_account(required_capabilities={"web_ui"}).alias == "older"


def test_no_available_account_raises_typed_exception(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _write_registry(store, [_account("disabled_alias", enabled=False)])

    try:
        _enforcer(store).select_account(required_capabilities={"web_ui"})
    except NoAvailableAccountError:
        pass
    else:  # pragma: no cover - explicit failure branch for pytest output
        raise AssertionError("selection did not fail closed")


def test_would_limit_preflight_rejects_without_incrementing_usage(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _write_registry(store, [_account("limited_alias")])
    started_at = NOW - timedelta(hours=1)
    store.write_state(
        {
            "limited_alias": QuotaStateRecord(
                status="available",
                remaining_estimate="low",
                usage_count=4,
                usage_window_started_at=started_at,
                usage_limit_estimate=5,
            )
        }
    )
    enforcer = _enforcer(store)

    assert enforcer.would_limit("limited_alias", planned_increment=2) is True
    try:
        enforcer.preflight_usage("limited_alias", planned_increment=2)
    except QuotaLimitExceeded:
        pass
    else:  # pragma: no cover - explicit failure branch for pytest output
        raise AssertionError("preflight did not reject over-limit work")

    state_after = store.load_state()["limited_alias"]
    assert state_after.usage_count == 4
    assert state_after.usage_window_started_at == started_at
    assert store.load_events() == ()
    try:
        enforcer.select_account(required_capabilities={"web_ui"}, planned_increment=2)
    except NoAvailableAccountError:
        pass
    else:  # pragma: no cover - explicit failure branch for pytest output
        raise AssertionError("selection ignored preflight limit rejection")


def test_record_usage_updates_state_and_appends_event(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _write_registry(store, [_account("metered_alias")])
    store.write_state(
        {
            "metered_alias": QuotaStateRecord(
                status="available",
                remaining_estimate="high",
                usage_count=1,
                usage_limit_estimate=3,
            )
        }
    )

    updated = _enforcer(store).record_usage(
        "metered_alias",
        source="web_ui",
        run_id="run_example",
        planned_increment=1,
    )

    assert updated.usage_count == 2
    assert updated.usage_window_started_at == NOW
    assert updated.last_used_at == NOW
    assert store.load_events()[0].event_type == "usage_recorded"


def test_quota_signal_hashes_observed_text_and_updates_status(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _write_registry(store, [_account("signal_alias")])
    observed_text = "Synthetic quota banner that must not be stored verbatim"

    updated = _enforcer(store).record_quota_signal(
        "signal_alias",
        signal="rate_limited",
        source="web_ui",
        observed_text=observed_text,
        cooldown_until=NOW + timedelta(minutes=15),
    )

    assert updated.status == "cooldown"
    assert updated.remaining_estimate == "low"
    event_text = store.events_path.read_text(encoding="utf-8")
    assert observed_text not in event_text
    event = store.load_events()[0]
    assert event.observed_text_hash is not None
    assert len(event.observed_text_hash) == 64
    assert event.sanitized_reason == "rate_limited"

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from noeticbraid_core.account.enforcer import (
    AccountQuotaEnforcer,
    NoAvailableAccountError,
    QuotaLimitExceeded,
)
from noeticbraid_core.account.store import AccountQuotaStore


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def make_store(tmp_path: Path) -> AccountQuotaStore:
    store = AccountQuotaStore(tmp_path)
    write_json(
        store.accounts_path,
        {
            "accounts": [
                {"alias": "low-priority", "provider": "chatgpt", "priority": 1, "capabilities": ["chat"]},
                {"alias": "best", "provider": "chatgpt", "priority": 20, "capabilities": ["chat", "browser"]},
                {"alias": "cooling", "provider": "chatgpt", "priority": 99, "capabilities": ["chat"]},
            ]
        },
    )
    write_json(
        store.state_path,
        {
            "low-priority": {"status": "available", "remaining_estimate": "medium"},
            "best": {"status": "available", "remaining_estimate": "high"},
            "cooling": {
                "status": "cooldown",
                "remaining_estimate": "low",
                "cooldown_until": "2026-05-05T13:00:00Z",
            },
        },
    )
    return store


def test_enforcer_selects_by_health_capability_priority_quota_and_recency(tmp_path: Path) -> None:
    now = datetime(2026, 5, 5, 12, 0, tzinfo=timezone.utc)
    enforcer = AccountQuotaEnforcer(make_store(tmp_path), now_fn=lambda: now)

    selection = enforcer.select_account(["chat"], planned_increment=1)

    assert selection.alias == "best"
    assert selection.reason == "selected_by_health_capability_priority_quota_recency"
    assert selection.capabilities == ("chat", "browser")


def test_enforcer_preflight_usage_fails_before_exceeding_limit(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    state = store.load_state()
    state["best"] = state["best"].model_copy(update={"usage_count": 4, "usage_limit_estimate": 5})
    store.write_state(state)
    enforcer = AccountQuotaEnforcer(store)

    with pytest.raises(QuotaLimitExceeded):
        enforcer.preflight_usage("best", planned_increment=2)


def test_enforcer_records_usage_and_quota_signal_without_raw_observed_text(tmp_path: Path) -> None:
    now = datetime(2026, 5, 5, 12, 0, tzinfo=timezone.utc)
    store = make_store(tmp_path)
    enforcer = AccountQuotaEnforcer(store, now_fn=lambda: now)

    usage = enforcer.record_usage("best", source="unit_test", run_id="run_1", planned_increment=1)
    signal = enforcer.record_quota_signal(
        "best",
        signal="quota limit reached!!! token=secret",
        source="unit_test",
        observed_text="raw browser/session text containing secret",
    )

    assert usage.usage_count == 1
    assert signal.status == "quota_low"
    assert signal.remaining_estimate == "low"
    events_text = store.events_path.read_text(encoding="utf-8")
    assert "raw browser/session text" not in events_text
    assert "secret" not in events_text
    assert "observed_text_hash" in events_text


def test_enforcer_empty_pool_raises_no_available_account(tmp_path: Path) -> None:
    store = AccountQuotaStore(tmp_path)
    enforcer = AccountQuotaEnforcer(store)

    with pytest.raises(NoAvailableAccountError):
        enforcer.select_account(["chat"])

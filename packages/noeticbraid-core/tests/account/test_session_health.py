from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from noeticbraid_core.account.models import AccountRegistryRecord
from noeticbraid_core.account.session_health import (
    SessionHealthRecord,
    check_session_health,
    record_session_health,
)
from noeticbraid_core.account.store import AccountQuotaStore


class FakeProbe:
    def __init__(self, record: SessionHealthRecord) -> None:
        self.record = record

    def check(self, account: AccountRegistryRecord) -> SessionHealthRecord:
        return self.record


class DictProbe:
    def check(self, account: AccountRegistryRecord) -> dict[str, str]:
        return {"alias": account.alias, "status": "available", "source": "dict_probe"}


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def account(alias: str = "gpt-main") -> AccountRegistryRecord:
    return AccountRegistryRecord(alias=alias, provider="chatgpt", capabilities=["chat"])


def test_check_session_health_accepts_probe_record_and_hashes_observed_text() -> None:
    now = datetime(2026, 5, 5, 12, 0, tzinfo=timezone.utc)
    record = SessionHealthRecord(
        alias="gpt-main",
        status="login_required",
        checked_at=now,
        source="manual_probe",
        sanitized_reason="session expired token=secret",
        observed_text="raw login page with secret",
    )

    checked = check_session_health(account(), FakeProbe(record), now_fn=lambda: now)

    assert checked.alias == "gpt-main"
    assert checked.status == "login_required"
    assert checked.observed_text_hash is not None
    assert len(checked.observed_text_hash) == 64
    dumped = checked.model_dump(mode="json", exclude_none=True)
    assert "observed_text" not in dumped
    assert "raw login page" not in json.dumps(dumped)
    assert "secret" not in json.dumps(dumped)


def test_check_session_health_fails_when_probe_alias_mismatches() -> None:
    now = datetime(2026, 5, 5, 12, 0, tzinfo=timezone.utc)
    record = SessionHealthRecord(alias="other", status="available", checked_at=now, source="manual_probe")

    with pytest.raises(ValueError, match="probe returned alias"):
        check_session_health(account("gpt-main"), FakeProbe(record), now_fn=lambda: now)


def test_check_session_health_uses_now_fn_for_mapping_probe_without_checked_at() -> None:
    now = datetime(2026, 5, 5, 12, 0, tzinfo=timezone.utc)

    checked = check_session_health(account(), DictProbe(), now_fn=lambda: now)

    assert checked.checked_at == now


def test_record_session_health_updates_state_and_appends_quota_signal_event(tmp_path: Path) -> None:
    store = AccountQuotaStore(tmp_path)
    write_json(store.accounts_path, {"accounts": [{"alias": "gpt-main", "provider": "chatgpt"}]})
    now = datetime(2026, 5, 5, 12, 0, tzinfo=timezone.utc)
    cooldown_until = now + timedelta(hours=1)
    record = SessionHealthRecord(
        alias="gpt-main",
        status="cooldown",
        checked_at=now,
        source="manual_probe",
        sanitized_reason="cooldown active",
        observed_text="raw cooldown page",
        cooldown_until=cooldown_until,
    )

    updated = record_session_health(store, record, run_id="run_1")

    assert updated.status == "cooldown"
    assert updated.remaining_estimate == "low"
    assert updated.cooldown_until == cooldown_until
    events = store.load_events()
    assert len(events) == 1
    assert events[0].event_type == "quota_signal"
    assert events[0].observed_text_hash == record.observed_text_hash

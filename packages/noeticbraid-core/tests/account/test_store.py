from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from noeticbraid_core.account.models import AccountRegistryRecord, QuotaStateRecord
from noeticbraid_core.account.store import AccountQuotaStore, MalformedAccountQuotaState


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_store_loads_registry_and_public_summaries_without_private_profile_label(tmp_path: Path) -> None:
    store = AccountQuotaStore(tmp_path)
    write_json(
        store.accounts_path,
        {
            "accounts": [
                {
                    "alias": "gpt-main",
                    "provider": "chatgpt",
                    "priority": 10,
                    "capabilities": ["chat", "browser"],
                    "browser_profile_label": "Profile 1",
                    "notes": "private note",
                }
            ]
        },
    )
    write_json(
        store.state_path,
        {
            "gpt-main": {
                "status": "available",
                "remaining_estimate": "high",
                "last_signal": "manual_ok",
            }
        },
    )

    registry = store.load_registry()
    summaries = store.public_profile_summaries()

    assert registry[0].browser_profile_label == "Profile 1"
    dumped = summaries[0].model_dump(mode="json", exclude_none=True)
    assert dumped == {
        "alias": "gpt-main",
        "provider": "chatgpt",
        "status": "available",
        "remaining_estimate": "high",
        "capabilities": ["chat", "browser"],
    }
    assert "browser_profile_label" not in dumped
    assert "notes" not in dumped


def test_store_fails_closed_on_malformed_registry(tmp_path: Path) -> None:
    store = AccountQuotaStore(tmp_path)
    store.accounts_path.write_text("not-json", encoding="utf-8")

    with pytest.raises(MalformedAccountQuotaState) as excinfo:
        store.load_registry()

    assert excinfo.value.filename == "accounts.private.json"
    assert excinfo.value.kind == "registry"
    assert "not-json" not in str(excinfo.value)


def test_store_writes_state_atomically_and_loads_jsonl_events(tmp_path: Path) -> None:
    from noeticbraid_core.account.models import QuotaEventRecord

    store = AccountQuotaStore(tmp_path)
    now = datetime(2026, 5, 5, 12, 0, tzinfo=timezone.utc)
    store.write_state({"b": QuotaStateRecord(status="unknown"), "a": QuotaStateRecord(status="available")})
    text = store.state_path.read_text(encoding="utf-8")

    assert text.endswith("\n")
    assert list(json.loads(text).keys()) == ["a", "b"]
    store.append_event(
        QuotaEventRecord(
            alias="a",
            event_type="quota_signal",
            source="unit_test",
            created_at=now,
            sanitized_reason="manual_ok",
        )
    )

    events = store.load_events()
    assert len(events) == 1
    assert events[0].alias == "a"
    assert events[0].created_at == now


def test_store_fails_closed_on_malformed_quota_state_json(tmp_path: Path) -> None:
    store = AccountQuotaStore(tmp_path)
    store.state_path.write_text("{ broken json", encoding="utf-8")

    with pytest.raises(MalformedAccountQuotaState) as excinfo:
        store.load_state()

    assert excinfo.value.filename == "quota_state.json"
    assert excinfo.value.kind == "state"


def test_store_fails_closed_on_malformed_events_jsonl(tmp_path: Path) -> None:
    store = AccountQuotaStore(tmp_path)
    store.events_path.write_text("not-json-line\n", encoding="utf-8")

    with pytest.raises(MalformedAccountQuotaState) as excinfo:
        store.load_events()

    assert excinfo.value.filename == "quota_events.jsonl"
    assert excinfo.value.kind == "events"


def test_account_quota_store_from_settings(tmp_path: Path) -> None:
    configured_root = tmp_path / "state" / "account_quota"
    settings = SimpleNamespace(account_quota_dir=configured_root)

    store = AccountQuotaStore.from_settings(settings)

    assert store.root == configured_root


def test_load_registry_bare_list_format(tmp_path: Path) -> None:
    store = AccountQuotaStore(tmp_path)
    write_json(
        store.accounts_path,
        [
            {
                "account_id": "legacy-main",
                "provider": "chatgpt",
                "capabilities": ["chat"],
            }
        ],
    )

    records = store.load_registry()

    assert len(records) == 1
    assert records[0].alias == "legacy-main"


def test_account_registry_record_extra_forbid_rejects() -> None:
    with pytest.raises(ValidationError):
        AccountRegistryRecord(
            alias="gpt-main",
            provider="chatgpt",
            capabilities=["chat"],
            unknown_field="should-be-rejected",
        )

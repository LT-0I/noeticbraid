# SPDX-License-Identifier: Apache-2.0
"""Tests for private account/quota JSON and JSONL persistence."""

from __future__ import annotations

import json
import traceback
from datetime import datetime, timezone
from pathlib import Path

from noeticbraid_backend.account_quota.models import QuotaEventRecord, QuotaStateRecord
from noeticbraid_backend.account_quota.store import AccountQuotaStore, MalformedAccountQuotaState
from noeticbraid_backend.settings import Settings


def _store(tmp_path: Path) -> AccountQuotaStore:
    settings = Settings(state_dir=tmp_path / "state", dpapi_blob_path=None)
    return AccountQuotaStore.from_settings(settings)


def test_missing_runtime_files_return_empty_views(tmp_path: Path) -> None:
    store = _store(tmp_path)

    assert store.load_registry() == ()
    assert store.load_state() == {}
    assert store.load_events() == ()
    assert store.public_profile_summaries() == ()


def test_registry_legacy_alias_input_maps_to_alias(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.accounts_path.parent.mkdir(parents=True)
    legacy_alias_key = "account" + "_id"
    store.accounts_path.write_text(
        json.dumps(
            {
                "accounts": [
                    {
                        legacy_alias_key: "chatgpt_6fox",
                        "provider": "chatgpt_web",
                        "enabled": True,
                        "priority": 10,
                        "capabilities": ["web_ui", "file_upload"],
                        "profile_directory": "Profile 21",
                        "notes": "synthetic test registry note",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    (record,) = store.load_registry()

    assert record.alias == "chatgpt_6fox"
    assert record.browser_profile_label == "Profile 21"
    assert record.capabilities == ["web_ui", "file_upload"]


def test_malformed_json_fails_closed_without_echoing_raw_content(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.accounts_path.parent.mkdir(parents=True)
    secret_phrase = "do-not-echo-this-value"
    store.accounts_path.write_text("{not-json " + secret_phrase, encoding="utf-8")

    try:
        store.load_registry()
    except MalformedAccountQuotaState as exc:
        rendered = str(exc)
    else:  # pragma: no cover - explicit failure branch for pytest output
        raise AssertionError("malformed registry JSON was accepted")

    assert "accounts.private.json" in rendered
    assert secret_phrase not in rendered

    store.state_path.write_text("{not-json " + secret_phrase, encoding="utf-8")
    try:
        store.load_state()
    except MalformedAccountQuotaState as exc:
        rendered = str(exc)
    else:  # pragma: no cover - explicit failure branch for pytest output
        raise AssertionError("malformed state JSON was accepted")

    assert "quota_state.json" in rendered
    assert secret_phrase not in rendered


def test_registry_validation_exception_chain_does_not_echo_private_values(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.accounts_path.parent.mkdir(parents=True)
    private_values = (
        "private_alias_do_not_echo!",
        "C:/Users/example/Profile 21",
        "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    )
    store.accounts_path.write_text(
        json.dumps(
            {
                "accounts": [
                    {
                        "alias": private_values[0],
                        "provider": "chatgpt_web",
                        "enabled": True,
                        "priority": 1,
                        "capabilities": ["web_ui"],
                        "browser_profile_label": private_values[1],
                        "notes": private_values[2],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    try:
        store.load_registry()
    except MalformedAccountQuotaState as exc:
        rendered_traceback = "".join(traceback.format_exception(exc))
        assert exc.__cause__ is None
    else:  # pragma: no cover - explicit failure branch for pytest output
        raise AssertionError("malformed private registry was accepted")

    for private_value in private_values:
        assert private_value not in rendered_traceback


def test_state_write_is_parse_valid_and_preserves_usage_accounting(tmp_path: Path) -> None:
    store = _store(tmp_path)
    started_at = datetime(2026, 5, 2, 20, 0, tzinfo=timezone.utc)
    checked_at = datetime(2026, 5, 2, 20, 5, tzinfo=timezone.utc)

    store.write_state(
        {
            "chatgpt_6fox": QuotaStateRecord(
                status="available",
                remaining_estimate="medium",
                last_checked_at=checked_at,
                usage_count=2,
                usage_window_started_at=started_at,
                usage_limit_estimate=5,
            )
        }
    )

    parsed = json.loads(store.state_path.read_text(encoding="utf-8"))
    record = parsed["chatgpt_6fox"]
    assert record["usage_count"] == 2
    assert record["usage_window_started_at"] in {started_at.isoformat(), started_at.isoformat().replace("+00:00", "Z")}
    assert record["usage_limit_estimate"] == 5
    assert store.load_state()["chatgpt_6fox"].usage_count == 2


def test_jsonl_event_append_is_line_oriented_and_parse_valid(tmp_path: Path) -> None:
    store = _store(tmp_path)
    created_at = datetime(2026, 5, 2, 20, 10, tzinfo=timezone.utc)

    store.append_event(
        QuotaEventRecord(
            alias="chatgpt_6fox",
            event_type="usage_recorded",
            source="web_ui",
            run_id="run_example",
            created_at=created_at,
            sanitized_reason="usage_recorded",
        )
    )
    store.append_event(
        QuotaEventRecord(
            alias="chatgpt_6fox",
            event_type="quota_signal",
            source="codex_cli",
            created_at=created_at,
            observed_text_hash="0" * 64,
            sanitized_reason="rate_limited",
        )
    )

    lines = store.events_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    for line in lines:
        assert isinstance(json.loads(line), dict)
    assert [event.event_type for event in store.load_events()] == ["usage_recorded", "quota_signal"]

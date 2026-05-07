from __future__ import annotations

import json

import noeticbraid.tools.workflow_scheduler.notifier as notifier_module
from noeticbraid.tools.workflow_scheduler.notifier import ALLOWED_OUTBOUND_LEVELS, OutboundChannelConfig, OutboundNotifier


def test_outbound_levels_are_blueprint_five_levels():
    assert ALLOWED_OUTBOUND_LEVELS == (
        "silent_record",
        "low_priority",
        "normal",
        "requires_confirmation",
        "urgent_interrupt",
    )


def test_local_fallback_records_sanitized_message(tmp_path):
    events = tmp_path / "notify.jsonl"
    notifier = OutboundNotifier(event_log_path=events)

    result = notifier.send("review token=SECRET123 private/creds.txt", level="normal", channel="lark", refs={"workflow_id": "workflow_unit"})

    assert result.delivery == "local_record"
    assert result.reason == "channel_not_configured"
    payload = json.loads(events.read_text(encoding="utf-8").splitlines()[-1])
    assert payload["event_type"] == "outbound_notify"
    assert "SECRET123" not in json.dumps(payload)
    assert "private/creds" not in json.dumps(payload)


def test_lark_and_dingtalk_webhooks_use_env_tokens_without_leaking(monkeypatch, tmp_path):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append((request.full_url, request.data.decode("utf-8"), timeout))
        class Response:
            def __enter__(self): return self
            def __exit__(self, exc_type, exc, tb): return False
            def read(self): return b'{"ok": true}'
        return Response()

    monkeypatch.setenv("LARK_WEBHOOK_URL", "https://example.invalid/lark/TOKENSECRET")
    monkeypatch.setenv("DINGTALK_WEBHOOK_URL", "https://example.invalid/dingtalk/TOKENSECRET")
    events = tmp_path / "notify.jsonl"
    notifier = OutboundNotifier(
        event_log_path=events,
        channels={
            "lark": OutboundChannelConfig(channel="lark", enabled=True, webhook_url_env="LARK_WEBHOOK_URL"),
            "dingtalk": OutboundChannelConfig(channel="dingtalk", enabled=True, webhook_url_env="DINGTALK_WEBHOOK_URL"),
        },
        urlopen=fake_urlopen,
    )

    lark = notifier.send("approval needed", level="requires_confirmation", channel="lark", refs={})
    ding = notifier.send("normal", level="normal", channel="dingtalk", refs={})

    assert lark.delivery == "sent"
    assert ding.delivery == "sent"
    assert len(calls) == 2
    ledger_text = events.read_text(encoding="utf-8")
    assert "TOKENSECRET" not in ledger_text


def test_telegram_channel_is_disabled_by_default(tmp_path):
    notifier = OutboundNotifier(event_log_path=tmp_path / "notify.jsonl")
    result = notifier.send("hello", level="normal", channel="telegram", refs={})

    assert result.delivery == "local_record"
    assert result.reason == "telegram_disabled"


def test_silent_record_is_local_only_and_event_log_is_fsynced(monkeypatch, tmp_path):
    fsynced = []
    monkeypatch.setattr(notifier_module.os, "fsync", lambda fileno: fsynced.append(fileno))
    events = tmp_path / "notify.jsonl"
    notifier = OutboundNotifier(
        event_log_path=events,
        channels={"lark": OutboundChannelConfig(channel="lark", enabled=True, webhook_url_env="LARK_WEBHOOK_URL")},
    )

    result = notifier.send("raw_token=SECRET", level="silent_record", channel="lark", refs={"dpapi_blob": "BLOB"})

    payload = json.loads(events.read_text(encoding="utf-8").splitlines()[-1])
    assert result.channel == "local"
    assert result.reason == "silent_record"
    assert payload["channel"] == "local"
    assert payload["refs"]["dpapi_blob"] == "[REDACTED]"
    assert "SECRET" not in json.dumps(payload)
    assert fsynced


def test_urgent_interrupt_fans_out_to_enabled_lark_and_dingtalk(monkeypatch, tmp_path):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(request.full_url)

        class Response:
            def __enter__(self): return self
            def __exit__(self, exc_type, exc, tb): return False
            def read(self): return b'{"ok": true}'

        return Response()

    monkeypatch.setenv("LARK_WEBHOOK_URL", "https://example.invalid/lark/TOKENSECRET")
    monkeypatch.setenv("DINGTALK_WEBHOOK_URL", "https://example.invalid/dingtalk/TOKENSECRET")
    events = tmp_path / "notify.jsonl"
    notifier = OutboundNotifier(
        event_log_path=events,
        channels={
            "lark": OutboundChannelConfig(channel="lark", enabled=True, webhook_url_env="LARK_WEBHOOK_URL"),
            "dingtalk": OutboundChannelConfig(channel="dingtalk", enabled=True, webhook_url_env="DINGTALK_WEBHOOK_URL"),
        },
        urlopen=fake_urlopen,
    )

    result = notifier.send("urgent", level="urgent_interrupt", channel=None, refs={"webhook_url": "https://secret.invalid"})

    assert result["fanout"] is True
    assert [item["channel"] for item in result["channels"]] == ["lark", "dingtalk"]
    assert len(calls) == 2
    ledger_text = events.read_text(encoding="utf-8")
    assert "TOKENSECRET" not in ledger_text
    assert "secret.invalid" not in ledger_text

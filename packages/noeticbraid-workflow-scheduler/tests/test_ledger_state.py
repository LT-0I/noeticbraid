from __future__ import annotations

import json

import noeticbraid.tools.workflow_scheduler.ledger as ledger_module
from noeticbraid.tools.workflow_scheduler.ledger import (
    OUTBOUND_LEVEL_TO_EVENT_TYPE,
    RUNRECORD_EVENT_TYPE_MAPPING,
    REQUIRED_LEDGER_FIELDS,
    RunLedgerWriter,
    read_jsonl,
)
from noeticbraid.tools.workflow_scheduler.redaction import redact_text, redact_value
from noeticbraid.tools.workflow_scheduler.state_store import update_scheduler_module_state


def test_ledger_writer_emits_required_fields_and_neutral_event_names(tmp_path):
    ledger = tmp_path / "runs.jsonl"
    writer = RunLedgerWriter(ledger)

    writer.write(
        run_id="run_unit",
        workflow_id="workflow_unit",
        event_type="outbound_notify",
        status="blocked",
        step_id="step_notify",
        task_id="task_unit",
        level="requires_confirmation",
    )

    records = read_jsonl(ledger)
    assert len(records) == 1
    assert all(field in records[0] for field in REQUIRED_LEDGER_FIELDS)
    assert records[0]["event_type"] == "outbound_notify"
    assert records[0]["runrecord_event_type"] == "approval_requested"
    assert "telegram_notify" not in json.dumps(records[0])


def test_runrecord_mapping_uses_only_frozen_event_types():
    frozen = {
        "task_created", "task_classified", "context_built", "approval_requested",
        "approval_decision_recorded", "web_ai_call_requested", "profile_health_checked",
        "source_record_linked", "artifact_created", "security_violation",
        "lesson_candidate_created", "routing_advice_recorded", "task_completed", "task_failed",
    }
    assert set(RUNRECORD_EVENT_TYPE_MAPPING.values()) <= frozen
    assert OUTBOUND_LEVEL_TO_EVENT_TYPE == {
        "silent_record": "artifact_created",
        "low_priority": "routing_advice_recorded",
        "normal": "approval_requested",
        "requires_confirmation": "approval_requested",
        "urgent_interrupt": "approval_requested",
    }
    assert RUNRECORD_EVENT_TYPE_MAPPING["run_finished"] == "task_completed"
    assert "schedule_due" not in RUNRECORD_EVENT_TYPE_MAPPING


def test_ledger_redacts_sensitive_keys_and_fsyncs(monkeypatch, tmp_path):
    fsynced = []
    monkeypatch.setattr(ledger_module.os, "fsync", lambda fileno: fsynced.append(fileno))
    ledger = tmp_path / "runs.jsonl"
    writer = RunLedgerWriter(ledger)

    writer.write(
        run_id="run_secret",
        workflow_id="workflow_unit",
        event_type="outbound_notify",
        status="blocked",
        level="silent_record",
        refs={"raw_token": "SECRET", "nested": {"dpapi_blob": "BLOB", "webhook_url": "https://secret.invalid"}},
    )

    record = read_jsonl(ledger)[0]
    assert record["runrecord_event_type"] == "artifact_created"
    assert record["refs"] == {
        "raw_token": "[REDACTED]",
        "nested": {"dpapi_blob": "[REDACTED]", "webhook_url": "[REDACTED]"},
    }
    assert fsynced
    assert redact_value({"raw_token": "SECRET", "dpapi_blob": "BLOB", "bot_token": "123:ABC", "webhook_url": "https://x"}) == {
        "raw_token": "[REDACTED]",
        "dpapi_blob": "[REDACTED]",
        "bot_token": "[REDACTED]",
        "webhook_url": "[REDACTED]",
    }
    text = "raw_token=SECRET dpapi_blob=BLOB webhook_url=https://example.invalid bot_token=123456:ABCDEF0123456789abcdef"
    redacted = redact_text(text)
    assert "SECRET" not in redacted
    assert "BLOB" not in redacted
    assert "example.invalid" not in redacted
    assert "ABCDEF" not in redacted


def test_state_update_changes_only_workflow_scheduler_namespace(tmp_path):
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"phase": "1.2", "pending_actor": "idle", "modules": {"other": {"x": 1}}}), encoding="utf-8")

    updated = update_scheduler_module_state(state, run_id="run_unit", status="completed")
    reloaded = json.loads(state.read_text(encoding="utf-8"))

    assert updated == reloaded
    assert reloaded["phase"] == "1.2"
    assert reloaded["pending_actor"] == "idle"
    assert reloaded["modules"]["other"] == {"x": 1}
    assert reloaded["modules"]["workflow_scheduler"] == {
        "step": "implemented",
        "last_run_id": "run_unit",
        "last_status": "completed",
    }
    assert "workflow_scheduler_telegram" not in reloaded["modules"]

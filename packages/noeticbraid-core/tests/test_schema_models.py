"""Behavioral tests for Stage 1 candidate schema models."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from noeticbraid_core.schemas import (
    ApprovalRequest,
    DigestionItem,
    RunRecord,
    SideNote,
    SourceRecord,
    Task,
)

MODEL_FIXTURE_NAMES = [
    (Task, "task"),
    (RunRecord, "run_record"),
    (SourceRecord, "source_record"),
    (ApprovalRequest, "approval_request"),
    (SideNote, "side_note"),
    (DigestionItem, "digestion_item"),
]


def base_data(load_schema_fixture, model):
    name = dict(MODEL_FIXTURE_NAMES)[model]
    return load_schema_fixture(name)


@pytest.mark.parametrize("model, fixture_name", MODEL_FIXTURE_NAMES)
def test_fixtures_validate_after_metadata_pop(model, fixture_name, load_schema_fixture):
    data = load_schema_fixture(fixture_name)
    instance = model.model_validate(data)
    assert instance is not None


@pytest.mark.parametrize("model, fixture_name", MODEL_FIXTURE_NAMES)
def test_json_round_trip(model, fixture_name, load_schema_fixture):
    instance = model.model_validate(load_schema_fixture(fixture_name))
    round_tripped = model.model_validate_json(instance.model_dump_json())
    assert instance == round_tripped


@pytest.mark.parametrize("model, fixture_name", MODEL_FIXTURE_NAMES)
def test_extra_fields_are_forbidden(model, fixture_name, load_schema_fixture):
    data = load_schema_fixture(fixture_name)
    data["extra_field"] = "not allowed"
    with pytest.raises(ValidationError):
        model.model_validate(data)


@pytest.mark.parametrize(
    "model, field_name, invalid_value",
    [
        (Task, "task_id", "task bad"),
        (RunRecord, "run_id", "run bad"),
        (RunRecord, "task_id", "task bad"),
        (SourceRecord, "source_ref_id", "source bad"),
        (SourceRecord, "retrieved_by_run_id", "run bad"),
        (SourceRecord, "source_fingerprint", "fingerprint bad"),
        (ApprovalRequest, "approval_id", "approval bad"),
        (ApprovalRequest, "task_id", "task bad"),
        (ApprovalRequest, "run_id", "run bad"),
        (SideNote, "note_id", "note bad"),
        (DigestionItem, "digestion_id", "digestion bad"),
        (DigestionItem, "side_note_id", "note bad"),
    ],
)
def test_identifier_patterns_reject_invalid_values(
    model, field_name, invalid_value, load_schema_fixture
):
    data = base_data(load_schema_fixture, model)
    data[field_name] = invalid_value
    with pytest.raises(ValidationError):
        model.model_validate(data)


@pytest.mark.parametrize(
    "model, field_name, valid_value",
    [
        (Task, "task_id", "task_valid_001"),
        (RunRecord, "run_id", "run_valid_001"),
        (RunRecord, "task_id", "task_valid_001"),
        (SourceRecord, "source_ref_id", "source_valid_001"),
        (SourceRecord, "retrieved_by_run_id", "run_valid_001"),
        (SourceRecord, "source_fingerprint", "fingerprint_valid_001"),
        (ApprovalRequest, "approval_id", "approval_valid_001"),
        (ApprovalRequest, "task_id", "task_valid_001"),
        (ApprovalRequest, "run_id", "run_valid_001"),
        (SideNote, "note_id", "note_valid_001"),
        (DigestionItem, "digestion_id", "digestion_valid_001"),
        (DigestionItem, "side_note_id", "note_valid_001"),
    ],
)
def test_identifier_patterns_accept_valid_values(model, field_name, valid_value, load_schema_fixture):
    data = base_data(load_schema_fixture, model)
    data[field_name] = valid_value
    assert model.model_validate(data) is not None


@pytest.mark.parametrize(
    "model, field_name",
    [
        (Task, "user_request"),
        (SourceRecord, "title"),
        (ApprovalRequest, "requested_action"),
        (ApprovalRequest, "reason"),
        (SideNote, "claim"),
    ],
)
def test_required_text_fields_reject_empty_strings(model, field_name, load_schema_fixture):
    data = base_data(load_schema_fixture, model)
    data[field_name] = ""
    with pytest.raises(ValidationError):
        model.model_validate(data)


@pytest.mark.parametrize(
    "model, field_name, oversized_value",
    [
        pytest.param(Task, "user_request", "x" * 8193, id="task_user_request_oversized"),
        pytest.param(SourceRecord, "title", "x" * 513, id="source_title_oversized"),
        pytest.param(ApprovalRequest, "reason", "x" * 4097, id="approval_reason_oversized"),
        pytest.param(SideNote, "claim", "x" * 4097, id="side_note_claim_oversized"),
    ],
)
def test_text_fields_reject_oversized_strings(model, field_name, oversized_value, load_schema_fixture):
    data = base_data(load_schema_fixture, model)
    data[field_name] = oversized_value
    with pytest.raises(ValidationError):
        model.model_validate(data)


@pytest.mark.parametrize(
    "model, datetime_field",
    [
        (Task, "created_at"),
        (RunRecord, "created_at"),
        (SourceRecord, "captured_at"),
        (ApprovalRequest, "requested_at"),
        (SideNote, "created_at"),
        (DigestionItem, "created_at"),
        (DigestionItem, "next_review_at"),
    ],
)
def test_naive_datetimes_are_normalized_to_utc(model, datetime_field, load_schema_fixture):
    data = base_data(load_schema_fixture, model)
    data[datetime_field] = datetime(2026, 4, 28, 9, 30, 0)
    instance = model.model_validate(data)
    assert getattr(instance, datetime_field).tzinfo is not None
    assert getattr(instance, datetime_field).utcoffset() == timedelta(0)


@pytest.mark.parametrize(
    "model, datetime_attr",
    [
        (Task, "created_at"),
        (RunRecord, "created_at"),
        (SourceRecord, "captured_at"),
        (ApprovalRequest, "requested_at"),
        (SideNote, "created_at"),
        (DigestionItem, "created_at"),
    ],
)
def test_datetime_default_factories_are_utc(model, datetime_attr):
    kwargs = {
        Task: dict(
            task_id="task_default_001",
            task_type="research",
            risk_level="low",
            approval_level="none",
            user_request="default timestamp test",
            source_channel="local",
        ),
        RunRecord: dict(
            run_id="run_default_001",
            task_id="task_default_001",
            event_type="task_created",
            actor="system",
        ),
        SourceRecord: dict(
            source_ref_id="source_default_001",
            source_type="paper",
            title="Default timestamp source",
            retrieved_by_run_id="run_default_001",
            content_hash="sha256:1111111111111111111111111111111111111111111111111111111111111111",
            source_fingerprint="fingerprint_default_001",
            evidence_role="source_grounding",
            used_for_purpose="source_grounding",
        ),
        ApprovalRequest: dict(
            approval_id="approval_default_001",
            task_id="task_default_001",
            approval_level="light",
            requested_action="approve default timestamp test",
            reason="timestamp validation",
        ),
        SideNote: dict(
            note_id="note_default_001",
            note_type="fact",
            claim="default timestamp side note",
            confidence="medium",
        ),
        DigestionItem: dict(
            digestion_id="digestion_default_001",
            side_note_id="note_default_001",
        ),
    }[model]
    instance = model(**kwargs)
    assert getattr(instance, datetime_attr).tzinfo is not None


@pytest.mark.parametrize(
    "model, field_name, bad_value",
    [
        (RunRecord, "model_refs", ["bad_model"]),
        (RunRecord, "source_refs", ["bad_source"]),
        (RunRecord, "artifact_refs", ["bad_artifact"]),
        (SideNote, "linked_source_refs", ["bad_source"]),
    ],
)
def test_reference_lists_reject_bad_prefixes(model, field_name, bad_value, load_schema_fixture):
    data = base_data(load_schema_fixture, model)
    data[field_name] = bad_value
    with pytest.raises(ValidationError):
        model.model_validate(data)


@pytest.mark.parametrize(
    "model, field_name, duplicated_value",
    [
        (RunRecord, "model_refs", "model_duplicate"),
        (RunRecord, "source_refs", "source_duplicate"),
        (RunRecord, "artifact_refs", "artifact_duplicate"),
        (SideNote, "linked_source_refs", "source_duplicate"),
    ],
)
def test_reference_lists_reject_duplicates(
    model, field_name, duplicated_value, load_schema_fixture
):
    data = base_data(load_schema_fixture, model)
    data[field_name] = [duplicated_value, duplicated_value]
    with pytest.raises(ValidationError):
        model.model_validate(data)


def test_task_defaults_and_business_methods():
    task = Task(
        task_id="task_business_001",
        task_type="project_planning",
        risk_level="medium",
        approval_level="light",
        user_request="plan a schema test",
        source_channel="console",
    )
    assert task.status == "draft"
    assert task.requires_user_approval() is True
    assert task.is_terminal() is False
    assert task.to_event_dict()["task_id"] == "task_business_001"
    assert Task.model_validate({**task.model_dump(), "status": "completed"}).is_terminal() is True


def test_run_record_defaults_and_business_methods():
    run = RunRecord(
        run_id="run_business_001",
        task_id="task_business_001",
        event_type="task_failed",
        actor="system",
        source_refs=["source_business_001"],
    )
    assert run.status == "draft"
    assert run.is_failure() is True
    assert run.has_external_refs() is True
    assert run.to_ledger_event_dict()["event_type"] == "task_failed"


def test_source_record_business_methods_and_url_validation(load_schema_fixture):
    source = SourceRecord.model_validate(load_schema_fixture("source_record"))
    assert source.has_location() is True
    assert source.is_high_value() is True
    assert source.to_evidence_key().startswith("source_stage1_candidate_001:")

    data = load_schema_fixture("source_record")
    data["canonical_url"] = "ftp://example.com/file"
    with pytest.raises(ValidationError):
        SourceRecord.model_validate(data)


def test_approval_request_defaults_and_business_methods():
    approval = ApprovalRequest(
        approval_id="approval_business_001",
        task_id="task_business_001",
        approval_level="strong",
        requested_action="change a protected boundary",
        reason="requires strong user approval",
    )
    assert approval.status == "pending"
    assert approval.needs_user_decision() is True
    assert approval.is_resolved() is False
    assert ApprovalRequest.model_validate({**approval.model_dump(), "status": "approved"}).is_approved() is True


def test_side_note_defaults_and_business_methods():
    note = SideNote(
        note_id="note_business_001",
        linked_source_refs=["source_business_001"],
        note_type="challenge",
        claim="this needs user review",
        confidence="high",
    )
    assert note.user_response == "unread"
    assert note.has_sources() is True
    assert note.is_actionable() is True
    assert SideNote.model_validate({**note.model_dump(), "user_response": "accepted"}).is_user_resolved() is True


def test_digestion_item_defaults_and_business_methods():
    past = datetime(2026, 4, 27, 9, 35, 0, tzinfo=timezone.utc)
    now = datetime(2026, 4, 28, 9, 35, 0, tzinfo=timezone.utc)
    item = DigestionItem(
        digestion_id="digestion_business_001",
        side_note_id="note_business_001",
        next_review_at=past,
    )
    assert item.c_status == "c0"
    assert item.status == "open"
    assert item.is_overdue(now) is True
    assert item.needs_review(now) is True
    assert DigestionItem.model_validate({**item.model_dump(), "status": "closed"}).is_closed() is True


@pytest.mark.parametrize(
    "model, field_name, bad_literal",
    [
        (Task, "task_type", "data_analysis"),
        (Task, "risk_level", "critical"),
        (Task, "approval_level", "admin"),
        (Task, "status", "archived"),
        (Task, "source_channel", "email"),
        (RunRecord, "event_type", "unknown_event"),
        (RunRecord, "actor", "agent"),
        (RunRecord, "status", "done"),
        (SourceRecord, "source_type", "blog"),
        (SourceRecord, "quality_score", "excellent"),
        (SourceRecord, "relevance_score", "excellent"),
        (SourceRecord, "evidence_role", "citation"),
        (SourceRecord, "used_for_purpose", "training"),
        (ApprovalRequest, "approval_level", "admin"),
        (ApprovalRequest, "status", "done"),
        (SideNote, "note_type", "memo"),
        (SideNote, "confidence", "certain"),
        (SideNote, "user_response", "ignored"),
        (DigestionItem, "c_status", "c5"),
        (DigestionItem, "status", "done"),
    ],
)
def test_literal_fields_reject_unknown_values(
    model, field_name, bad_literal, load_schema_fixture
):
    data = base_data(load_schema_fixture, model)
    data[field_name] = bad_literal
    with pytest.raises(ValidationError):
        model.model_validate(data)


VALID_LITERAL_CASES = [
    (Task, "task_type", value)
    for value in ["project_planning", "research", "code_review"]
] + [
    (Task, "risk_level", value) for value in ["low", "medium", "high"]
] + [
    (Task, "approval_level", value)
    for value in ["none", "light", "strong", "forbidden"]
] + [
    (Task, "status", value)
    for value in ["draft", "ready", "queued", "running", "waiting_for_user", "failed", "completed"]
] + [
    (Task, "source_channel", value)
    for value in ["console", "obsidian", "im", "schedule", "local"]
] + [
    (RunRecord, "event_type", value)
    for value in [
        "task_created",
        "task_classified",
        "context_built",
        "approval_requested",
        "approval_decision_recorded",
        "web_ai_call_requested",
        "profile_health_checked",
        "source_record_linked",
        "artifact_created",
        "security_violation",
        "lesson_candidate_created",
        "routing_advice_recorded",
        "task_completed",
        "task_failed",
    ]
] + [
    (RunRecord, "actor", value) for value in ["user", "system", "model", "local_review"]
] + [
    (RunRecord, "status", value) for value in ["draft", "recorded", "failed"]
] + [
    (SourceRecord, "source_type", value)
    for value in [
        "user_note",
        "web_page",
        "github_repo",
        "paper",
        "patent",
        "video",
        "ai_output",
        "paid_database",
    ]
] + [
    (SourceRecord, "quality_score", value)
    for value in ["low", "medium", "high", "unknown"]
] + [
    (SourceRecord, "relevance_score", value)
    for value in ["low", "medium", "high", "unknown"]
] + [
    (SourceRecord, "evidence_role", value)
    for value in [
        "user_context",
        "reference_project",
        "source_grounding",
        "contradiction",
        "memory_update_evidence",
    ]
] + [
    (SourceRecord, "used_for_purpose", value)
    for value in [
        "project_positioning",
        "constraint_extraction",
        "source_grounding",
        "prior_art_check",
        "other",
    ]
] + [
    (ApprovalRequest, "approval_level", value)
    for value in ["none", "light", "strong", "forbidden"]
] + [
    (ApprovalRequest, "status", value)
    for value in ["pending", "approved", "rejected", "blocked"]
] + [
    (SideNote, "note_type", value) for value in ["fact", "hypothesis", "challenge", "action"]
] + [
    (SideNote, "confidence", value) for value in ["low", "medium", "high"]
] + [
    (SideNote, "user_response", value)
    for value in ["unread", "accepted", "rejected", "modified"]
] + [
    (DigestionItem, "c_status", value) for value in ["c0", "c1", "c2", "c3", "c4", "cX"]
] + [
    (DigestionItem, "status", value) for value in ["open", "closed", "rejected", "snoozed"]
]


@pytest.mark.parametrize("model, field_name, valid_literal", VALID_LITERAL_CASES)
def test_literal_fields_accept_every_declared_value(
    model, field_name, valid_literal, load_schema_fixture
):
    data = base_data(load_schema_fixture, model)
    data[field_name] = valid_literal
    assert model.model_validate(data) is not None

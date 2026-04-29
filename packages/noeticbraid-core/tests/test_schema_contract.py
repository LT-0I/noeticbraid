"""Contract-equivalence checks for Stage 1 candidate schema implementations."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional, get_args, get_origin

import pytest

from noeticbraid_core.schemas import (
    ApprovalRequest,
    DigestionItem,
    RunRecord,
    SideNote,
    SourceRecord,
    Task,
)

EXPECTED_FIELDS = {
    Task: {
        "task_id",
        "task_type",
        "risk_level",
        "approval_level",
        "created_at",
        "status",
        "user_request",
        "source_channel",
        "account_hint",
        "project_ref",
    },
    RunRecord: {
        "run_id",
        "task_id",
        "event_type",
        "created_at",
        "actor",
        "model_refs",
        "source_refs",
        "artifact_refs",
        "routing_advice",
        "status",
    },
    SourceRecord: {
        "source_ref_id",
        "source_type",
        "title",
        "canonical_url",
        "local_path",
        "author",
        "captured_at",
        "retrieved_by_run_id",
        "content_hash",
        "source_fingerprint",
        "quality_score",
        "relevance_score",
        "evidence_role",
        "used_for_purpose",
    },
    ApprovalRequest: {
        "approval_id",
        "task_id",
        "run_id",
        "approval_level",
        "requested_at",
        "requested_action",
        "reason",
        "diff_ref",
        "status",
    },
    SideNote: {
        "note_id",
        "created_at",
        "linked_source_refs",
        "note_type",
        "claim",
        "confidence",
        "user_response",
        "follow_up_ref",
    },
    DigestionItem: {
        "digestion_id",
        "side_note_id",
        "created_at",
        "c_status",
        "user_response_ref",
        "next_review_at",
        "status",
    },
}

EXPECTED_LITERAL_VALUES = {
    (Task, "task_type"): {"project_planning", "research", "code_review"},
    (Task, "risk_level"): {"low", "medium", "high"},
    (Task, "approval_level"): {"none", "light", "strong", "forbidden"},
    (Task, "status"): {
        "draft",
        "ready",
        "queued",
        "running",
        "waiting_for_user",
        "failed",
        "completed",
    },
    (Task, "source_channel"): {"console", "obsidian", "im", "schedule", "local"},
    (RunRecord, "event_type"): {
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
    },
    (RunRecord, "actor"): {"user", "system", "model", "local_review"},
    (RunRecord, "status"): {"draft", "recorded", "failed"},
    (SourceRecord, "source_type"): {
        "user_note",
        "web_page",
        "github_repo",
        "paper",
        "patent",
        "video",
        "ai_output",
        "paid_database",
    },
    (SourceRecord, "quality_score"): {"low", "medium", "high", "unknown"},
    (SourceRecord, "relevance_score"): {"low", "medium", "high", "unknown"},
    (SourceRecord, "evidence_role"): {
        "user_context",
        "reference_project",
        "source_grounding",
        "contradiction",
        "memory_update_evidence",
    },
    (SourceRecord, "used_for_purpose"): {
        "project_positioning",
        "constraint_extraction",
        "source_grounding",
        "prior_art_check",
        "other",
    },
    (ApprovalRequest, "approval_level"): {"none", "light", "strong", "forbidden"},
    (ApprovalRequest, "status"): {"pending", "approved", "rejected", "blocked"},
    (SideNote, "note_type"): {"fact", "hypothesis", "challenge", "action"},
    (SideNote, "confidence"): {"low", "medium", "high"},
    (SideNote, "user_response"): {"unread", "accepted", "rejected", "modified"},
    (DigestionItem, "c_status"): {"c0", "c1", "c2", "c3", "c4", "cX"},
    (DigestionItem, "status"): {"open", "closed", "rejected", "snoozed"},
}

EXPECTED_NON_LITERAL_TYPES = {
    (Task, "task_id"): str,
    (Task, "created_at"): datetime,
    (Task, "user_request"): str,
    (Task, "account_hint"): Optional[str],
    (Task, "project_ref"): Optional[str],
    (RunRecord, "run_id"): str,
    (RunRecord, "task_id"): str,
    (RunRecord, "created_at"): datetime,
    (RunRecord, "model_refs"): list[str],
    (RunRecord, "source_refs"): list[str],
    (RunRecord, "artifact_refs"): list[str],
    (RunRecord, "routing_advice"): Optional[str],
    (SourceRecord, "source_ref_id"): str,
    (SourceRecord, "title"): str,
    (SourceRecord, "canonical_url"): Optional[str],
    (SourceRecord, "local_path"): Optional[str],
    (SourceRecord, "author"): Optional[str],
    (SourceRecord, "captured_at"): datetime,
    (SourceRecord, "retrieved_by_run_id"): str,
    (SourceRecord, "content_hash"): str,
    (SourceRecord, "source_fingerprint"): str,
    (ApprovalRequest, "approval_id"): str,
    (ApprovalRequest, "task_id"): str,
    (ApprovalRequest, "run_id"): Optional[str],
    (ApprovalRequest, "requested_at"): datetime,
    (ApprovalRequest, "requested_action"): str,
    (ApprovalRequest, "reason"): str,
    (ApprovalRequest, "diff_ref"): Optional[str],
    (SideNote, "note_id"): str,
    (SideNote, "created_at"): datetime,
    (SideNote, "linked_source_refs"): list[str],
    (SideNote, "claim"): str,
    (SideNote, "follow_up_ref"): Optional[str],
    (DigestionItem, "digestion_id"): str,
    (DigestionItem, "side_note_id"): str,
    (DigestionItem, "created_at"): datetime,
    (DigestionItem, "user_response_ref"): Optional[str],
    (DigestionItem, "next_review_at"): Optional[datetime],
}


@pytest.mark.parametrize("model", list(EXPECTED_FIELDS))
def test_field_set_matches_stage0_stub(model):
    assert set(model.model_fields) == EXPECTED_FIELDS[model]


@pytest.mark.parametrize("model_field, expected_values", EXPECTED_LITERAL_VALUES.items())
def test_literal_value_sets_match_stage0_stub(model_field, expected_values):
    model, field_name = model_field
    annotation = model.model_fields[field_name].annotation
    assert get_origin(annotation) is Literal
    assert set(get_args(annotation)) == expected_values


@pytest.mark.parametrize("model_field, expected_annotation", EXPECTED_NON_LITERAL_TYPES.items())
def test_bare_non_literal_types_match_stage0_stub(model_field, expected_annotation):
    model, field_name = model_field
    assert model.model_fields[field_name].annotation == expected_annotation

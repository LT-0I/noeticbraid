from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel

# contract_version: 0.1.0 (DRAFT)
# status: non-authoritative
# TODO: TASK-1.1.4 GPT-A complete implementation + tests + local double-review PASS,
# then local main Claude session freezes 1.0.0 and reverse-syncs this stub.


class Task(BaseModel):
    task_id: str
    task_type: Literal["project_planning", "research", "code_review"]
    risk_level: Literal["low", "medium", "high"]
    approval_level: Literal["none", "light", "strong", "forbidden"]
    created_at: datetime
    status: Literal["draft", "ready", "queued", "running", "waiting_for_user", "failed", "completed"]
    user_request: str
    source_channel: Literal["console", "obsidian", "im", "schedule", "local"]
    account_hint: Optional[str]
    project_ref: Optional[str]


class RunRecord(BaseModel):
    run_id: str
    task_id: str
    event_type: Literal["task_created", "task_classified", "context_built", "approval_requested", "approval_decision_recorded", "web_ai_call_requested", "profile_health_checked", "source_record_linked", "artifact_created", "security_violation", "lesson_candidate_created", "routing_advice_recorded", "task_completed", "task_failed"]
    created_at: datetime
    actor: Literal["user", "system", "model", "local_review"]
    model_refs: list[str]
    source_refs: list[str]
    artifact_refs: list[str]
    routing_advice: Optional[str]
    status: Literal["draft", "recorded", "failed"]


class SourceRecord(BaseModel):
    source_ref_id: str
    source_type: Literal["user_note", "web_page", "github_repo", "paper", "patent", "video", "ai_output", "paid_database"]
    title: str
    canonical_url: Optional[str]
    local_path: Optional[str]
    author: Optional[str]
    captured_at: datetime
    retrieved_by_run_id: str
    content_hash: str
    source_fingerprint: str
    quality_score: Literal["low", "medium", "high", "unknown"]
    relevance_score: Literal["low", "medium", "high", "unknown"]
    evidence_role: Literal["user_context", "reference_project", "source_grounding", "contradiction", "memory_update_evidence"]
    used_for_purpose: Literal["project_positioning", "constraint_extraction", "source_grounding", "prior_art_check", "other"]


class ApprovalRequest(BaseModel):
    approval_id: str
    task_id: str
    run_id: Optional[str]
    approval_level: Literal["none", "light", "strong", "forbidden"]
    requested_at: datetime
    requested_action: str
    reason: str
    diff_ref: Optional[str]
    status: Literal["pending", "approved", "rejected", "blocked"]


class SideNote(BaseModel):
    note_id: str
    created_at: datetime
    linked_source_refs: list[str]
    note_type: Literal["fact", "hypothesis", "challenge", "action"]
    claim: str
    confidence: Literal["low", "medium", "high"]
    user_response: Literal["unread", "accepted", "rejected", "modified"]
    follow_up_ref: Optional[str]


class DigestionItem(BaseModel):
    digestion_id: str
    side_note_id: str
    created_at: datetime
    c_status: Literal["c0", "c1", "c2", "c3", "c4", "cX"]
    user_response_ref: Optional[str]
    next_review_at: Optional[datetime]
    status: Literal["open", "closed", "rejected", "snoozed"]

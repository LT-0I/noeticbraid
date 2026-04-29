# contract_version: 1.0.0
# status: authoritative
# frozen: true
# stage1_implementation_commit: b8d7152
# stage1_review_claude: docs/reviews/phase1.1/stage1_claude.md (PASS, 0D 0S)
# stage1_review_codex: docs/reviews/phase1.1/stage1_codex.md (PASS, 0D 0S)
#
# CONTRACT_NOTE (global, applies to all 6 models):
#   model_config = ConfigDict(
#       extra="forbid",
#       frozen=False,
#       str_strip_whitespace=True,
#       validate_assignment=True,  # M-1 from Stage 1 Claude review:
#                                  # field reassignment triggers secondary validation
#   )
#   Datetime normalizers treat naive datetimes as UTC and convert aware datetimes
#   to UTC with astimezone(timezone.utc).
#   Optional string normalizers convert blank strings to None before validation.
#
# CONTRACT_NOTE (Task):
#   task_id: pattern=r"^task_[A-Za-z0-9_]+$", min_length=1, max_length=128
#   task_type: required (no default); 3 Literal values
#   risk_level: required (no default); 3 Literal values
#   approval_level: required (no default); 4 Literal values
#   created_at: default_factory=utc_now (timezone-aware UTC);
#               validator ensures naive→UTC, aware→astimezone UTC
#   status: default="draft"; 7 Literal values
#   user_request: min_length=1, max_length=8192
#   source_channel: required; 5 Literal values
#   account_hint: default=None, max_length=64; blank-string→None pre-validator
#   project_ref: default=None, max_length=128; blank-string→None pre-validator
#   methods:
#     - Task.is_terminal() -> bool  (status in {"failed", "completed"})
#     - Task.requires_user_approval() -> bool
#       (approval_level in {"light", "strong", "forbidden"})
#     - Task.to_event_dict() -> dict[str, str]
#       (returns {task_id, task_type, status, source_channel})
#
# CONTRACT_NOTE (RunRecord):
#   run_id: pattern=r"^run_[A-Za-z0-9_]+$", min_length=1, max_length=128
#   task_id: pattern=r"^task_[A-Za-z0-9_]+$", min_length=1, max_length=128
#   event_type: required; 14 Literal values
#   created_at: default_factory=utc_now; UTC-normalize validator
#   actor: required; 4 Literal values
#   model_refs: default_factory=list, max_length=100;
#               each item must match r"^model_[A-Za-z0-9_]+$"; no duplicates
#   source_refs: default_factory=list, max_length=100;
#                each item must match r"^source_[A-Za-z0-9_]+$"; no duplicates
#   artifact_refs: default_factory=list, max_length=100;
#                  each item must match r"^artifact_[A-Za-z0-9_]+$"; no duplicates
#   routing_advice: default=None, max_length=4096; blank-string→None pre-validator
#   status: default="draft"; 3 Literal values
#   methods:
#     - RunRecord.is_failure() -> bool
#       (status=="failed" or event_type in {"task_failed", "security_violation"})
#     - RunRecord.has_external_refs() -> bool
#       (any of model_refs/source_refs/artifact_refs)
#     - RunRecord.to_ledger_event_dict() -> dict[str, object]
#       (returns {run_id, task_id, event_type, actor, status, created_at_isoformat})
#
# CONTRACT_NOTE (SourceRecord):
#   source_ref_id: pattern=r"^source_[A-Za-z0-9_]+$", min_length=1, max_length=128
#   source_type: required; 8 Literal values
#   title: min_length=1, max_length=512
#   canonical_url: default=None, max_length=2048;
#                  if non-None, must start with http:// or https://;
#                  blank-string→None pre-validator
#   local_path: default=None, max_length=1024; blank-string→None pre-validator
#   author: default=None, max_length=256; blank-string→None pre-validator
#   captured_at: default_factory=utc_now; UTC-normalize validator
#   retrieved_by_run_id: pattern=r"^run_[A-Za-z0-9_]+$", min_length=1, max_length=128
#   content_hash: pattern=r"^sha256:[A-Fa-f0-9]{64}$", min_length=71, max_length=71;
#                 normalize-validator lowercases the hex portion
#                 (L-1 from Stage 1 Claude review). Storage form is lowercase only.
#   source_fingerprint: pattern=r"^fingerprint_[A-Za-z0-9_]+$", min_length=1, max_length=128
#   quality_score: default="unknown"; 4 Literal values
#   relevance_score: default="unknown"; 4 Literal values
#   evidence_role: required; 5 Literal values
#   used_for_purpose: required; 5 Literal values
#   methods:
#     - SourceRecord.has_location() -> bool  (canonical_url or local_path is non-None)
#     - SourceRecord.is_high_value() -> bool
#       (quality_score=="high" and relevance_score=="high")
#     - SourceRecord.to_evidence_key() -> str
#       (returns f"{source_ref_id}:{source_fingerprint}")
#
# CONTRACT_NOTE (ApprovalRequest):
#   approval_id: pattern=r"^approval_[A-Za-z0-9_]+$", min_length=1, max_length=128
#   task_id: pattern=r"^task_[A-Za-z0-9_]+$", min_length=1, max_length=128
#   run_id: default=None, max_length=128;
#           if non-None must match r"^run_[A-Za-z0-9_]+$";
#           blank-string→None pre-validator (L-2 from Stage 1 Claude review:
#           Pydantic v2 Optional[str] with pattern skips pattern check when value is None)
#   approval_level: required; 4 Literal values
#   requested_at: default_factory=utc_now; UTC-normalize validator
#   requested_action: min_length=1, max_length=2048
#   reason: min_length=1, max_length=4096
#   diff_ref: default=None, max_length=256; blank-string→None pre-validator
#   status: default="pending"; 4 Literal values
#   methods:
#     - ApprovalRequest.is_resolved() -> bool
#       (status in {"approved", "rejected", "blocked"})
#     - ApprovalRequest.is_approved() -> bool  (status=="approved")
#     - ApprovalRequest.needs_user_decision() -> bool
#       (status=="pending" and approval_level not in {"none", "forbidden"})
#
# CONTRACT_NOTE (SideNote):
#   note_id: pattern=r"^note_[A-Za-z0-9_]+$", min_length=1, max_length=128
#   created_at: default_factory=utc_now; UTC-normalize validator
#   linked_source_refs: default_factory=list, max_length=100;
#                       each item must match r"^source_[A-Za-z0-9_]+$"; no duplicates
#   note_type: required; 4 Literal values
#   claim: min_length=1, max_length=4096
#   confidence: required; 3 Literal values
#   user_response: default="unread"; 4 Literal values
#   follow_up_ref: default=None, max_length=128; blank-string→None pre-validator
#   methods:
#     - SideNote.has_sources() -> bool  (linked_source_refs is non-empty)
#     - SideNote.is_actionable() -> bool
#       (note_type in {"challenge", "action"} and user_response in {"unread", "modified"})
#     - SideNote.is_user_resolved() -> bool
#       (user_response in {"accepted", "rejected", "modified"})
#
# CONTRACT_NOTE (DigestionItem):
#   digestion_id: pattern=r"^digestion_[A-Za-z0-9_]+$", min_length=1, max_length=128
#   side_note_id: pattern=r"^note_[A-Za-z0-9_]+$", min_length=1, max_length=128
#   created_at: default_factory=utc_now; UTC-normalize validator
#   c_status: default="c0"; 6 Literal values
#   user_response_ref: default=None, max_length=128; blank-string→None pre-validator
#   next_review_at: default=None; UTC-normalize validator (None passthrough)
#   status: default="open"; 4 Literal values
#   methods:
#     - DigestionItem.is_overdue(now: datetime) -> bool
#       (only when next_review_at is not None and status in {"open", "snoozed"};
#        compares next_review_at <= ensure_utc_datetime(now))
#     - DigestionItem.is_closed() -> bool  (status in {"closed", "rejected"})
#     - DigestionItem.needs_review(now: datetime) -> bool
#       (status=="open" and is_overdue(now))

from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel


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

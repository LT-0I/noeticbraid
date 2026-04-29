/**
 * NoeticBraid Phase 1.1 Contract Types (TypeScript mirror)
 *
 * NOTE:
 *   contract_version: 1.0.0
 *   contract_status: AUTHORITATIVE
 *   contract_frozen: true
 *   stage1_implementation_commit: b8d7152
 *   contract_source_of_truth: docs/contracts/phase1_1_pydantic_schemas.py
 *                            + docs/contracts/phase1_1_openapi.yaml
 *                            + docs/contracts/phase1_1_api_contract.md
 *
 * This file is a hand-written TS mirror of the 6 frozen Pydantic schemas
 * and the 5 endpoint response shapes used by Phase 1.1 console.
 *
 * Constraint information (min_length, max_length, pattern, default) is
 * referenced from CONTRACT_NOTE block in the python stub; only field
 * name + bare type signature + Literal enum values are mirrored here
 * (contract diff equivalence rules per Step 6 v2 §3.3.10).
 *
 * DO NOT modify this file unless contract_version bumps. Phase 1.2 may
 * extend with additional types but must not narrow Phase 1.1 surface.
 */

// ============================================================
// 6 frozen schemas
// ============================================================

export type TaskType = 'project_planning' | 'research' | 'code_review'
export type RiskLevel = 'low' | 'medium' | 'high'
export type ApprovalLevel = 'none' | 'light' | 'strong' | 'forbidden'
export type TaskStatus =
  | 'draft'
  | 'ready'
  | 'queued'
  | 'running'
  | 'waiting_for_user'
  | 'failed'
  | 'completed'
export type SourceChannel = 'console' | 'obsidian' | 'im' | 'schedule' | 'local'

export interface Task {
  task_id: string
  task_type: TaskType
  risk_level: RiskLevel
  approval_level: ApprovalLevel
  created_at: string
  status: TaskStatus
  user_request: string
  source_channel: SourceChannel
  account_hint: string | null
  project_ref: string | null
}

export type EventType =
  | 'task_created'
  | 'task_classified'
  | 'context_built'
  | 'approval_requested'
  | 'approval_decision_recorded'
  | 'web_ai_call_requested'
  | 'profile_health_checked'
  | 'source_record_linked'
  | 'artifact_created'
  | 'security_violation'
  | 'lesson_candidate_created'
  | 'routing_advice_recorded'
  | 'task_completed'
  | 'task_failed'
export type Actor = 'user' | 'system' | 'model' | 'local_review'
export type RunStatus = 'draft' | 'recorded' | 'failed'

export interface RunRecord {
  run_id: string
  task_id: string
  event_type: EventType
  created_at: string
  actor: Actor
  model_refs: string[]
  source_refs: string[]
  artifact_refs: string[]
  routing_advice: string | null
  status: RunStatus
}

export type SourceType =
  | 'user_note'
  | 'web_page'
  | 'github_repo'
  | 'paper'
  | 'patent'
  | 'video'
  | 'ai_output'
  | 'paid_database'
export type ScoreLevel = 'low' | 'medium' | 'high' | 'unknown'
export type EvidenceRole =
  | 'user_context'
  | 'reference_project'
  | 'source_grounding'
  | 'contradiction'
  | 'memory_update_evidence'
export type UsedForPurpose =
  | 'project_positioning'
  | 'constraint_extraction'
  | 'source_grounding'
  | 'prior_art_check'
  | 'other'

export interface SourceRecord {
  source_ref_id: string
  source_type: SourceType
  title: string
  canonical_url: string | null
  local_path: string | null
  author: string | null
  captured_at: string
  retrieved_by_run_id: string
  content_hash: string
  source_fingerprint: string
  quality_score: ScoreLevel
  relevance_score: ScoreLevel
  evidence_role: EvidenceRole
  used_for_purpose: UsedForPurpose
}

export type ApprovalStatus = 'pending' | 'approved' | 'rejected' | 'blocked'

export interface ApprovalRequest {
  approval_id: string
  task_id: string
  run_id: string | null
  approval_level: ApprovalLevel
  requested_at: string
  requested_action: string
  reason: string
  diff_ref: string | null
  status: ApprovalStatus
}

export type NoteType = 'fact' | 'hypothesis' | 'challenge' | 'action'
export type Confidence = 'low' | 'medium' | 'high'
export type UserResponse = 'unread' | 'accepted' | 'rejected' | 'modified'

export interface SideNote {
  note_id: string
  created_at: string
  linked_source_refs: string[]
  note_type: NoteType
  claim: string
  confidence: Confidence
  user_response: UserResponse
  follow_up_ref: string | null
}

export type CStatus = 'c0' | 'c1' | 'c2' | 'c3' | 'c4' | 'cX'
export type DigestionStatus = 'open' | 'closed' | 'rejected' | 'snoozed'

export interface DigestionItem {
  digestion_id: string
  side_note_id: string
  created_at: string
  c_status: CStatus
  user_response_ref: string | null
  next_review_at: string | null
  status: DigestionStatus
}

// ============================================================
// 5 endpoint response shapes (Phase 1.1 console used)
// ============================================================

export interface HealthResponse {
  status: 'ok'
  contract_version: string // "1.0.0"
  authoritative: boolean // true
}

export interface EmptyDashboard {
  tasks: Task[]
  approvals: ApprovalRequest[]
  accounts: unknown[] // AccountProfile not exposed in Phase 1.1 console
}

export interface WorkspaceThreads {
  threads: Task[]
}

export interface RunLedgerRuns {
  runs: RunRecord[]
}

export interface ApprovalQueue {
  approvals: ApprovalRequest[]
}

/**
 * NoeticBraid contract types used by the console.
 * Frozen Phase 1.1/1.2 shapes remain intact; SDD-D2-02/D2-03 add contract
 * 1.3.0 surfaces and SDD-D2-04 adds the R6 candidate gate mirror.
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
// Endpoint response shapes
// ============================================================

export interface HealthResponse {
  status: 'ok'
  contract_version: string
  authoritative: boolean
}

export interface EmptyDashboard {
  tasks: Task[]
  approvals: ApprovalRequest[]
  accounts: unknown[]
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

// ============================================================
// SDD-D2-02 contract 1.3.0 additions
// ============================================================

export type CandidateStatus = 'candidate' | 'adopted' | 'confirmed' | 'archived'
export type R6GateStatus = 'candidate' | 'confirmed' | 'expired'
export type CapabilityEndType = 'cli' | 'web'
export type CapabilityStatus =
  | 'unknown'
  | 'available'
  | 'degraded'
  | 'unavailable'
  | 'healthy'
  | 'unhealthy'
  | 'not_implemented'
export type CapabilityHealthMode = 'mock' | 'live_opt_in'

export interface R6GateState {
  reuse_count: number
  ledger_evidence_refs: string[]
  adopted_at: string | null
  expires_at: string | null
  r6_gate_schema_version: '1.0.0'
}

export interface CandidateLesson {
  candidate_id: string
  project_id: 'omc-ingest'
  source_sdd_ids: string[]
  summary: string
  status: CandidateStatus
  upgrade_rule: string
  adopted_at: string | null
  adopted_by: string | null
  run_record_ref: string | null
  reuse_evidence_refs: string[]
  artifact_refs: string[]
  source_refs: string[]
  r6_gate?: R6GateState | null
}

export interface OMCExternalReference {
  source_ref: string
  title: string
  url: string
  mode: 'link-only'
}

export interface OMCProjectFixture {
  project: {
    project_id: 'omc-ingest'
    title: '吸收 OMC'
    project_type: 'ingestion'
    owner: 'user'
    status: string
  }
  task_card: OMCProjectTaskRequest
  external_references: OMCExternalReference[]
  candidates: CandidateLesson[]
  adopted_history: CandidateLesson[]
  run_records: RunRecord[]
}

export interface OMCProjectTaskRequest {
  task_id?: string
  title?: string
  prompt: string
  source_refs?: string[]
}

export interface OMCProjectTaskResponse {
  project_id: 'omc-ingest'
  task_id: string
  candidate_id: string
  convergence_markdown_ref: string
  run_record_ref: string
  artifact_refs: string[]
  candidate: CandidateLesson
  run_records: RunRecord[]
}

export interface OMCProjectCandidates {
  project_id: 'omc-ingest'
  candidates: CandidateLesson[]
}

export interface OMCProjectAdoptedHistory {
  project_id: 'omc-ingest'
  adopted_candidates: CandidateLesson[]
}

export interface CandidateAdoptionResponse {
  project_id: 'omc-ingest'
  candidate_id: string
  status: CandidateStatus
  adopted_at: string
  adopted_by: string
  run_record_ref: string
  adoption_artifact_ref: string
  ledger_refs: string[]
  candidate: CandidateLesson
}

export interface CapabilityHealthResult {
  capability_id: string
  mode: CapabilityHealthMode
  status: CapabilityStatus
  checked_at: string
  summary: string
  artifact_ref: string | null
  version?: string | null
  last_checked?: string | null
  error_msg?: string | null
}

export interface CapabilityRegistryEntry {
  capability_id: string
  display_name: string
  provider: string
  end_type: CapabilityEndType
  status: CapabilityStatus
  health_mode: CapabilityHealthMode
  last_checked_at: string | null
  last_result: CapabilityHealthResult | null
  source_ref: string
  first_stage: boolean
}

export interface CapabilitiesResponse {
  capabilities: CapabilityRegistryEntry[]
}

export interface CapabilityHealthCheckResponse {
  capability: CapabilityRegistryEntry
  result: CapabilityHealthResult
}

// ============================================================
// SDD-D8-01 read-only account status (frontend view-type only;
// consumes the already-shipped GET /api/account/status — no
// backend contract change)
// ============================================================

export type AccountLoginState = 'logged_in' | 'logged_out' | 'unknown'
export type AccountHealth = 'ok' | 'fail' | 'unknown'
export type AccountSnapshotState = 'ok' | 'racing'

export interface AccountStatusEntry {
  capability_id: string
  display_name: string
  provider: string
  end_type: CapabilityEndType
  login_state: AccountLoginState
  health: AccountHealth
  checked_at: string
  snapshot_state: AccountSnapshotState
}

export interface AccountStatusResponse {
  accounts: AccountStatusEntry[]
}

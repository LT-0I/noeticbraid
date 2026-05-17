export type PlatformTaskState =
  | 'created'
  | 'planning'
  | 'dispatching'
  | 'producing'
  | 'cross_validating'
  | 'delivered'
  | 'blocked'
  | 'error'

export type PlatformModality = 'document' | 'slides' | 'image' | 'poster' | 'video' | 'music'

export type PlatformDeliverableStatus = 'delivered' | 'converted' | 'blocked'
export type PlatformDeliverableProvenanceKind =
  | 'ai_produced_markdown'
  | 'local_format_conversion'
  | 'on_disk_unledgered_real_binary'
  | 'not_attempted'

export interface PlatformTask {
  task_id: string
  title: string
  state: PlatformTaskState
  created_ts: string
  updated_ts: string
  modality_targets: PlatformModality[]
}

export interface PlatformTaskListResponse {
  tasks: PlatformTask[]
}

export interface PlatformDeliverableResponse {
  deliverable: PlatformDeliverable
}

export interface PlatformDeliverable {
  title: string
  generated_at: string | null
  assigned_ts?: string | null
  modalities: DeliverableModality[]
  timeline?: TimelineEntry[]
}

export interface DeliverableModality {
  modality: PlatformModality
  status: PlatformDeliverableStatus
  title: string
  filename: string
  content_type: string
  bytes: number | null
  sha256: string | null
  download_url: string | null
  blocked_reason: string | null
  provenance: {
    source_task_id: string | null
    ledgered: boolean
    kind: PlatformDeliverableProvenanceKind
    note: string
    source_artifact_sha256?: string
  }
}

export interface TimelineEntry {
  label: string
  ts?: string | null
  tone: 'neutral' | 'active' | 'done' | 'blocked' | 'error'
}

export interface PlatformCreateTaskRequest {
  title: string
  modality_targets: PlatformModality[]
}

export interface PlatformTaskDetailResponse {
  task: PlatformTask
  ledger?: PlatformLedgerEvent[]
  artifacts?: PlatformArtifact[]
}

export interface PlatformAiDeltaFrame {
  type: 'ai_delta'
  task_id: string
  payload: Record<string, unknown>
}

export interface PlatformProgressFrame {
  type: 'progress'
  task_id: string
  message: string
  step?: number
  total?: number
}

export interface PlatformLedgerFrame {
  type: 'ledger'
  task_id: string
  event: PlatformLedgerEvent
}

export interface PlatformArtifactFrame extends PlatformArtifact {
  type: 'artifact'
  task_id: string
}

export interface PlatformBlockedFrame {
  type: 'blocked'
  task_id: string
  modality: string
  reason: string
}

export interface PlatformErrorFrame {
  type: 'error'
  task_id: string
  code: string
  reason: string
}

export type PlatformServerFrame =
  | PlatformAiDeltaFrame
  | PlatformProgressFrame
  | PlatformLedgerFrame
  | PlatformArtifactFrame
  | PlatformBlockedFrame
  | PlatformErrorFrame

export interface PlatformLedgerEvent {
  type?: string
  event_type?: string
  task_id?: string
  state?: PlatformTaskState | string
  message?: string
  reason?: string
  created_at?: string
  ts?: string
  payload?: Record<string, unknown>
  [key: string]: unknown
}

export interface PlatformArtifact {
  modality: string
  rel_path: string
  sha256: string
  bytes: number
  filename?: string
  content_type?: string
  download_url?: string
}

export type PlatformTranscribeResponse =
  | { status: 'ok'; text: string }
  | { text: string }
  | { status: 'not_provisioned' }

export type ConversationalModality = PlatformModality | 'text' | 'research' | 'code' | 'ppt' | 'web_ai'
export type RequirementCapabilityStatus = 'supported' | 'unavailable' | 'deferred'
export type RequirementCoarseState = 'pending' | 'in_progress' | 'done' | 'blocked'
export type ConversationRole = 'user' | 'assistant'
export type ConversationKind = 'message' | 'question' | 'answer' | 'coarse_status'

export interface PlatformConversationRow {
  ts: string
  role: ConversationRole
  kind: ConversationKind
  text: string
  requirement_id?: string
}

export interface PlatformCoarseStatusItem {
  requirement_id: string
  text: string
  coarse_state: RequirementCoarseState
  capability_status: RequirementCapabilityStatus
  blocked_reason?: string
}

export interface PlatformCapabilityNotice {
  modality: ConversationalModality
  capability_status: RequirementCapabilityStatus
  reason: string | null
  reason_zh: string | null
  reason_en: string | null
}

export interface PlatformTaskViewResponse {
  conversation: PlatformConversationRow[]
  deliverables: PlatformDeliverable[]
  coarse_status: PlatformCoarseStatusItem[]
  capability_notice: PlatformCapabilityNotice[]
}

export interface PlatformConversationCreateResponse {
  task: PlatformTask
  view: PlatformTaskViewResponse
}

export interface PlatformElicitRequest {
  raw_requirement: string
}

export interface PlatformConversationTurnRequest {
  text: string
}

export interface PlatformRequirementConfirmItem {
  id: string
  text: string
  modality: ConversationalModality
}

export interface PlatformRequirementConfirmResponse {
  requirements: {
    task_id: string
    schema_version: 1
    status: 'confirmed'
    confirmed_at: string
    requirements: Array<{
      id: string
      text: string
      modality: ConversationalModality
      capability_status: RequirementCapabilityStatus
      coarse_state: RequirementCoarseState
      blocked_reason?: string
    }>
  }
  view: PlatformTaskViewResponse
}

export interface PlatformCapabilityEntry {
  modality: ConversationalModality
  capability_status: RequirementCapabilityStatus
  reason_zh: string | null
  reason_en: string | null
}

export interface PlatformCapabilityRegistryResponse {
  capabilities: PlatformCapabilityEntry[]
}

export type PlatformOrchestrationPhase = 'running' | 'delivered' | 'capped' | 'deferred'

export interface PlatformOrchestrateStatusResponse {
  coarse_status: PlatformCoarseStatusItem[]
  phase: PlatformOrchestrationPhase
}

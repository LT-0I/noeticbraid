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

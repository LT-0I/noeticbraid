import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { getBearer } from './auth'

import type {
  PlatformAttachmentDeletedResponse,
  PlatformAttachmentHubSendRequest,
  PlatformAttachmentHubSendResponse,
  PlatformAttachmentResponse,
  PlatformAttachmentsResponse,
  PlatformDeliverableResponse,
  PlatformCapabilityRegistryResponse,
  PlatformConversationCreateResponse,
  PlatformConversationTurnRequest,
  PlatformElicitRequest,
  PlatformOrchestrateStatusResponse,
  PlatformPerTaskDeliverableItem,
  PlatformPerTaskDeliverablesResponse,
  PlatformRequirementConfirmItem,
  PlatformRequirementConfirmResponse,
  PlatformTaskViewResponse,
  PlatformArtifact,
  PlatformCreateTaskRequest,
  PlatformTask,
  PlatformTaskDetailResponse,
  PlatformTaskListResponse,
  PlatformTranscribeResponse,
} from '@/types/platform'

function requestUrl(url: string): string {
  if (typeof window === 'undefined') return url
  return new URL(url, window.location.origin).toString()
}

function wsUrl(path: string): string {
  if (typeof window === 'undefined') return path
  const url = new URL(path, window.location.origin)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  return url.toString()
}

function authHeaders(headers?: HeadersInit): HeadersInit {
  const token = getBearer()
  return token ? { ...(headers as Record<string, string> | undefined), Authorization: `Bearer ${token}` } : { ...(headers as Record<string, string> | undefined) }
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(requestUrl(url), {
    ...init,
    headers: authHeaders(init?.headers),
  })
  if (!response.ok) throw new Error(`HTTP ${response.status} ${url}`)
  return (await response.json()) as T
}

export class PlatformAttachmentError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string | null,
    message = `HTTP ${status} attachment`,
  ) {
    super(message)
    this.name = 'PlatformAttachmentError'
  }
}

async function fetchAttachmentJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(requestUrl(url), {
    ...init,
    headers: authHeaders(init?.headers),
  })
  if (!response.ok) {
    let detail: string | null = null
    try {
      const payload = (await response.json()) as { detail?: unknown }
      detail = typeof payload.detail === 'string' ? payload.detail : null
    } catch {
      detail = null
    }
    throw new PlatformAttachmentError(response.status, detail, `HTTP ${response.status} ${url}`)
  }
  return (await response.json()) as T
}

function normalizeTaskList(payload: PlatformTaskListResponse | PlatformTask[]): PlatformTaskListResponse {
  return Array.isArray(payload) ? { tasks: payload } : payload
}

function normalizeTaskDetail(payload: PlatformTaskDetailResponse | PlatformTask): PlatformTaskDetailResponse {
  return 'task' in payload ? payload : { task: payload }
}

function normalizePerTaskDeliverables(payload: unknown): PlatformPerTaskDeliverablesResponse {
  if (!payload || typeof payload !== 'object' || !Array.isArray((payload as { deliverables?: unknown }).deliverables)) {
    return { deliverables: [] }
  }
  const deliverables = (payload as { deliverables: unknown[] }).deliverables.flatMap((item): PlatformPerTaskDeliverableItem[] => {
    if (!item || typeof item !== 'object') return []
    const row = item as Record<string, unknown>
    const status = row.status
    if (status !== 'delivered' && status !== 'blocked') return []
    if (typeof row.requirement_id !== 'string' || typeof row.title !== 'string' || !row.title.trim()) return []
    return [{
      requirement_id: row.requirement_id,
      title: row.title,
      status,
      ...(typeof row.download_ref === 'string' ? { download_ref: row.download_ref } : {}),
      ...(typeof row.blocked_reason === 'string' ? { blocked_reason: row.blocked_reason } : {}),
    }]
  })
  return { deliverables }
}

export function createPlatformTaskSocket(taskId: string): WebSocket {
  return new WebSocket(wsUrl(`/platform/ws/tasks/${encodeURIComponent(taskId)}`))
}

export function platformAuthFrame(): { type: 'auth'; token: string } | null {
  const token = getBearer()
  return token ? { type: 'auth', token } : null
}

export async function fetchPlatformTasks(): Promise<PlatformTaskListResponse> {
  const payload = await fetchJson<PlatformTaskListResponse | PlatformTask[]>('/platform/tasks')
  return normalizeTaskList(payload)
}

export async function createPlatformTask(payload: PlatformCreateTaskRequest): Promise<PlatformTask> {
  const response = await fetchJson<PlatformTaskDetailResponse | PlatformTask>('/platform/tasks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return normalizeTaskDetail(response).task
}

export async function fetchPlatformTask(taskId: string): Promise<PlatformTaskDetailResponse> {
  const payload = await fetchJson<PlatformTaskDetailResponse | PlatformTask>(
    `/platform/tasks/${encodeURIComponent(taskId)}`,
  )
  return normalizeTaskDetail(payload)
}

export async function fetchPlatformDeliverable(): Promise<PlatformDeliverableResponse> {
  return fetchJson<PlatformDeliverableResponse>('/platform/deliverable')
}

export async function createConversationalPlatformTask(payload: { title: string }): Promise<PlatformConversationCreateResponse> {
  return fetchJson<PlatformConversationCreateResponse>('/platform/tasks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title: payload.title }),
  })
}

export async function elicitPlatformTask(taskId: string, payload: PlatformElicitRequest): Promise<{ view: PlatformTaskViewResponse }> {
  return fetchJson<{ view: PlatformTaskViewResponse }>(`/platform/tasks/${encodeURIComponent(taskId)}/elicit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function sendPlatformConversation(taskId: string, payload: PlatformConversationTurnRequest): Promise<{ view: PlatformTaskViewResponse }> {
  return fetchJson<{ view: PlatformTaskViewResponse }>(`/platform/tasks/${encodeURIComponent(taskId)}/conversation`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function confirmPlatformRequirements(
  taskId: string,
  requirements: PlatformRequirementConfirmItem[],
): Promise<PlatformRequirementConfirmResponse> {
  return fetchJson<PlatformRequirementConfirmResponse>(`/platform/tasks/${encodeURIComponent(taskId)}/requirements/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ requirements }),
  })
}

export async function fetchPlatformTaskView(taskId: string): Promise<PlatformTaskViewResponse> {
  return fetchJson<PlatformTaskViewResponse>(`/platform/tasks/${encodeURIComponent(taskId)}/view`)
}

export async function fetchPlatformTaskDeliverables(taskId: string): Promise<PlatformPerTaskDeliverablesResponse> {
  const payload = await fetchJson<unknown>(`/platform/tasks/${encodeURIComponent(taskId)}/deliverables`)
  return normalizePerTaskDeliverables(payload)
}

export async function fetchPlatformCapabilities(): Promise<PlatformCapabilityRegistryResponse> {
  return fetchJson<PlatformCapabilityRegistryResponse>('/platform/capabilities')
}

export async function postOrchestrate(taskId: string): Promise<{ view: PlatformTaskViewResponse }> {
  return fetchJson<{ view: PlatformTaskViewResponse }>(`/platform/tasks/${encodeURIComponent(taskId)}/orchestrate`, {
    method: 'POST',
  })
}

export async function getOrchestrateStatus(taskId: string): Promise<PlatformOrchestrateStatusResponse> {
  return fetchJson<PlatformOrchestrateStatusResponse>(`/platform/tasks/${encodeURIComponent(taskId)}/orchestrate/status`)
}

export async function transcribePlatformAudio(blob: Blob): Promise<PlatformTranscribeResponse> {
  const form = new FormData()
  form.append('audio', blob, 'voice-input.webm')
  return fetchJson<PlatformTranscribeResponse>('/platform/stt/transcribe', {
    method: 'POST',
    body: form,
  })
}

export async function uploadPlatformAttachment(taskId: string, file: File): Promise<PlatformAttachmentResponse> {
  const form = new FormData()
  form.append('file', file, file.name)
  return fetchAttachmentJson<PlatformAttachmentResponse>(`/platform/tasks/${encodeURIComponent(taskId)}/attachments`, {
    method: 'POST',
    body: form,
  })
}

export async function fetchPlatformAttachments(taskId: string): Promise<PlatformAttachmentsResponse> {
  return fetchAttachmentJson<PlatformAttachmentsResponse>(`/platform/tasks/${encodeURIComponent(taskId)}/attachments`)
}

export async function deletePlatformAttachment(taskId: string, attachmentId: string): Promise<PlatformAttachmentDeletedResponse> {
  const url = `/platform/tasks/${encodeURIComponent(taskId)}/attachments/${encodeURIComponent(attachmentId)}`
  const response = await fetch(requestUrl(url), {
    method: 'DELETE',
    headers: authHeaders(),
  })
  if (response.status === 404) return { deleted: true }
  if (!response.ok) {
    let detail: string | null = null
    try {
      const payload = (await response.json()) as { detail?: unknown }
      detail = typeof payload.detail === 'string' ? payload.detail : null
    } catch {
      detail = null
    }
    throw new PlatformAttachmentError(response.status, detail, `HTTP ${response.status} ${url}`)
  }
  return (await response.json()) as PlatformAttachmentDeletedResponse
}

export async function sendPlatformAttachmentToHub(
  taskId: string,
  attachmentId: string,
  body?: PlatformAttachmentHubSendRequest,
): Promise<PlatformAttachmentHubSendResponse> {
  return fetchAttachmentJson<PlatformAttachmentHubSendResponse>(`/platform/tasks/${encodeURIComponent(taskId)}/attachments/${encodeURIComponent(attachmentId)}/send-to-hub`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {}),
  })
}

export async function downloadPlatformAttachment(taskId: string, attachmentId: string, filename: string): Promise<void> {
  return downloadBlob(`/platform/tasks/${encodeURIComponent(taskId)}/attachments/${encodeURIComponent(attachmentId)}`, filename, authHeaders())
}

export async function fetchPlatformArtifactBlob(artifact: PlatformArtifact): Promise<Blob> {
  const url = artifact.download_url ?? `/platform/artifacts?path=${encodeURIComponent(artifact.rel_path)}`
  const response = await fetch(requestUrl(url), { headers: authHeaders() })
  if (!response.ok) throw new Error(`HTTP ${response.status} artifact`)
  return response.blob()
}

export async function downloadBlob(url: string, filename: string, headers?: HeadersInit): Promise<void> {
  const response = await fetch(requestUrl(url), { headers: authHeaders(headers) })
  if (!response.ok) throw new Error(`HTTP ${response.status} download`)
  const blob = await response.blob()
  const objectUrl = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = objectUrl
  anchor.download = filename
  document.body.append(anchor)
  anchor.click()
  anchor.remove()
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000)
}

export const usePlatformTasks = (enabled = true) =>
  useQuery({
    queryKey: ['platform', 'tasks'],
    queryFn: fetchPlatformTasks,
    enabled,
  })

export const usePlatformTask = (taskId: string, enabled = true) =>
  useQuery({
    queryKey: ['platform', 'tasks', taskId],
    queryFn: () => fetchPlatformTask(taskId),
    enabled,
  })

export const usePlatformDeliverable = (enabled = true) =>
  useQuery({
    queryKey: ['platform', 'deliverable'],
    queryFn: fetchPlatformDeliverable,
    enabled,
  })

export const useCreatePlatformTask = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: createPlatformTask,
    onSuccess: (task) => {
      void queryClient.invalidateQueries({ queryKey: ['platform', 'tasks'] })
      void queryClient.setQueryData(['platform', 'tasks', task.task_id], { task })
    },
  })
}

export const usePlatformTaskView = (taskId: string, enabled = true) =>
  useQuery({
    queryKey: ['platform', 'tasks', taskId, 'view'],
    queryFn: () => fetchPlatformTaskView(taskId),
    enabled,
  })

export const usePlatformTaskDeliverables = (taskId: string, enabled = true) =>
  useQuery({
    queryKey: ['platform', 'tasks', taskId, 'deliverables'],
    queryFn: () => fetchPlatformTaskDeliverables(taskId),
    enabled: enabled && Boolean(taskId),
    retry: false,
  })

export const usePlatformAttachments = (taskId: string, enabled = true) =>
  useQuery({
    queryKey: ['platform', 'tasks', taskId, 'attachments'],
    queryFn: () => fetchPlatformAttachments(taskId),
    enabled: enabled && Boolean(taskId),
    retry: false,
  })

export const useUploadPlatformAttachment = (taskId: string) => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (file: File) => uploadPlatformAttachment(taskId, file),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['platform', 'tasks', taskId, 'attachments'] })
    },
  })
}

export const useDeletePlatformAttachment = (taskId: string) => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (attachmentId: string) => deletePlatformAttachment(taskId, attachmentId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['platform', 'tasks', taskId, 'attachments'] })
    },
  })
}

export const useSendPlatformAttachmentToHub = (taskId: string) => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ attachmentId, body }: { attachmentId: string; body?: PlatformAttachmentHubSendRequest }) => sendPlatformAttachmentToHub(taskId, attachmentId, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['platform', 'tasks', taskId, 'view'] })
    },
  })
}

export const usePlatformCapabilities = (enabled = true) =>
  useQuery({
    queryKey: ['platform', 'capabilities'],
    queryFn: fetchPlatformCapabilities,
    enabled,
  })

export const useOrchestrateStatus = (taskId: string, enabled = true) =>
  useQuery({
    queryKey: ['platform', 'tasks', taskId, 'orchestrate', 'status'],
    queryFn: () => getOrchestrateStatus(taskId),
    enabled,
  })

export const useCreateConversationalPlatformTask = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: createConversationalPlatformTask,
    onSuccess: (response) => {
      void queryClient.invalidateQueries({ queryKey: ['platform', 'tasks'] })
      void queryClient.setQueryData(['platform', 'tasks', response.task.task_id, 'view'], response.view)
      void queryClient.setQueryData(['platform', 'tasks', response.task.task_id], { task: response.task })
    },
  })
}

export const useElicitPlatformTask = (taskId: string) => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: PlatformElicitRequest) => elicitPlatformTask(taskId, payload),
    onSuccess: (response) => {
      void queryClient.setQueryData(['platform', 'tasks', taskId, 'view'], response.view)
    },
  })
}

export const useSendPlatformConversation = (taskId: string) => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: PlatformConversationTurnRequest) => sendPlatformConversation(taskId, payload),
    onSuccess: (response) => {
      void queryClient.setQueryData(['platform', 'tasks', taskId, 'view'], response.view)
    },
  })
}

export const useConfirmPlatformRequirements = (taskId: string) => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (requirements: PlatformRequirementConfirmItem[]) => confirmPlatformRequirements(taskId, requirements),
    onSuccess: (response) => {
      void queryClient.setQueryData(['platform', 'tasks', taskId, 'view'], response.view)
    },
  })
}

export const usePostOrchestrate = (taskId: string) => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => postOrchestrate(taskId),
    onSuccess: (response) => {
      void queryClient.setQueryData(['platform', 'tasks', taskId, 'view'], response.view)
      void queryClient.invalidateQueries({ queryKey: ['platform', 'tasks', taskId, 'orchestrate', 'status'] })
    },
  })
}

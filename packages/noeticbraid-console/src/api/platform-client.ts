import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { getBearer } from './auth'

import type {
  PlatformDeliverableResponse,
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

function normalizeTaskList(payload: PlatformTaskListResponse | PlatformTask[]): PlatformTaskListResponse {
  return Array.isArray(payload) ? { tasks: payload } : payload
}

function normalizeTaskDetail(payload: PlatformTaskDetailResponse | PlatformTask): PlatformTaskDetailResponse {
  return 'task' in payload ? payload : { task: payload }
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

export async function transcribePlatformAudio(blob: Blob): Promise<PlatformTranscribeResponse> {
  const form = new FormData()
  form.append('audio', blob, 'voice-input.webm')
  return fetchJson<PlatformTranscribeResponse>('/platform/stt/transcribe', {
    method: 'POST',
    body: form,
  })
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

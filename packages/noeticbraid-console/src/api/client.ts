import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import type {
  AccountStatusResponse,
  ApprovalQueue,
  CandidateAdoptionResponse,
  CapabilitiesResponse,
  CapabilityHealthCheckResponse,
  EmptyDashboard,
  HealthResponse,
  OMCProjectAdoptedHistory,
  OMCProjectCandidates,
  OMCProjectTaskRequest,
  OMCProjectTaskResponse,
  RunLedgerRuns,
  WorkspaceThreads,
} from '@/types/contracts'

function requestUrl(url: string): string {
  if (typeof window === 'undefined') {
    return url
  }
  return new URL(url, window.location.origin).toString()
}

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(requestUrl(url))
  if (!res.ok) throw new Error(`HTTP ${res.status} ${url}`)
  return (await res.json()) as T
}

async function postJson<T>(url: string, body?: unknown): Promise<T> {
  const res = await fetch(requestUrl(url), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status} ${url}`)
  return (await res.json()) as T
}

export const fetchOmcCandidates = () =>
  fetchJson<OMCProjectCandidates>('/api/projects/omc-ingest/candidates')
export const fetchOmcAdoptedHistory = () =>
  fetchJson<OMCProjectAdoptedHistory>('/api/projects/omc-ingest/adopted-history')
export const submitOmcTask = (payload: OMCProjectTaskRequest) =>
  postJson<OMCProjectTaskResponse>('/api/projects/omc-ingest/tasks', payload)
export const adoptCandidate = (candidateId: string) =>
  postJson<CandidateAdoptionResponse>(`/api/candidates/${candidateId}/adopt`)
export const fetchCapabilities = () => fetchJson<CapabilitiesResponse>('/api/capabilities')
// TODO(D8-02-auth): GET /api/account/status is bearer-protected (same auth as
// /api/account/pool) per SDD-D8-01. The console currently has no bearer/token
// mechanism in client.ts (fetchJson is unauthenticated; dev/test use MSW), so
// no auth header is injected here. When a console-wide bearer mechanism lands,
// route this call through it instead of inventing a new auth path.
export const fetchAccountStatus = () => fetchJson<AccountStatusResponse>('/api/account/status')
export const healthCheckCapability = (capabilityId: string) =>
  postJson<CapabilityHealthCheckResponse>(`/api/capabilities/${capabilityId}/health-check`)

export const useHealth = () =>
  useQuery({
    queryKey: ['health'],
    queryFn: () => fetchJson<HealthResponse>('/api/health'),
  })

export const useDashboardEmpty = () =>
  useQuery({
    queryKey: ['dashboard', 'empty'],
    queryFn: () => fetchJson<EmptyDashboard>('/api/dashboard/empty'),
  })

export const useWorkspaceThreads = () =>
  useQuery({
    queryKey: ['workspace', 'threads'],
    queryFn: () => fetchJson<WorkspaceThreads>('/api/workspace/threads'),
  })

export const useLedgerRuns = () =>
  useQuery({
    queryKey: ['ledger', 'runs'],
    queryFn: () => fetchJson<RunLedgerRuns>('/api/ledger/runs'),
  })

export const useApprovalQueue = () =>
  useQuery({
    queryKey: ['approval', 'queue'],
    queryFn: () => fetchJson<ApprovalQueue>('/api/approval/queue'),
  })

export const useOmcCandidates = () =>
  useQuery({
    queryKey: ['omc', 'candidates'],
    queryFn: fetchOmcCandidates,
  })

export const useOmcAdoptedHistory = () =>
  useQuery({
    queryKey: ['omc', 'adopted-history'],
    queryFn: fetchOmcAdoptedHistory,
  })

export const useCapabilities = () =>
  useQuery({
    queryKey: ['capabilities'],
    queryFn: fetchCapabilities,
  })

export const useAccountStatus = () =>
  useQuery({
    queryKey: ['account', 'status'],
    queryFn: fetchAccountStatus,
  })

export const useSubmitOmcTask = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: submitOmcTask,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['omc'] })
      void queryClient.invalidateQueries({ queryKey: ['ledger', 'runs'] })
    },
  })
}

export const useAdoptCandidate = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: adoptCandidate,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['omc'] })
      void queryClient.invalidateQueries({ queryKey: ['ledger', 'runs'] })
    },
  })
}

export const useCapabilityHealthCheck = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: healthCheckCapability,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['capabilities'] })
    },
  })
}

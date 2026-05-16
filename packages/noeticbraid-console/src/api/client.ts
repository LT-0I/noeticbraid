import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { AuthUnavailableError, clearBearer, ensureBearer, getBearer } from './auth'

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

function withAuth(headers?: HeadersInit): HeadersInit | undefined {
  const token = getBearer()
  if (!token) return headers
  return { ...(headers as Record<string, string> | undefined), Authorization: `Bearer ${token}` }
}

async function fetchJson<T>(url: string): Promise<T> {
  const doFetch = () => fetch(requestUrl(url), { headers: withAuth() })
  let res = await doFetch()
  if (res.status === 401) {
    clearBearer()
    const reboot = await ensureBearer()
    if (!reboot.ok) throw new AuthUnavailableError(reboot.mode ?? 'unknown')
    res = await doFetch()
    if (res.status === 401) throw new AuthUnavailableError('unauthorized')
  }
  if (!res.ok) throw new Error(`HTTP ${res.status} ${url}`)
  return (await res.json()) as T
}

async function postJson<T>(url: string, body?: unknown): Promise<T> {
  const doFetch = () =>
    fetch(requestUrl(url), {
      method: 'POST',
      headers: withAuth({ 'Content-Type': 'application/json' }),
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  let res = await doFetch()
  if (res.status === 401) {
    clearBearer()
    const reboot = await ensureBearer()
    if (!reboot.ok) throw new AuthUnavailableError(reboot.mode ?? 'unknown')
    res = await doFetch()
    if (res.status === 401) throw new AuthUnavailableError('unauthorized')
  }
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
// GET /api/account/status is bearer-protected (same auth as /api/account/pool)
// per SDD-D8-01/D8-02. fetchJson now injects the console-wide bearer and
// re-bootstraps once on 401, so this routes through the authed path.
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

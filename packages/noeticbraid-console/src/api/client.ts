import { useQuery } from '@tanstack/react-query'

import type {
  ApprovalQueue,
  EmptyDashboard,
  HealthResponse,
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

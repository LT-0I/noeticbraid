import { createRoute } from '@tanstack/react-router'

import { useDashboardEmpty, useHealth } from '@/api/client'
import { EmptyState } from '@/components/EmptyState'

import { rootRoute } from './__root'

function DashboardPage() {
  const health = useHealth()
  const dashboard = useDashboardEmpty()

  if (health.isLoading || dashboard.isLoading) {
    return <div data-testid="dashboard-loading">Loading...</div>
  }
  if (health.isError || dashboard.isError) {
    return <div data-testid="dashboard-error">Failed to load dashboard</div>
  }
  if (!health.data || !dashboard.data) {
    return <div data-testid="dashboard-loading">Loading...</div>
  }

  const isEmpty =
    dashboard.data.tasks.length === 0 &&
    dashboard.data.approvals.length === 0 &&
    dashboard.data.accounts.length === 0

  return (
    <section data-testid="dashboard-root">
      <h1>NoeticBraid Console</h1>
      <div data-testid="health-badge">
        contract {health.data.contract_version} ·{' '}
        {health.data.authoritative ? 'authoritative' : 'draft'}
      </div>
      {isEmpty ? (
        <EmptyState message="No tasks, approvals, or accounts yet." />
      ) : (
        <div data-testid="dashboard-summary">
          tasks: {dashboard.data.tasks.length} · approvals: {dashboard.data.approvals.length}
        </div>
      )}
    </section>
  )
}

export const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: DashboardPage,
})

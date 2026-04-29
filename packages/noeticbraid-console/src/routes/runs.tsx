import { createRoute } from '@tanstack/react-router'

import { useLedgerRuns } from '@/api/client'
import { EmptyState } from '@/components/EmptyState'

import { rootRoute } from './__root'

function RunsPage() {
  const runs = useLedgerRuns()

  if (runs.isLoading) {
    return <div data-testid="runs-loading">Loading...</div>
  }
  if (runs.isError) {
    return <div data-testid="runs-error">Failed to load run ledger</div>
  }
  if (!runs.data) {
    return <div data-testid="runs-loading">Loading...</div>
  }

  return (
    <section data-testid="runs-root">
      <h1>Run Ledger</h1>
      {runs.data.runs.length === 0 ? (
        <EmptyState message="No run records yet." />
      ) : (
        <ol data-testid="run-timeline">
          {runs.data.runs.map((run) => (
            <li key={run.run_id} data-testid={`run-item-${run.run_id}`}>
              <strong>{run.event_type}</strong> · {run.actor} · {run.status}
              {run.routing_advice ? <p>{run.routing_advice}</p> : null}
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}

export const runsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/runs',
  component: RunsPage,
})

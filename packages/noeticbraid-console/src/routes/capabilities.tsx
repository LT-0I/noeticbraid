import { createRoute } from '@tanstack/react-router'

import { useCapabilities, useCapabilityHealthCheck } from '@/api/client'

import { rootRoute } from './__root'

function CapabilitiesPage() {
  const capabilities = useCapabilities()
  const healthCheck = useCapabilityHealthCheck()

  if (capabilities.isLoading) {
    return <div data-testid="capabilities-loading">Loading...</div>
  }
  if (capabilities.isError) {
    return <div data-testid="capabilities-error">Failed to load capabilities</div>
  }
  if (!capabilities.data) {
    return <div data-testid="capabilities-loading">Loading...</div>
  }

  return (
    <section data-testid="capabilities-root">
      <h1>Capabilities</h1>
      <p data-testid="health-mode-note">Mock health checks by default; live checks require NOETICBRAID_HEALTH_CHECK_LIVE=1.</p>
      <ul data-testid="capability-list">
        {capabilities.data.capabilities.map((capability) => (
          <li key={capability.capability_id} data-testid={`capability-${capability.capability_id}`}>
            <strong>{capability.display_name}</strong> · {capability.provider} · {capability.end_type} ·{' '}
            {capability.health_mode} · {capability.status}
            {capability.last_checked_at ? <span> · checked {capability.last_checked_at}</span> : null}
            {capability.last_result ? <p>{capability.last_result.summary}</p> : null}
            <button
              type="button"
              data-testid={`health-check-${capability.capability_id}`}
              disabled={healthCheck.isPending}
              onClick={() => healthCheck.mutate(capability.capability_id)}
            >
              Trigger health-check
            </button>
          </li>
        ))}
      </ul>
      {healthCheck.data ? (
        <div data-testid="health-check-result">
          {healthCheck.data.capability.display_name}: {healthCheck.data.result.mode} ·{' '}
          {healthCheck.data.result.status}
        </div>
      ) : null}
    </section>
  )
}

export const capabilitiesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/capabilities',
  component: CapabilitiesPage,
})

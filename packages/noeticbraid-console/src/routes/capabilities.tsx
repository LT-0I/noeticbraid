import { createRoute } from '@tanstack/react-router'

import { useCapabilities, useCapabilityHealthCheck } from '@/api/client'
import type { CapabilityHealthResult, CapabilityRegistryEntry, CapabilityStatus } from '@/types/contracts'

import { rootRoute } from './__root'

const STATUS_COLORS: Partial<Record<CapabilityStatus, string>> = {
  healthy: 'green',
  unhealthy: 'red',
  not_implemented: 'gray',
}

function statusColor(status: CapabilityStatus): string {
  return STATUS_COLORS[status] ?? 'gray'
}

function latestChecked(capability: CapabilityRegistryEntry): string | null {
  return capability.last_result?.last_checked ?? capability.last_checked_at ?? capability.last_result?.checked_at ?? null
}

function ResultDetails({ result }: { result: CapabilityHealthResult }) {
  return (
    <dl data-testid={`health-result-details-${result.capability_id}`}>
      <div>
        <dt>Status</dt>
        <dd>
          <span
            data-testid={`result-status-badge-${result.capability_id}`}
            style={{ color: statusColor(result.status), fontWeight: 700 }}
          >
            {result.status}
          </span>
        </dd>
      </div>
      {result.version ? (
        <div>
          <dt>Version</dt>
          <dd data-testid={`result-version-${result.capability_id}`}>{result.version}</dd>
        </div>
      ) : null}
      {result.last_checked ? (
        <div>
          <dt>Last checked</dt>
          <dd data-testid={`result-last-checked-${result.capability_id}`}>{result.last_checked}</dd>
        </div>
      ) : null}
      {result.error_msg ? (
        <div>
          <dt>Error</dt>
          <dd data-testid={`result-error-${result.capability_id}`}>{result.error_msg}</dd>
        </div>
      ) : null}
    </dl>
  )
}

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
        {capabilities.data.capabilities.map((capability) => {
          const checked = latestChecked(capability)
          return (
            <li key={capability.capability_id} data-testid={`capability-${capability.capability_id}`}>
              <strong>{capability.display_name}</strong> · {capability.provider} · {capability.end_type} ·{' '}
              {capability.health_mode} ·{' '}
              <span
                data-testid={`status-badge-${capability.capability_id}`}
                style={{ color: statusColor(capability.status), fontWeight: 700 }}
              >
                {capability.status}
              </span>
              {checked ? <span data-testid={`last-checked-${capability.capability_id}`}> · checked {checked}</span> : null}
              {capability.last_result?.version ? (
                <span data-testid={`version-${capability.capability_id}`}> · version {capability.last_result.version}</span>
              ) : null}
              {capability.last_result?.error_msg ? (
                <p data-testid={`error-msg-${capability.capability_id}`}>{capability.last_result.error_msg}</p>
              ) : null}
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
          )
        })}
      </ul>
      {healthCheck.data ? (
        <div data-testid="health-check-result">
          {healthCheck.data.capability.display_name}: {healthCheck.data.result.mode} ·{' '}
          {healthCheck.data.result.status}
          <ResultDetails result={healthCheck.data.result} />
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

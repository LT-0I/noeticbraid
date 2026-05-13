import { createRoute } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { useCapabilities, useCapabilityHealthCheck } from '@/api/client'
import { Badge, Button, CapabilityStatusBadge, Card, CardBody, PageHeader } from '@/components/ui'
import type { CapabilityHealthResult, CapabilityRegistryEntry } from '@/types/contracts'

import { rootRoute } from './__root'

function latestChecked(capability: CapabilityRegistryEntry): string | null {
  return capability.last_result?.last_checked ?? capability.last_checked_at ?? capability.last_result?.checked_at ?? null
}

function ResultDetails({ result }: { result: CapabilityHealthResult }) {
  const { t } = useTranslation()

  return (
    <dl data-testid={`health-result-details-${result.capability_id}`} className="metadata-grid">
      <div className="metadata-item">
        <dt>{t('routes.capabilities.resultStatus')}</dt>
        <dd>
          <CapabilityStatusBadge capabilityId={result.capability_id} status={result.status} result />
        </dd>
      </div>
      {result.version ? (
        <div className="metadata-item">
          <dt>{t('routes.capabilities.resultVersion')}</dt>
          <dd data-testid={`result-version-${result.capability_id}`}>{result.version}</dd>
        </div>
      ) : null}
      {result.last_checked ? (
        <div className="metadata-item">
          <dt>{t('routes.capabilities.resultLastChecked')}</dt>
          <dd data-testid={`result-last-checked-${result.capability_id}`}>{result.last_checked}</dd>
        </div>
      ) : null}
      {result.error_msg ? (
        <div className="metadata-item">
          <dt>{t('routes.capabilities.resultError')}</dt>
          <dd data-testid={`result-error-${result.capability_id}`}>{result.error_msg}</dd>
        </div>
      ) : null}
    </dl>
  )
}

function CapabilitiesPage() {
  const { t } = useTranslation()
  const capabilities = useCapabilities()
  const healthCheck = useCapabilityHealthCheck()

  if (capabilities.isLoading) {
    return <div data-testid="capabilities-loading" className="state-panel">{t('state.loading')}</div>
  }
  if (capabilities.isError) {
    return <div data-testid="capabilities-error" className="state-panel state-panel--error">{t('errors.capabilities')}</div>
  }
  if (!capabilities.data) {
    return <div data-testid="capabilities-loading" className="state-panel">{t('state.loading')}</div>
  }

  return (
    <section data-testid="capabilities-root" className="stack">
      <PageHeader title={t('routes.capabilities.title')} subtitle={t('routes.capabilities.subtitle')} />

      <Card>
        <p data-testid="health-mode-note" className="text-muted">
          {t('routes.capabilities.healthModeNote')}
        </p>
        <ul data-testid="capability-list" className="item-list">
          {capabilities.data.capabilities.map((capability) => {
            const checked = latestChecked(capability)
            return (
              <li key={capability.capability_id} data-testid={`capability-${capability.capability_id}`} className="item-card">
                <div className="item-card__topline">
                  <h2 className="item-card__title">{capability.display_name}</h2>
                  <CapabilityStatusBadge capabilityId={capability.capability_id} status={capability.status} />
                </div>
                <dl className="metadata-grid">
                  <div className="metadata-item">
                    <dt>{t('routes.capabilities.provider')}</dt>
                    <dd>{capability.provider}</dd>
                  </div>
                  <div className="metadata-item">
                    <dt>{t('routes.capabilities.endType')}</dt>
                    <dd>{t(`end.${capability.end_type}`)}</dd>
                  </div>
                  <div className="metadata-item">
                    <dt>{t('routes.capabilities.healthMode')}</dt>
                    <dd>{t(`healthMode.${capability.health_mode}`)}</dd>
                  </div>
                </dl>
                {checked ? (
                  <span data-testid={`last-checked-${capability.capability_id}`} className="item-card__meta">
                    {t('routes.capabilities.checked', { checkedAt: checked })}
                  </span>
                ) : null}
                {capability.last_result?.version ? (
                  <span data-testid={`version-${capability.capability_id}`} className="item-card__meta">
                    {' '}{t('routes.capabilities.version', { version: capability.last_result.version })}
                  </span>
                ) : null}
                {capability.last_result?.error_msg ? (
                  <p data-testid={`error-msg-${capability.capability_id}`}>{capability.last_result.error_msg}</p>
                ) : null}
                {capability.last_result ? <p>{capability.last_result.summary}</p> : null}
                <Button
                  type="button"
                  data-testid={`health-check-${capability.capability_id}`}
                  disabled={healthCheck.isPending}
                  onClick={() => healthCheck.mutate(capability.capability_id)}
                >
                  {t('routes.capabilities.trigger')}
                </Button>
              </li>
            )
          })}
        </ul>
      </Card>

      {healthCheck.data ? (
        <Card data-testid="health-check-result">
          <CardBody>
            <div className="item-card__topline">
              <h2 className="item-card__title">{t('routes.capabilities.resultTitle')}</h2>
              <Badge tone="neutral">{healthCheck.data.capability.display_name}</Badge>
            </div>
            <p className="text-muted">
              {healthCheck.data.result.mode} · {t(`status.${healthCheck.data.result.status}`)}
            </p>
            <ResultDetails result={healthCheck.data.result} />
          </CardBody>
        </Card>
      ) : null}
    </section>
  )
}

export const capabilitiesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/capabilities',
  component: CapabilitiesPage,
})

import { createRoute } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { useDashboardEmpty, useHealth } from '@/api/client'
import { Badge, Card, CardBody, CardDescription, CardHeader, CardTitle, EmptyState, PageHeader } from '@/components/ui'

import { rootRoute } from './__root'

function DashboardPage() {
  const { t } = useTranslation()
  const health = useHealth()
  const dashboard = useDashboardEmpty()

  if (health.isLoading || dashboard.isLoading) {
    return <div data-testid="dashboard-loading" className="state-panel">{t('state.loading')}</div>
  }
  if (health.isError || dashboard.isError) {
    return <div data-testid="dashboard-error" className="state-panel state-panel--error">{t('errors.dashboard')}</div>
  }
  if (!health.data || !dashboard.data) {
    return <div data-testid="dashboard-loading" className="state-panel">{t('state.loading')}</div>
  }

  const isEmpty =
    dashboard.data.tasks.length === 0 &&
    dashboard.data.approvals.length === 0 &&
    dashboard.data.accounts.length === 0

  return (
    <section data-testid="dashboard-root" className="stack">
      <PageHeader title={t('routes.dashboard.title')} subtitle={t('routes.dashboard.subtitle')} />

      <Card>
        <CardHeader>
          <div>
            <CardTitle>{t('routes.dashboard.healthTitle')}</CardTitle>
            <CardDescription>{t('routes.dashboard.healthDescription')}</CardDescription>
          </div>
        </CardHeader>
        <CardBody>
          <div data-testid="health-badge" className="health-badge">
            <Badge tone="success">{t('routes.dashboard.contract', { version: health.data.contract_version })}</Badge>
            <span className="text-muted">
              {health.data.authoritative ? t('routes.dashboard.authoritative') : t('routes.dashboard.draft')}
            </span>
          </div>
        </CardBody>
      </Card>

      {isEmpty ? (
        <EmptyState title={t('empty.dashboard.title')} message={t('empty.dashboard.message')} />
      ) : (
        <Card data-testid="dashboard-summary">
          {t('routes.dashboard.summary', {
            tasks: dashboard.data.tasks.length,
            approvals: dashboard.data.approvals.length,
          })}
        </Card>
      )}
    </section>
  )
}

export const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: DashboardPage,
})

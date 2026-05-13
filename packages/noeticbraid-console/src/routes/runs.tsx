import { createRoute } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { useLedgerRuns } from '@/api/client'
import { Badge, Card, CardBody, EmptyState, PageHeader, Table } from '@/components/ui'

import { rootRoute } from './__root'

function RunsPage() {
  const { t } = useTranslation()
  const runs = useLedgerRuns()

  if (runs.isLoading) {
    return <div data-testid="runs-loading" className="state-panel">{t('state.loading')}</div>
  }
  if (runs.isError) {
    return <div data-testid="runs-error" className="state-panel state-panel--error">{t('errors.runs')}</div>
  }
  if (!runs.data) {
    return <div data-testid="runs-loading" className="state-panel">{t('state.loading')}</div>
  }

  return (
    <section data-testid="runs-root" className="stack">
      <PageHeader title={t('routes.runs.title')} subtitle={t('routes.runs.subtitle')} />
      {runs.data.runs.length === 0 ? (
        <EmptyState title={t('empty.runs.title')} message={t('empty.runs.message')} />
      ) : (
        <Card>
          <CardBody>
            <div className="ui-table-wrap">
              <Table data-testid="run-timeline">
                <thead>
                  <tr>
                    <th>{t('routes.runs.event')}</th>
                    <th>{t('routes.runs.actor')}</th>
                    <th>{t('routes.runs.status')}</th>
                    <th>{t('routes.runs.created')}</th>
                    <th>{t('routes.runs.routingAdvice')}</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.data.runs.map((run) => (
                    <tr key={run.run_id} data-testid={`run-item-${run.run_id}`}>
                      <td className="mono">{t(`event.${run.event_type}`)}</td>
                      <td>{t(`actor.${run.actor}`)}</td>
                      <td>
                        <Badge tone={run.status === 'failed' ? 'danger' : run.status === 'recorded' ? 'success' : 'neutral'}>
                          {t(`status.${run.status}`)}
                        </Badge>
                      </td>
                      <td className="mono">{run.created_at}</td>
                      <td>{run.routing_advice ?? t('common.none')}</td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </div>
          </CardBody>
        </Card>
      )}
    </section>
  )
}

export const runsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/runs',
  component: RunsPage,
})

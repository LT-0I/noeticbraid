import { createRoute } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { useApprovalQueue } from '@/api/client'
import { Badge, Card, CardBody, EmptyState, PageHeader, Table } from '@/components/ui'

import { rootRoute } from './__root'

function ApprovalsPage() {
  const { t } = useTranslation()
  const approvals = useApprovalQueue()

  if (approvals.isLoading) {
    return <div data-testid="approvals-loading" className="state-panel">{t('state.loading')}</div>
  }
  if (approvals.isError) {
    return <div data-testid="approvals-error" className="state-panel state-panel--error">{t('errors.approvals')}</div>
  }
  if (!approvals.data) {
    return <div data-testid="approvals-loading" className="state-panel">{t('state.loading')}</div>
  }

  return (
    <section data-testid="approvals-root" className="stack">
      <PageHeader title={t('routes.approvals.title')} subtitle={t('routes.approvals.subtitle')} />
      {approvals.data.approvals.length === 0 ? (
        <EmptyState title={t('empty.approvals.title')} message={t('empty.approvals.message')} />
      ) : (
        <Card>
          <CardBody>
            <div className="ui-table-wrap">
              <Table data-testid="approval-list">
                <thead>
                  <tr>
                    <th>{t('routes.approvals.level')}</th>
                    <th>{t('routes.approvals.status')}</th>
                    <th>{t('routes.approvals.action')}</th>
                    <th>{t('routes.approvals.reason')}</th>
                    <th>{t('routes.approvals.requestedAt')}</th>
                  </tr>
                </thead>
                <tbody>
                  {approvals.data.approvals.map((approval) => (
                    <tr key={approval.approval_id} data-testid={`approval-item-${approval.approval_id}`}>
                      <td>
                        <Badge tone={approval.approval_level === 'strong' ? 'warning' : 'neutral'}>
                          {t(`approval.${approval.approval_level}`)}
                        </Badge>
                      </td>
                      <td>{t(`status.${approval.status}`)}</td>
                      <td>{approval.requested_action}</td>
                      <td>{approval.reason}</td>
                      <td className="mono">{approval.requested_at}</td>
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

export const approvalsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/approvals',
  component: ApprovalsPage,
})

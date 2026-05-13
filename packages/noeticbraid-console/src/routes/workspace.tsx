import { createRoute } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { useWorkspaceThreads } from '@/api/client'
import { Badge, Card, CardBody, CardDescription, CardHeader, CardTitle, EmptyState, PageHeader } from '@/components/ui'

import { rootRoute } from './__root'

function WorkspacePage() {
  const { t } = useTranslation()
  const threads = useWorkspaceThreads()

  if (threads.isLoading) {
    return <div data-testid="workspace-loading" className="state-panel">{t('state.loading')}</div>
  }
  if (threads.isError) {
    return <div data-testid="workspace-error" className="state-panel state-panel--error">{t('errors.workspace')}</div>
  }
  if (!threads.data) {
    return <div data-testid="workspace-loading" className="state-panel">{t('state.loading')}</div>
  }

  return (
    <section data-testid="workspace-root" className="stack">
      <PageHeader title={t('routes.workspace.title')} subtitle={t('routes.workspace.subtitle')} />
      {threads.data.threads.length === 0 ? (
        <EmptyState title={t('empty.workspace.title')} message={t('empty.workspace.message')} />
      ) : (
        <Card>
          <CardHeader>
            <div>
              <CardTitle>{t('routes.workspace.threadCount', { count: threads.data.threads.length })}</CardTitle>
              <CardDescription>{t('routes.workspace.request')}</CardDescription>
            </div>
          </CardHeader>
          <CardBody>
            <ul data-testid="thread-list" className="item-list">
              {threads.data.threads.map((thread) => (
                <li key={thread.task_id} data-testid={`thread-item-${thread.task_id}`} className="item-card">
                  <div className="item-card__topline">
                    <h2 className="item-card__title">{t(`taskType.${thread.task_type}`)}</h2>
                    <Badge tone="neutral">{t(`status.${thread.status}`)}</Badge>
                    <Badge tone={thread.risk_level === 'high' ? 'danger' : thread.risk_level === 'medium' ? 'warning' : 'success'}>
                      {t(`risk.${thread.risk_level}`)}
                    </Badge>
                  </div>
                  <p>{thread.user_request}</p>
                  <dl className="metadata-grid">
                    <div className="metadata-item">
                      <dt>{t('routes.workspace.source')}</dt>
                      <dd>{t(`source.${thread.source_channel}`)}</dd>
                    </div>
                    <div className="metadata-item">
                      <dt>{t('routes.workspace.project')}</dt>
                      <dd>{thread.project_ref ?? t('common.none')}</dd>
                    </div>
                    <div className="metadata-item">
                      <dt>{t('routes.workspace.status')}</dt>
                      <dd>{t(`status.${thread.status}`)}</dd>
                    </div>
                  </dl>
                </li>
              ))}
            </ul>
          </CardBody>
        </Card>
      )}
    </section>
  )
}

export const workspaceRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/workspace',
  component: WorkspacePage,
})

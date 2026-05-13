import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

interface EmptyStateProps {
  title?: ReactNode
  message?: ReactNode
  action?: ReactNode
}

export function EmptyState({ title, message, action }: EmptyStateProps) {
  const { t } = useTranslation()

  return (
    <div className="empty-state" data-testid="empty-state" role="status">
      <div className="empty-state__mark" aria-hidden="true" />
      <div>
        <p className="empty-state__title">{title ?? t('empty.defaultTitle')}</p>
        <p className="empty-state__message">{message ?? t('empty.defaultMessage')}</p>
      </div>
      {action ? <div className="empty-state__action">{action}</div> : null}
    </div>
  )
}

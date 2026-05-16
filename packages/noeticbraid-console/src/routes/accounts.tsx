import { createRoute } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { useAuthState } from '@/api/auth-context'
import { useAccountStatus } from '@/api/client'
import {
  AccountHealthBadge,
  AccountLoginStateBadge,
  Card,
  CardBody,
  EmptyState,
  PageHeader,
} from '@/components/ui'

import { rootRoute } from './__root'

// Minimal UTC formatter (no codebase locale/date util exists; no new dependency).
// Falls back to the raw value if it is not a parseable ISO-8601 timestamp.
function formatUtc(value: string): string {
  const ms = Date.parse(value)
  if (Number.isNaN(ms)) return value
  return new Date(ms).toISOString().replace('T', ' ').replace('.000Z', 'Z')
}

function authModeLabel(t: ReturnType<typeof useTranslation>['t'], mode: string): string {
  const key = `auth.mode.${mode}`
  const label = t(key)
  return label === key ? mode : label
}

function AccountsPage() {
  const { t } = useTranslation()
  const auth = useAuthState()
  const accounts = useAccountStatus()

  if (auth.status === 'booting') {
    return <div data-testid="accounts-loading" className="state-panel">{t('state.loading')}</div>
  }
  if (auth.status === 'degraded') {
    return (
      <section data-testid="accounts-root" className="stack">
        <PageHeader title={t('routes.accounts.title')} subtitle={t('routes.accounts.subtitle')} />
        <div data-testid="auth-unavailable" className="state-panel state-panel--error">
          <EmptyState
            title={t('auth.unavailable.title')}
            message={t('auth.unavailable.message', { mode: authModeLabel(t, auth.mode) })}
          />
        </div>
      </section>
    )
  }

  if (accounts.isLoading) {
    return <div data-testid="accounts-loading" className="state-panel">{t('state.loading')}</div>
  }
  if (accounts.isError) {
    return <div data-testid="accounts-error" className="state-panel state-panel--error">{t('errors.accounts')}</div>
  }
  if (!accounts.data) {
    return <div data-testid="accounts-loading" className="state-panel">{t('state.loading')}</div>
  }

  return (
    <section data-testid="accounts-root" className="stack">
      <PageHeader title={t('routes.accounts.title')} subtitle={t('routes.accounts.subtitle')} />
      {accounts.data.accounts.length === 0 ? (
        <EmptyState title={t('empty.accounts.title')} message={t('empty.accounts.message')} />
      ) : (
        <Card>
          <CardBody>
            <ul data-testid="account-list" className="item-list">
              {accounts.data.accounts.map((account) => (
                <li
                  key={account.capability_id}
                  data-testid={`account-item-${account.capability_id}`}
                  className="item-card"
                >
                  <div className="item-card__topline">
                    <h2 className="item-card__title">{account.display_name}</h2>
                    <AccountHealthBadge capabilityId={account.capability_id} value={account.health} />
                  </div>
                  <dl className="metadata-grid">
                    <div className="metadata-item">
                      <dt>{t('routes.accounts.provider')}</dt>
                      <dd>{t(`provider.${account.provider}`)}</dd>
                    </div>
                    <div className="metadata-item">
                      <dt>{t('routes.accounts.endType')}</dt>
                      <dd>{t(`endType.${account.end_type}`)}</dd>
                    </div>
                    <div className="metadata-item">
                      <dt>{t('routes.accounts.loginState')}</dt>
                      <dd>
                        <AccountLoginStateBadge
                          capabilityId={account.capability_id}
                          value={account.login_state}
                        />
                      </dd>
                    </div>
                    <div className="metadata-item">
                      <dt>{t('routes.accounts.checkedAt')}</dt>
                      <dd>
                        <time className="mono">{formatUtc(account.checked_at)}</time>
                      </dd>
                    </div>
                    {account.snapshot_state === 'racing' && (
                      <div className="metadata-item">
                        <dt>{t('routes.accounts.snapshot')}</dt>
                        <dd>
                          <span className="text-muted">{t('snapshot.racing')}</span>
                        </dd>
                      </div>
                    )}
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

export const accountsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/accounts',
  component: AccountsPage,
})

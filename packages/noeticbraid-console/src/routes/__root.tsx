import { createRootRoute, Link, Outlet } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import '@/i18n'
import { LanguageToggle } from '@/components/ui'

type NavItem = {
  to: string
  labelKey: string
  testId: string
  exact?: boolean
}

const navItems: readonly NavItem[] = [
  { to: '/', labelKey: 'nav.dashboard', testId: 'nav-dashboard', exact: true },
  { to: '/workspace', labelKey: 'nav.workspace', testId: 'nav-workspace' },
  { to: '/runs', labelKey: 'nav.runs', testId: 'nav-runs' },
  { to: '/approvals', labelKey: 'nav.approvals', testId: 'nav-approvals' },
  { to: '/projects/omc-ingest', labelKey: 'nav.projects', testId: 'nav-projects' },
  { to: '/capabilities', labelKey: 'nav.capabilities', testId: 'nav-capabilities' },
]

function RootLayout() {
  const { t } = useTranslation()

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        {t('nav.skipToMain')}
      </a>
      <aside className="sidebar" aria-label={t('nav.primary')}>
        <div className="brand-lockup">
          <div className="brand-mark" aria-hidden="true">
            NB
          </div>
          <div className="brand-copy">
            <div className="brand-title">{t('app.product')}</div>
            <div className="brand-kicker">{t('app.kicker')}</div>
          </div>
        </div>

        <nav className="sidebar-nav">
          {navItems.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              data-testid={item.testId}
              className="sidebar-link"
              activeProps={{ className: 'sidebar-link sidebar-link--active' }}
              activeOptions={{ exact: item.exact ?? false }}
            >
              {t(item.labelKey)}
            </Link>
          ))}
        </nav>

        <div className="sidebar-note">
          <strong>{t('app.sidebarNoteTitle')}</strong>
          {t('app.sidebarNote')}
        </div>
      </aside>

      <div className="main-column">
        <header className="topbar">
          <span className="sr-only">{t('app.subtitle')}</span>
          <LanguageToggle />
        </header>
        <main className="main-content" id="main-content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

export const rootRoute = createRootRoute({
  component: RootLayout,
})

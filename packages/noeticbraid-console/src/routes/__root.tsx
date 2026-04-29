import { createRootRoute, Link, Outlet } from '@tanstack/react-router'

export const rootRoute = createRootRoute({
  component: () => (
    <div>
      <nav style={{ display: 'flex', gap: 16, padding: 16, borderBottom: '1px solid #ddd' }}>
        <Link to="/" data-testid="nav-dashboard">Dashboard</Link>
        <Link to="/workspace" data-testid="nav-workspace">Workspace</Link>
        <Link to="/runs" data-testid="nav-runs">Runs</Link>
        <Link to="/approvals" data-testid="nav-approvals">Approvals</Link>
      </nav>
      <main style={{ padding: 16 }}>
        <Outlet />
      </main>
    </div>
  ),
})

import { createRoute } from '@tanstack/react-router'

import { useApprovalQueue } from '@/api/client'
import { EmptyState } from '@/components/EmptyState'

import { rootRoute } from './__root'

function ApprovalsPage() {
  const approvals = useApprovalQueue()

  if (approvals.isLoading) {
    return <div data-testid="approvals-loading">Loading...</div>
  }
  if (approvals.isError) {
    return <div data-testid="approvals-error">Failed to load approval queue</div>
  }
  if (!approvals.data) {
    return <div data-testid="approvals-loading">Loading...</div>
  }

  return (
    <section data-testid="approvals-root">
      <h1>Approval Queue</h1>
      {approvals.data.approvals.length === 0 ? (
        <EmptyState message="No pending approvals yet." />
      ) : (
        <ul data-testid="approval-list">
          {approvals.data.approvals.map((approval) => (
            <li key={approval.approval_id} data-testid={`approval-item-${approval.approval_id}`}>
              <strong>{approval.approval_level}</strong> · {approval.status} ·{' '}
              {approval.requested_action}
              <p>{approval.reason}</p>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

export const approvalsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/approvals',
  component: ApprovalsPage,
})

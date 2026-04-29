import { createRoute } from '@tanstack/react-router'

import { useWorkspaceThreads } from '@/api/client'
import { EmptyState } from '@/components/EmptyState'

import { rootRoute } from './__root'

function WorkspacePage() {
  const threads = useWorkspaceThreads()

  if (threads.isLoading) {
    return <div data-testid="workspace-loading">Loading...</div>
  }
  if (threads.isError) {
    return <div data-testid="workspace-error">Failed to load workspace threads</div>
  }
  if (!threads.data) {
    return <div data-testid="workspace-loading">Loading...</div>
  }

  return (
    <section data-testid="workspace-root">
      <h1>Workspace Threads</h1>
      {threads.data.threads.length === 0 ? (
        <EmptyState message="No workspace threads yet." />
      ) : (
        <ul data-testid="thread-list">
          {threads.data.threads.map((thread) => (
            <li key={thread.task_id} data-testid={`thread-item-${thread.task_id}`}>
              <strong>{thread.task_type}</strong> · {thread.status} · {thread.user_request}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

export const workspaceRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/workspace',
  component: WorkspacePage,
})

import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider, createMemoryHistory, createRouter } from '@tanstack/react-router'
import { http, HttpResponse } from 'msw'
import { describe, expect, test } from 'vitest'

import { server } from '../src/mocks/server'
import { routeTree } from '../src/routes/routeTree'

function renderAt(path: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  const router = createRouter({
    routeTree,
    history: createMemoryHistory({ initialEntries: [path] }),
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

describe('console routes', () => {
  test('dashboard renders empty state when API returns empty arrays', async () => {
    renderAt('/')
    await waitFor(() => expect(screen.getByTestId('dashboard-root')).toBeInTheDocument())
    expect(screen.getByTestId('empty-state')).toBeInTheDocument()
    expect(screen.getByTestId('health-badge')).toHaveTextContent('1.0.0')
  })

  test('workspace renders thread list from API', async () => {
    renderAt('/workspace')
    await waitFor(() =>
      expect(screen.getByTestId('thread-item-task_stage1_candidate_001')).toBeInTheDocument(),
    )
  })

  test('runs renders timeline from API', async () => {
    renderAt('/runs')
    await waitFor(() =>
      expect(screen.getByTestId('run-item-run_stage1_candidate_001')).toBeInTheDocument(),
    )
  })

  test('approvals renders queue from API', async () => {
    renderAt('/approvals')
    await waitFor(() =>
      expect(screen.getByTestId('approval-item-approval_stage1_candidate_001')).toBeInTheDocument(),
    )
  })

  test('loading state is shown while data fetches', async () => {
    // Slow the workspace endpoint so the loading branch is observable;
    // TanStack Router resolves the route asynchronously, and react-query
    // would otherwise transition to data before the first poll.
    server.use(
      http.get('/api/workspace/threads', async () => {
        await new Promise((resolve) => setTimeout(resolve, 100))
        return HttpResponse.json({ threads: [] })
      }),
    )
    renderAt('/workspace')
    expect(await screen.findByTestId('workspace-loading')).toBeInTheDocument()
  })

  test('error state is shown when API fails', async () => {
    server.use(http.get('/api/workspace/threads', () => new HttpResponse(null, { status: 500 })))
    renderAt('/workspace')
    await waitFor(() => expect(screen.getByTestId('workspace-error')).toBeInTheDocument())
  })
})

import { fireEvent, render, screen, waitFor } from '@testing-library/react'
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
    expect(screen.getByTestId('health-badge')).toHaveTextContent('1.3.0')
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

  test('renders Projects and Capabilities nav only for D2-02', async () => {
    renderAt('/')
    await waitFor(() => expect(screen.getByTestId('nav-projects')).toBeInTheDocument())

    expect(screen.getByTestId('nav-projects')).toHaveTextContent('Projects')
    expect(screen.getByTestId('nav-capabilities')).toHaveTextContent('Capabilities')
    expect(screen.queryByText('External References')).not.toBeInTheDocument()
    expect(screen.queryByText('SideNote Tracking')).not.toBeInTheDocument()
  })

  test('OMC project route shows task card candidates adopted history capabilities and run records', async () => {
    renderAt('/projects/omc-ingest')

    await waitFor(() => expect(screen.getByTestId('omc-project-root')).toBeInTheDocument())
    expect(screen.getByRole('heading', { name: '吸收 OMC' })).toBeInTheDocument()
    expect(screen.getByTestId('omc-task-card')).toHaveTextContent('Task card')
    expect(screen.getByTestId('project-chat-entry')).toHaveTextContent('card + adopt log')
    expect(screen.getByTestId('external-reference-pool')).toHaveTextContent('OMC_DEBATE_LOOP.md')
    expect(screen.getByTestId('candidate-item-memory_omc_ingest_debate_loop')).toBeInTheDocument()
    expect(screen.getByTestId('adopted-item-memory_omc_help_lesson')).toBeInTheDocument()
    expect(screen.getByTestId('mini-capability-cap_claude_code_cli')).toHaveTextContent('Claude Code CLI')
    expect(screen.getByTestId('omc-run-run_omc_ingest_debate_loop-lesson_candidate_created')).toBeInTheDocument()
  })

  test('OMC project candidate adopt button calls backend adoption endpoint', async () => {
    let adoptedId = ''
    server.use(
      http.post('/api/candidates/:id/adopt', ({ params }) => {
        adoptedId = String(params.id)
        return HttpResponse.json({
          project_id: 'omc-ingest',
          candidate_id: adoptedId,
          status: 'adopted',
          adopted_at: '2026-05-12T12:30:00Z',
          adopted_by: 'user',
          run_record_ref: 'run_omc_ingest_debate_loop',
          adoption_artifact_ref: `.omx/artifacts/candidate-adoption-${adoptedId}-20260512T123000Z.md`,
          ledger_refs: ['run_omc_ingest_debate_loop', `artifact_candidate_adoption_${adoptedId}_20260512T123000Z`],
          candidate: {
            candidate_id: adoptedId,
            project_id: 'omc-ingest',
            source_sdd_ids: ['SDD-D2-01', 'SDD-D2-02'],
            summary: 'adopted test candidate',
            status: 'adopted',
            upgrade_rule:
              'explicit user adoption OR reuse >=3 times with at least one independently checkable ledger run; not rejected is never sufficient',
            adopted_at: '2026-05-12T12:30:00Z',
            adopted_by: 'user',
            run_record_ref: 'run_omc_ingest_debate_loop',
            reuse_evidence_refs: [`artifact_candidate_adoption_${adoptedId}_20260512T123000Z`],
            artifact_refs: [`.omx/artifacts/candidate-adoption-${adoptedId}-20260512T123000Z.md`],
            source_refs: ['source_omc_metadata'],
          },
        })
      }),
    )
    renderAt('/projects/omc-ingest')
    await waitFor(() =>
      expect(screen.getByTestId('adopt-memory_omc_ingest_debate_loop')).toBeInTheDocument(),
    )

    fireEvent.click(screen.getByTestId('adopt-memory_omc_ingest_debate_loop'))

    await waitFor(() => expect(adoptedId).toBe('memory_omc_ingest_debate_loop'))
    await waitFor(() =>
      expect(screen.getByTestId('adopted-memory_omc_ingest_debate_loop')).toBeInTheDocument(),
    )
  })

  test('does not register external references or sidenote tracking routes', async () => {
    renderAt('/')
    await waitFor(() => expect(screen.getByTestId('nav-dashboard')).toBeInTheDocument())

    expect(screen.queryByTestId('nav-external-references')).not.toBeInTheDocument()
    expect(screen.queryByTestId('nav-sidenote-tracking')).not.toBeInTheDocument()
    expect(screen.queryByText('/external-references')).not.toBeInTheDocument()
    expect(screen.queryByText('/sidenote-tracking')).not.toBeInTheDocument()
  })
})

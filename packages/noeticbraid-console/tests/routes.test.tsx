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
    expect(screen.getByRole('heading', { name: 'Ingest OMC' })).toBeInTheDocument()
    expect(screen.getByTestId('omc-task-card')).toHaveTextContent('Task card')
    expect(screen.getByTestId('project-chat-entry')).toHaveTextContent('card + adopt log')
    expect(screen.getByTestId('external-reference-pool')).toHaveTextContent('OMC_DEBATE_LOOP.md')
    expect(screen.getByTestId('candidate-item-memory_omc_ingest_debate_loop')).toBeInTheDocument()
    expect(screen.getByTestId('adopted-item-memory_omc_help_lesson')).toBeInTheDocument()
    expect(screen.getByTestId('mini-capability-cap_claude_code_cli')).toHaveTextContent('Claude Code CLI')
    expect(screen.getByTestId('omc-run-run_omc_ingest_debate_loop-lesson_candidate_created')).toBeInTheDocument()
  })

  test('omc-ingest renders R6 gate badge', async () => {
    server.use(
      http.get('/api/projects/omc-ingest/candidates', () =>
        HttpResponse.json({
          project_id: 'omc-ingest',
          candidates: [
            {
              candidate_id: 'memory_r6_confirmed',
              project_id: 'omc-ingest',
              source_sdd_ids: ['SDD-D2-01', 'SDD-D2-02'],
              summary: 'confirmed through ledger-backed reuse',
              status: 'candidate',
              upgrade_rule:
                'explicit user adoption OR reuse >=3 times with at least one independently checkable ledger run; not rejected is never sufficient',
              adopted_at: null,
              adopted_by: null,
              run_record_ref: 'run_r6_confirmed',
              reuse_evidence_refs: [],
              artifact_refs: ['artifact_convergence_r6_confirmed'],
              source_refs: ['source_omc_metadata'],
              r6_gate: {
                reuse_count: 3,
                ledger_evidence_refs: ['run_a', 'run_b', 'run_c'],
                adopted_at: null,
                expires_at: null,
                r6_gate_schema_version: '1.0.0',
              },
            },
          ],
        }),
      ),
    )

    renderAt('/projects/omc-ingest')

    await waitFor(() => expect(screen.getByTestId('r6-gate-memory_r6_confirmed')).toBeInTheDocument())
    expect(screen.getByTestId('r6-gate-memory_r6_confirmed')).toHaveTextContent('R6Gate: confirmed')
    expect(screen.getByTestId('r6-gate-memory_r6_confirmed').style.color).toBe('green')
  })

  test('omc-ingest shows reuse count', async () => {
    server.use(
      http.get('/api/projects/omc-ingest/candidates', () =>
        HttpResponse.json({
          project_id: 'omc-ingest',
          candidates: [
            {
              candidate_id: 'memory_r6_reuse_count',
              project_id: 'omc-ingest',
              source_sdd_ids: ['SDD-D2-01', 'SDD-D2-02'],
              summary: 'candidate with reuse evidence count',
              status: 'candidate',
              upgrade_rule:
                'explicit user adoption OR reuse >=3 times with at least one independently checkable ledger run; not rejected is never sufficient',
              adopted_at: null,
              adopted_by: null,
              run_record_ref: 'run_r6_reuse_count',
              reuse_evidence_refs: [],
              artifact_refs: ['artifact_convergence_r6_reuse_count'],
              source_refs: ['source_omc_metadata'],
              r6_gate: {
                reuse_count: 2,
                ledger_evidence_refs: ['run_a', 'run_b'],
                adopted_at: null,
                expires_at: null,
                r6_gate_schema_version: '1.0.0',
              },
            },
          ],
        }),
      ),
    )

    renderAt('/projects/omc-ingest')

    await waitFor(() => expect(screen.getByTestId('r6-reuse-count-memory_r6_reuse_count')).toBeInTheDocument())
    expect(screen.getByTestId('r6-reuse-count-memory_r6_reuse_count')).toHaveTextContent('reuse count: 2')
  })

  test('omc-ingest renders R6 candidate fallback for legacy data', async () => {
    server.use(
      http.get('/api/projects/omc-ingest/candidates', () =>
        HttpResponse.json({
          project_id: 'omc-ingest',
          candidates: [
            {
              candidate_id: 'memory_r6_legacy_undefined',
              project_id: 'omc-ingest',
              source_sdd_ids: ['SDD-D2-01', 'SDD-D2-02'],
              summary: 'legacy candidate without r6 gate',
              status: 'candidate',
              upgrade_rule:
                'explicit user adoption OR reuse >=3 times with at least one independently checkable ledger run; not rejected is never sufficient',
              adopted_at: null,
              adopted_by: null,
              run_record_ref: 'run_r6_legacy_undefined',
              reuse_evidence_refs: [],
              artifact_refs: ['artifact_convergence_r6_legacy_undefined'],
              source_refs: ['source_omc_metadata'],
            },
            {
              candidate_id: 'memory_r6_legacy_null',
              project_id: 'omc-ingest',
              source_sdd_ids: ['SDD-D2-01', 'SDD-D2-02'],
              summary: 'legacy candidate with null r6 gate',
              status: 'candidate',
              upgrade_rule:
                'explicit user adoption OR reuse >=3 times with at least one independently checkable ledger run; not rejected is never sufficient',
              adopted_at: null,
              adopted_by: null,
              run_record_ref: 'run_r6_legacy_null',
              reuse_evidence_refs: [],
              artifact_refs: ['artifact_convergence_r6_legacy_null'],
              source_refs: ['source_omc_metadata'],
              r6_gate: null,
            },
          ],
        }),
      ),
    )

    renderAt('/projects/omc-ingest')

    await waitFor(() => expect(screen.getByTestId('r6-gate-memory_r6_legacy_undefined')).toBeInTheDocument())
    expect(screen.getByTestId('r6-gate-memory_r6_legacy_undefined')).toHaveTextContent('R6Gate: candidate')
    expect(screen.getByTestId('r6-gate-memory_r6_legacy_undefined').style.color).toBe('gray')
    expect(screen.getByTestId('r6-gate-memory_r6_legacy_null')).toHaveTextContent('R6Gate: candidate')
    expect(screen.getByTestId('r6-gate-memory_r6_legacy_null').style.color).toBe('gray')
  })

  test('omc-ingest renders R6 expired badge with strikethrough', async () => {
    server.use(
      http.get('/api/projects/omc-ingest/candidates', () =>
        HttpResponse.json({
          project_id: 'omc-ingest',
          candidates: [
            {
              candidate_id: 'memory_r6_expired',
              project_id: 'omc-ingest',
              source_sdd_ids: ['SDD-D2-01', 'SDD-D2-02'],
              summary: 'expired candidate gate',
              status: 'candidate',
              upgrade_rule:
                'explicit user adoption OR reuse >=3 times with at least one independently checkable ledger run; not rejected is never sufficient',
              adopted_at: null,
              adopted_by: null,
              run_record_ref: 'run_r6_expired',
              reuse_evidence_refs: [],
              artifact_refs: ['artifact_convergence_r6_expired'],
              source_refs: ['source_omc_metadata'],
              r6_gate: {
                reuse_count: 0,
                ledger_evidence_refs: [],
                adopted_at: null,
                expires_at: '2000-01-01T00:00:00Z',
                r6_gate_schema_version: '1.0.0',
              },
            },
          ],
        }),
      ),
    )

    renderAt('/projects/omc-ingest')

    await waitFor(() => expect(screen.getByTestId('r6-gate-memory_r6_expired')).toBeInTheDocument())
    expect(screen.getByTestId('r6-gate-memory_r6_expired')).toHaveTextContent('R6Gate: expired')
    expect(screen.getByTestId('r6-gate-memory_r6_expired').style.color).toBe('darkgray')
    expect(screen.getByTestId('r6-gate-memory_r6_expired').style.textDecoration).toBe('line-through')
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

  test('capabilities route shows status badge for healthy unhealthy and not implemented', async () => {
    server.use(
      http.get('/api/capabilities', () =>
        HttpResponse.json({
          capabilities: [
            {
              capability_id: 'cap_claude_code_cli',
              display_name: 'Claude Code CLI',
              provider: 'anthropic',
              end_type: 'cli',
              status: 'healthy',
              health_mode: 'live_opt_in',
              last_checked_at: '2026-05-12T12:30:00Z',
              last_result: null,
              source_ref: 'source_ai_invocation_reference',
              first_stage: true,
            },
            {
              capability_id: 'cap_codex_cli',
              display_name: 'Codex CLI',
              provider: 'openai',
              end_type: 'cli',
              status: 'unhealthy',
              health_mode: 'live_opt_in',
              last_checked_at: '2026-05-12T12:31:00Z',
              last_result: null,
              source_ref: 'source_ai_invocation_reference',
              first_stage: true,
            },
            {
              capability_id: 'cap_gemini_cli',
              display_name: 'Gemini CLI',
              provider: 'google',
              end_type: 'cli',
              status: 'unknown',
              health_mode: 'mock',
              last_checked_at: null,
              last_result: null,
              source_ref: 'source_ai_invocation_reference',
              first_stage: true,
            },
            {
              capability_id: 'cap_gemini_web',
              display_name: 'Gemini Web',
              provider: 'google',
              end_type: 'web',
              status: 'not_implemented',
              health_mode: 'live_opt_in',
              last_checked_at: '2026-05-12T12:32:00Z',
              last_result: null,
              source_ref: 'source_ai_invocation_reference',
              first_stage: true,
            },
          ],
        }),
      ),
    )

    renderAt('/capabilities')
    await waitFor(() => expect(screen.getByTestId('capabilities-root')).toBeInTheDocument())

    expect(screen.getByTestId('status-badge-cap_claude_code_cli')).toHaveTextContent('healthy')
    expect(screen.getByTestId('status-badge-cap_claude_code_cli').style.color).toBe('green')
    expect(screen.getByTestId('status-badge-cap_codex_cli')).toHaveTextContent('unhealthy')
    expect(screen.getByTestId('status-badge-cap_codex_cli').style.color).toBe('red')
    expect(screen.getByTestId('status-badge-cap_gemini_web')).toHaveTextContent('not_implemented')
    expect(screen.getByTestId('status-badge-cap_gemini_web').style.color).toBe('gray')
  })

  test('capabilities renders 5 entries', async () => {
    renderAt('/capabilities')
    await waitFor(() => expect(screen.getByTestId('capabilities-root')).toBeInTheDocument())

    expect(screen.getByTestId('capability-list').querySelectorAll('li')).toHaveLength(5)
    expect(screen.getByTestId('capability-cap_chatgpt_web')).toHaveTextContent('ChatGPT Web')
  })

  test('capabilities route shows version last checked and error message after manual trigger', async () => {
    let triggered = false
    const initialCapabilities = [
      {
        capability_id: 'cap_claude_code_cli',
        display_name: 'Claude Code CLI',
        provider: 'anthropic',
        end_type: 'cli',
        status: 'unknown',
        health_mode: 'mock',
        last_checked_at: null,
        last_result: null,
        source_ref: 'source_ai_invocation_reference',
        first_stage: true,
      },
      {
        capability_id: 'cap_codex_cli',
        display_name: 'Codex CLI',
        provider: 'openai',
        end_type: 'cli',
        status: 'unknown',
        health_mode: 'mock',
        last_checked_at: null,
        last_result: null,
        source_ref: 'source_ai_invocation_reference',
        first_stage: true,
      },
      {
        capability_id: 'cap_gemini_cli',
        display_name: 'Gemini CLI',
        provider: 'google',
        end_type: 'cli',
        status: 'unknown',
        health_mode: 'mock',
        last_checked_at: null,
        last_result: null,
        source_ref: 'source_ai_invocation_reference',
        first_stage: true,
      },
      {
        capability_id: 'cap_gemini_web',
        display_name: 'Gemini Web',
        provider: 'google',
        end_type: 'web',
        status: 'unknown',
        health_mode: 'mock',
        last_checked_at: null,
        last_result: null,
        source_ref: 'source_ai_invocation_reference',
        first_stage: true,
      },
    ]
    const codexResult = {
      capability_id: 'cap_codex_cli',
      mode: 'live_opt_in',
      status: 'healthy',
      checked_at: '2026-05-12T12:30:00Z',
      summary: 'Live health OK for Codex CLI; version parsed.',
      artifact_ref: '.omx/artifacts/health-check-cap_codex_cli-20260512T123000Z.json',
      version: 'codex 5.5',
      last_checked: '2026-05-12T12:30:00Z',
      error_msg: null,
    }
    const triggeredCapabilities = initialCapabilities.map((capability) => {
      if (capability.capability_id === 'cap_codex_cli') {
        return {
          ...capability,
          status: 'healthy',
          health_mode: 'live_opt_in',
          last_checked_at: codexResult.last_checked,
          last_result: codexResult,
        }
      }
      if (capability.capability_id === 'cap_gemini_web') {
        return {
          ...capability,
          status: 'not_implemented',
          health_mode: 'live_opt_in',
          last_checked_at: '2026-05-12T12:31:00Z',
          last_result: {
            capability_id: 'cap_gemini_web',
            mode: 'live_opt_in',
            status: 'not_implemented',
            checked_at: '2026-05-12T12:31:00Z',
            summary: 'real ping deferred to SDD-D2-03-hotfix-01',
            artifact_ref: null,
            version: null,
            last_checked: '2026-05-12T12:31:00Z',
            error_msg: 'real ping deferred to SDD-D2-03-hotfix-01',
          },
        }
      }
      return capability
    })
    server.use(
      http.get('/api/capabilities', () =>
        HttpResponse.json({ capabilities: triggered ? triggeredCapabilities : initialCapabilities }),
      ),
      http.post('/api/capabilities/:id/health-check', ({ params }) => {
        triggered = true
        const capability = triggeredCapabilities.find((item) => item.capability_id === params.id)
        return HttpResponse.json({ capability, result: codexResult })
      }),
    )

    renderAt('/capabilities')
    await waitFor(() => expect(screen.getByTestId('health-check-cap_codex_cli')).toBeInTheDocument())

    fireEvent.click(screen.getByTestId('health-check-cap_codex_cli'))

    await waitFor(() => expect(screen.getByTestId('result-version-cap_codex_cli')).toHaveTextContent('codex 5.5'))
    expect(screen.getByTestId('result-last-checked-cap_codex_cli')).toHaveTextContent('2026-05-12T12:30:00Z')
    await waitFor(() =>
      expect(screen.getByTestId('error-msg-cap_gemini_web')).toHaveTextContent(
        'real ping deferred to SDD-D2-03-hotfix-01',
      ),
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

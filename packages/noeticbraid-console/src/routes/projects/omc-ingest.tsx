import { createRoute } from '@tanstack/react-router'
import { useState } from 'react'

import {
  useAdoptCandidate,
  useCapabilities,
  useLedgerRuns,
  useOmcAdoptedHistory,
  useOmcCandidates,
  useSubmitOmcTask,
} from '@/api/client'
import type { CandidateLesson } from '@/types/contracts'

import { rootRoute } from '../__root'

const defaultPrompt = '吸收 OMC `omc help` slash 命令列表，整理成 NoeticBraid candidate lesson。'

function CandidateItem({ candidate }: { candidate: CandidateLesson }) {
  const adopt = useAdoptCandidate()
  const alreadyAdopted = candidate.status === 'adopted' || candidate.status === 'confirmed'
  return (
    <li data-testid={`candidate-item-${candidate.candidate_id}`}>
      <strong>{candidate.candidate_id}</strong> · {candidate.status}
      <p>{candidate.summary}</p>
      <p>run record: {candidate.run_record_ref ?? 'pending'}</p>
      <button
        type="button"
        data-testid={`adopt-${candidate.candidate_id}`}
        disabled={alreadyAdopted || adopt.isPending}
        onClick={() => adopt.mutate(candidate.candidate_id)}
      >
        {alreadyAdopted ? 'Adopted' : 'Adopt'}
      </button>
      {adopt.isSuccess ? <span data-testid={`adopted-${candidate.candidate_id}`}> adopted</span> : null}
    </li>
  )
}

function OmcIngestPage() {
  const [prompt, setPrompt] = useState(defaultPrompt)
  const candidates = useOmcCandidates()
  const adopted = useOmcAdoptedHistory()
  const capabilities = useCapabilities()
  const runs = useLedgerRuns()
  const submit = useSubmitOmcTask()

  if (candidates.isLoading || adopted.isLoading || capabilities.isLoading || runs.isLoading) {
    return <div data-testid="omc-loading">Loading...</div>
  }
  if (candidates.isError || adopted.isError || capabilities.isError || runs.isError) {
    return <div data-testid="omc-error">Failed to load OMC workspace</div>
  }
  if (!candidates.data || !adopted.data || !capabilities.data || !runs.data) {
    return <div data-testid="omc-loading">Loading...</div>
  }

  return (
    <section data-testid="omc-project-root">
      <h1>吸收 OMC</h1>
      <p data-testid="project-chat-entry">Project chat entry: card + adopt log only.</p>

      <section data-testid="omc-task-card">
        <h2>Task card</h2>
        <label htmlFor="omc-task-prompt">OMC ingestion prompt</label>
        <textarea
          id="omc-task-prompt"
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          rows={3}
          style={{ display: 'block', width: '100%', margin: '8px 0' }}
        />
        <button
          type="button"
          data-testid="submit-omc-task"
          disabled={submit.isPending}
          onClick={() =>
            submit.mutate({
              task_id: 'task_omc_ingest',
              title: '吸收 OMC `omc help` slash 命令列表',
              prompt,
              source_refs: [
                'source_project_definition_v3_2',
                'source_ai_invocation_reference',
                'source_omc_metadata',
              ],
            })
          }
        >
          Run OMC task
        </button>
        {submit.data ? <p data-testid="submitted-candidate">candidate {submit.data.candidate_id}</p> : null}
      </section>

      <section data-testid="external-reference-pool">
        <h2>Embedded External Reference Pool</h2>
        <ul>
          <li>
            <a href="https://github.com/auggie/oh-my-codex">oh-my-codex repository</a> · link-only
          </li>
          <li>
            <span>OMC_DEBATE_LOOP.md</span> · D2-01 reference outlet
          </li>
        </ul>
      </section>

      <section data-testid="candidate-list">
        <h2>Current candidate lessons</h2>
        <ul>
          {candidates.data.candidates.map((candidate) => (
            <CandidateItem key={candidate.candidate_id} candidate={candidate} />
          ))}
        </ul>
      </section>

      <section data-testid="adopted-history">
        <h2>Adopted history</h2>
        <ul>
          {adopted.data.adopted_candidates.map((candidate) => (
            <li key={candidate.candidate_id} data-testid={`adopted-item-${candidate.candidate_id}`}>
              {candidate.candidate_id} · {candidate.adopted_at} · {candidate.run_record_ref}
            </li>
          ))}
        </ul>
      </section>

      <section data-testid="capability-mini-list">
        <h2>First-4 capabilities</h2>
        <ul>
          {capabilities.data.capabilities.map((capability) => (
            <li key={capability.capability_id} data-testid={`mini-capability-${capability.capability_id}`}>
              {capability.display_name} · {capability.end_type} · {capability.health_mode}
            </li>
          ))}
        </ul>
      </section>

      <section data-testid="omc-run-records">
        <h2>Run records</h2>
        <ol>
          {runs.data.runs.map((run) => (
            <li key={`${run.run_id}-${run.event_type}`} data-testid={`omc-run-${run.run_id}-${run.event_type}`}>
              {run.run_id} · {run.event_type}
            </li>
          ))}
        </ol>
      </section>
    </section>
  )
}

export const omcIngestRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/projects/omc-ingest',
  component: OmcIngestPage,
})

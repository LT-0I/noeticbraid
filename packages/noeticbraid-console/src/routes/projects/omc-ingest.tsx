import { createRoute } from '@tanstack/react-router'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import {
  useAdoptCandidate,
  useCapabilities,
  useLedgerRuns,
  useOmcAdoptedHistory,
  useOmcCandidates,
  useSubmitOmcTask,
} from '@/api/client'
import {
  Badge,
  Button,
  Card,
  CardBody,
  CardDescription,
  CardHeader,
  CardTitle,
  PageHeader,
  R6GateBadge,
  Table,
} from '@/components/ui'
import type { CandidateLesson } from '@/types/contracts'

import { rootRoute } from '../__root'

function CandidateItem({
  candidate,
  adoptSuccessById,
  markAdoptSuccess,
}: {
  candidate: CandidateLesson
  adoptSuccessById: Record<string, boolean>
  markAdoptSuccess: (candidateId: string) => void
}) {
  const { t } = useTranslation()
  const adopt = useAdoptCandidate()
  const alreadyAdopted = candidate.status === 'adopted' || candidate.status === 'confirmed'
  const adoptSucceeded = adoptSuccessById[candidate.candidate_id] === true
  const reuseCount = candidate.r6_gate?.reuse_count ?? 0

  return (
    <li data-testid={`candidate-item-${candidate.candidate_id}`} className="item-card">
      <div className="item-card__topline">
        <h2 className="item-card__title mono">{candidate.candidate_id}</h2>
        <Badge tone={alreadyAdopted ? 'success' : 'warning'}>{t(`status.${candidate.status}`)}</Badge>
        <R6GateBadge candidate={candidate} />
        <Badge data-testid={`r6-reuse-count-${candidate.candidate_id}`} tone="neutral">
          {t('routes.omcIngest.reuseCount', { count: reuseCount })}
        </Badge>
      </div>

      <p>{candidate.summary}</p>
      <dl className="metadata-grid">
        <div className="metadata-item">
          <dt>{t('routes.omcIngest.runRecordLabel')}</dt>
          <dd>{candidate.run_record_ref ?? t('routes.omcIngest.pending')}</dd>
        </div>
        <div className="metadata-item">
          <dt>{t('routes.omcIngest.sourceIds')}</dt>
          <dd>{candidate.source_sdd_ids.join(', ')}</dd>
        </div>
        <div className="metadata-item">
          <dt>{t('routes.omcIngest.upgradeRule')}</dt>
          <dd>{candidate.upgrade_rule}</dd>
        </div>
      </dl>

      <Button
        type="button"
        data-testid={`adopt-${candidate.candidate_id}`}
        disabled={alreadyAdopted || adopt.isPending}
        onClick={() =>
          adopt.mutate(candidate.candidate_id, {
            onSuccess: (_data, candidateId) => markAdoptSuccess(candidateId),
          })
        }
      >
        {alreadyAdopted ? t('routes.omcIngest.adopted') : t('routes.omcIngest.adopt')}
      </Button>
      {adoptSucceeded ? (
        <span data-testid={`adopted-${candidate.candidate_id}`} className="text-muted">
          {' '}{t('routes.omcIngest.adoptSucceeded')}
        </span>
      ) : null}
    </li>
  )
}

function OmcIngestPage() {
  const { t, i18n } = useTranslation()
  const defaultPrompt = t('routes.omcIngest.defaultPrompt')
  const previousDefaultPrompt = useRef(defaultPrompt)
  const [prompt, setPrompt] = useState(defaultPrompt)
  const [promptEdited, setPromptEdited] = useState(false)
  const [adoptSuccessById, setAdoptSuccessById] = useState<Record<string, boolean>>({})
  const candidates = useOmcCandidates()
  const adopted = useOmcAdoptedHistory()
  const capabilities = useCapabilities()
  const runs = useLedgerRuns()
  const submit = useSubmitOmcTask()

  useEffect(() => {
    if (!promptEdited || prompt === previousDefaultPrompt.current) {
      setPrompt(defaultPrompt)
      previousDefaultPrompt.current = defaultPrompt
    }
  }, [defaultPrompt, prompt, promptEdited])

  if (candidates.isLoading || adopted.isLoading || capabilities.isLoading || runs.isLoading) {
    return <div data-testid="omc-loading" className="state-panel">{t('state.loading')}</div>
  }
  if (candidates.isError || adopted.isError || capabilities.isError || runs.isError) {
    return <div data-testid="omc-error" className="state-panel state-panel--error">{t('errors.omc')}</div>
  }
  if (!candidates.data || !adopted.data || !capabilities.data || !runs.data) {
    return <div data-testid="omc-loading" className="state-panel">{t('state.loading')}</div>
  }

  return (
    <section data-testid="omc-project-root" className="stack">
      <PageHeader title={t('routes.omcIngest.title')} subtitle={t('routes.omcIngest.subtitle')} />
      <p data-testid="project-chat-entry" className="text-muted">
        {t('routes.omcIngest.projectChatEntry')}
      </p>

      <Card data-testid="omc-task-card">
        <CardHeader>
          <div>
            <CardTitle>{t('routes.omcIngest.taskCardTitle')}</CardTitle>
            <CardDescription>{t('routes.omcIngest.defaultPrompt')}</CardDescription>
          </div>
        </CardHeader>
        <CardBody>
          <label className="form-field" htmlFor="omc-task-prompt">
            <span className="form-label">{t('routes.omcIngest.taskPromptLabel')}</span>
            <textarea
              className="textarea"
              id="omc-task-prompt"
              value={prompt}
              onChange={(event) => {
                setPromptEdited(true)
                setPrompt(event.target.value)
              }}
              rows={3}
              lang={i18n.resolvedLanguage}
            />
          </label>
          <Button
            type="button"
            variant="primary"
            data-testid="submit-omc-task"
            disabled={submit.isPending}
            onClick={() =>
              submit.mutate({
                task_id: 'task_omc_ingest',
                title: t('routes.omcIngest.submitTitle'),
                prompt,
                source_refs: [
                  'source_project_definition_v3_2',
                  'source_ai_invocation_reference',
                  'source_omc_metadata',
                ],
              })
            }
          >
            {t('routes.omcIngest.runTask')}
          </Button>
          {submit.data ? (
            <p data-testid="submitted-candidate" className="text-muted">
              {t('routes.omcIngest.submittedCandidate', { candidateId: submit.data.candidate_id })}
            </p>
          ) : null}
        </CardBody>
      </Card>

      <Card data-testid="external-reference-pool">
        <CardHeader>
          <CardTitle>{t('routes.omcIngest.referencesTitle')}</CardTitle>
        </CardHeader>
        <CardBody>
          <ul className="clean-list reference-list">
            <li>
              <a className="reference-link" href="https://github.com/auggie/oh-my-codex">
                {t('routes.omcIngest.repoName')}
              </a>{' '}
              · {t('routes.omcIngest.linkOnly')}
            </li>
            <li>
              <span className="mono">OMC_DEBATE_LOOP.md</span> · {t('routes.omcIngest.referenceOutlet')}
            </li>
          </ul>
        </CardBody>
      </Card>

      <Card data-testid="candidate-list">
        <CardHeader>
          <CardTitle>{t('routes.omcIngest.candidatesTitle')}</CardTitle>
        </CardHeader>
        <CardBody>
          <ul className="item-list">
            {candidates.data.candidates.map((candidate) => (
              <CandidateItem
                key={candidate.candidate_id}
                candidate={candidate}
                adoptSuccessById={adoptSuccessById}
                markAdoptSuccess={(candidateId) =>
                  setAdoptSuccessById((current) => ({ ...current, [candidateId]: true }))
                }
              />
            ))}
          </ul>
        </CardBody>
      </Card>

      <div className="grid-two">
        <Card data-testid="adopted-history">
          <CardHeader>
            <CardTitle>{t('routes.omcIngest.adoptedHistoryTitle')}</CardTitle>
          </CardHeader>
          <CardBody>
            <ul className="item-list">
              {adopted.data.adopted_candidates.map((candidate) => (
                <li key={candidate.candidate_id} data-testid={`adopted-item-${candidate.candidate_id}`} className="item-card">
                  <strong className="mono">{candidate.candidate_id}</strong>
                  <p className="mono">{candidate.adopted_at} · {candidate.run_record_ref}</p>
                </li>
              ))}
            </ul>
          </CardBody>
        </Card>

        <Card data-testid="capability-mini-list">
          <CardHeader>
            <CardTitle>{t('routes.omcIngest.capabilitiesTitle')}</CardTitle>
          </CardHeader>
          <CardBody>
            <ul className="item-list">
              {capabilities.data.capabilities.map((capability) => (
                <li key={capability.capability_id} data-testid={`mini-capability-${capability.capability_id}`} className="item-card">
                  <strong>{capability.display_name}</strong>
                  <p>{t(`end.${capability.end_type}`)} · {t(`healthMode.${capability.health_mode}`)}</p>
                </li>
              ))}
            </ul>
          </CardBody>
        </Card>
      </div>

      <Card data-testid="omc-run-records">
        <CardHeader>
          <CardTitle>{t('routes.omcIngest.runRecordsTitle')}</CardTitle>
        </CardHeader>
        <CardBody>
          <div className="ui-table-wrap">
            <Table>
              <thead>
                <tr>
                  <th>{t('routes.runs.event')}</th>
                  <th>{t('routes.runs.status')}</th>
                </tr>
              </thead>
              <tbody>
                {runs.data.runs.map((run) => (
                  <tr key={`${run.run_id}-${run.event_type}`} data-testid={`omc-run-${run.run_id}-${run.event_type}`}>
                    <td className="mono">{run.run_id}</td>
                    <td>{t(`event.${run.event_type}`)}</td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </div>
        </CardBody>
      </Card>
    </section>
  )
}

export const omcIngestRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/projects/omc-ingest',
  component: OmcIngestPage,
})

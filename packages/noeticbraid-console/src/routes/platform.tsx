import { Link, createRoute, useNavigate } from '@tanstack/react-router'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { useTranslation } from 'react-i18next'

import { useAuthState } from '@/api/auth-context'
import {
  createPlatformTaskSocket,
  downloadBlob,
  fetchPlatformArtifactBlob,
  platformAuthFrame,
  transcribePlatformAudio,
  useCreatePlatformTask,
  usePlatformDeliverable,
  usePlatformTask,
  usePlatformTasks,
} from '@/api/platform-client'
import { Badge, Button, Card, CardBody, CardDescription, CardFooter, CardHeader, CardTitle, EmptyState, PageHeader } from '@/components/ui'
import type {
  DeliverableModality,
  PlatformArtifact,
  PlatformBlockedFrame,
  PlatformDeliverableStatus,
  PlatformLedgerEvent,
  PlatformModality,
  PlatformProgressFrame,
  PlatformServerFrame,
  PlatformTask,
  PlatformTaskState,
  TimelineEntry,
} from '@/types/platform'

import { rootRoute } from './__root'

const modalityOptions: readonly PlatformModality[] = ['document', 'slides', 'image', 'poster', 'video', 'music']
const inProgressStates = new Set<PlatformTaskState>(['planning', 'dispatching', 'producing', 'cross_validating'])

type ChatMessage = {
  id: string
  role: 'user' | 'ai' | 'system'
  content: string
}

type ProgressItem = {
  id: string
  label: string
  state: 'normal' | 'active' | 'blocked' | 'error' | 'complete'
  meta?: string
}

type SocketStatus = 'connecting' | 'open' | 'reconnecting' | 'closed' | 'auth-missing'

function formatTimestamp(value: string): string {
  const ms = Date.parse(value)
  if (Number.isNaN(ms)) return value
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(ms))
}

function stateTone(state: PlatformTaskState) {
  if (state === 'delivered') return 'success' as const
  if (state === 'blocked') return 'warning' as const
  if (state === 'error') return 'error' as const
  if (inProgressStates.has(state)) return 'info' as const
  return 'neutral' as const
}

function stateLabel(state: string): string {
  return state.replace('_', ' ')
}

function shortSha(sha256: string): string {
  return sha256.slice(0, 8)
}

function filenameFor(artifact: PlatformArtifact): string {
  if (artifact.filename) return artifact.filename
  const parts = artifact.rel_path.split('/').filter(Boolean)
  return parts.at(-1) ?? artifact.rel_path
}

function sizeLabel(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function aiDeltaText(payload: Record<string, unknown>): string {
  for (const key of ['delta', 'text', 'content', 'message', 'summary']) {
    const value = payload[key]
    if (typeof value === 'string' && value.trim()) return value
  }
  return JSON.stringify(payload, null, 2)
}

function ledgerLabel(event: PlatformLedgerEvent): string {
  const named = event.event_type ?? event.type ?? event.state ?? event.message
  return typeof named === 'string' && named ? named : 'ledger event'
}

function ledgerMeta(event: PlatformLedgerEvent): string | undefined {
  const stamp = event.created_at ?? event.ts
  return typeof stamp === 'string' ? stamp : undefined
}

export function ModalityGlyph({ modality }: { modality: string }) {
  const label = modality.slice(0, 2).toUpperCase()
  return <span className="platform-glyph" aria-hidden="true">{label}</span>
}

function TaskStateBadge({ state }: { state: PlatformTaskState }) {
  return <Badge tone={stateTone(state)} dot>{state}</Badge>
}

function AuthUnavailable({ mode }: { mode: string }) {
  const { t } = useTranslation()
  return (
    <section data-testid="platform-auth-unavailable" className="stack">
      <PageHeader title={t('routes.platform.title')} subtitle={t('routes.platform.subtitle')} />
      <div className="state-panel state-panel--error">
        <EmptyState title={t('auth.unavailable.title')} message={t('auth.unavailable.message', { mode })} />
      </div>
    </section>
  )
}

const deliverableModalities: readonly PlatformModality[] = ['document', 'slides', 'poster', 'image', 'video', 'music']

function deliverableStatusTone(status: PlatformDeliverableStatus | 'notProduced') {
  if (status === 'delivered') return 'success' as const
  if (status === 'converted') return 'info' as const
  if (status === 'blocked') return 'warning' as const
  return 'neutral' as const
}

function deliverableStatusLabelKey(status: PlatformDeliverableStatus | 'notProduced') {
  return status === 'notProduced' ? 'platform.status.notProduced' : `platform.status.${status}`
}

function previewKind(item: DeliverableModality): 'image' | 'video' | 'markdown' | 'pptx' | 'none' {
  if (!item.download_url) return 'none'
  if (item.modality === 'document' || item.content_type.startsWith('text/markdown')) return 'markdown'
  if (item.modality === 'image' || item.modality === 'poster' || item.content_type.startsWith('image/')) return 'image'
  if (item.modality === 'video' || item.content_type.startsWith('video/')) return 'video'
  if (item.modality === 'slides') return 'pptx'
  return 'none'
}

function safeFilename(item: Partial<DeliverableModality>, modality: PlatformModality, t: (key: string) => string): string {
  return typeof item.filename === 'string' && item.filename ? item.filename : `${t(`modality.${modality}`)}`
}

function normalizeModality(
  incoming: DeliverableModality | undefined,
  modality: PlatformModality,
  t: (key: string) => string,
): DeliverableModality | null {
  if (!incoming) return null
  if (!incoming.title || !incoming.filename || !incoming.status) {
    return {
      modality,
      status: 'blocked',
      title: t(`modality.${modality}`),
      filename: safeFilename(incoming, modality, t),
      content_type: incoming.content_type ?? 'application/octet-stream',
      bytes: null,
      sha256: null,
      download_url: null,
      blocked_reason: t('errors.platformDeliverable'),
      provenance: {
        source_task_id: null,
        ledgered: false,
        kind: 'not_attempted',
        note: t('errors.platformDeliverable'),
      },
    }
  }
  return incoming
}

function DeliverableSkeleton() {
  const { t } = useTranslation()
  return (
    <section data-testid="platform-deliverable-loading" className="stack platform-page">
      <div className="state-panel">{t('state.loading')}</div>
      <div className="deliverable-gallery">
        {deliverableModalities.map((modality) => (
          <Card key={modality} className="deliverable-tile--skeleton" aria-hidden="true">
            <CardHeader>
              <div className="platform-artifact-heading">
                <ModalityGlyph modality={modality} />
                <div className="deliverable-skeleton-line" />
              </div>
            </CardHeader>
            <CardBody><div className="deliverable-skeleton-block" /></CardBody>
          </Card>
        ))}
      </div>
    </section>
  )
}

function DeliverableSummary({ items }: { items: Array<DeliverableModality | null> }) {
  const { t } = useTranslation()
  return (
    <nav className="deliverable-summary" aria-label={t('routes.platformDeliverable.summaryBadge', { done: 0, total: 6 })}>
      {items.map((item, index) => {
        const modality = deliverableModalities[index]!
        const status = item?.status ?? 'notProduced'
        return (
          <a key={modality} href={`#tile-${modality}`} className="deliverable-summary-pill">
            <ModalityGlyph modality={modality} />
            <span>{t(`modality.${modality}`)}</span>
            <Badge tone={deliverableStatusTone(status)} dot={status === 'delivered' || status === 'converted'}>
              {t(deliverableStatusLabelKey(status))}
            </Badge>
          </a>
        )
      })}
    </nav>
  )
}

function useObjectUrl(item: DeliverableModality): { url: string | null; failed: boolean } {
  const [url, setUrl] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    if (!item.download_url) return undefined
    let objectUrl: string | null = null
    let active = true
    void fetchPlatformArtifactBlob({
      modality: item.modality,
      rel_path: '',
      sha256: item.sha256 ?? '',
      bytes: item.bytes ?? 0,
      content_type: item.content_type,
      filename: item.filename,
      download_url: item.download_url,
    })
      .then((blob) => {
        if (!active) return
        if (typeof URL.createObjectURL === 'function') {
          objectUrl = URL.createObjectURL(blob)
          setUrl(objectUrl)
          return
        }
        setUrl(item.download_url)
      })
      .catch(() => {
        if (active) setFailed(true)
      })
    return () => {
      active = false
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [item])

  return { url, failed }
}

function MarkdownPreview({ item }: { item: DeliverableModality }) {
  const { t } = useTranslation()
  const [text, setText] = useState<string | null>(null)
  const [expanded, setExpanded] = useState(false)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    if (!item.download_url) return undefined
    let active = true
    void fetchPlatformArtifactBlob({
      modality: item.modality,
      rel_path: '',
      sha256: item.sha256 ?? '',
      bytes: item.bytes ?? 0,
      content_type: item.content_type,
      filename: item.filename,
      download_url: item.download_url,
    })
      .then((blob) => blob.text())
      .then((value) => {
        if (active) setText(value)
      })
      .catch(() => {
        if (active) setFailed(true)
      })
    return () => {
      active = false
    }
  }, [item])

  if (failed) return <div className="platform-preview-fallback">{t('routes.platform.previewUnavailable')}</div>
  if (text === null) return <div className="platform-preview-fallback">{t('state.loading')}</div>

  return (
    <div className={`deliverable-md${expanded ? ' deliverable-md--expanded' : ''}`}>
      <div tabIndex={0} role="region" aria-label={t('routes.platformDeliverable.markdownPreview', { title: item.title })}>
        {renderMarkdown(text)}
      </div>
      <button type="button" className="deliverable-expand" onClick={() => setExpanded((current) => !current)}>
        {expanded ? t('routes.platformDeliverable.collapseText') : t('routes.platformDeliverable.expandText')}
      </button>
    </div>
  )
}

function renderMarkdown(markdown: string) {
  return markdown.split(/\n+/).filter(Boolean).slice(0, 80).map((line, index) => {
    const trimmed = line.trim()
    if (trimmed.startsWith('# ')) return <h3 key={index}>{trimmed.slice(2)}</h3>
    if (trimmed.startsWith('## ')) return <h4 key={index}>{trimmed.slice(3)}</h4>
    if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) return <p key={index}>• {trimmed.slice(2)}</p>
    return <p key={index}>{trimmed.replace(/`/g, '')}</p>
  })
}

function DeliverablePreview({ item }: { item: DeliverableModality }) {
  const { t } = useTranslation()
  const kind = previewKind(item)
  const object = useObjectUrl(item)

  if (kind === 'markdown') return <MarkdownPreview item={item} />
  if (kind === 'image') {
    if (object.failed) return <div className="platform-preview-fallback">{t('routes.platform.previewUnavailable')}</div>
    if (!object.url) return <div className="platform-preview-fallback">{t('state.loading')}</div>
    return (
      <a href={object.url} target="_blank" rel="noreferrer" aria-label={t('routes.platformDeliverable.openFull')}>
        <img className="platform-artifact-image" src={object.url} alt={item.title} loading="lazy" />
      </a>
    )
  }
  if (kind === 'video') {
    if (object.failed) return <div className="platform-preview-fallback">{t('routes.platform.previewUnavailable')}</div>
    if (!object.url) return <div className="platform-preview-fallback">{t('state.loading')}</div>
    return (
      <video
        className="platform-artifact-media"
        src={object.url}
        controls
        preload="metadata"
        aria-label={t('platform.video.player', { title: item.title })}
      />
    )
  }
  return (
    <div className="platform-doc-preview">
      <ModalityGlyph modality={item.modality} />
      <span>{kind === 'pptx' ? t('routes.platformDeliverable.previewGenerating') : item.filename}</span>
    </div>
  )
}

function Provenance({ item }: { item: DeliverableModality }) {
  const { t } = useTranslation()
  return (
    <details className="deliverable-provenance">
      <summary>{t('routes.platformDeliverable.provenance')}</summary>
      <dl>
        {item.sha256 ? (
          <>
            <dt>sha256</dt>
            <dd>{item.sha256}</dd>
          </>
        ) : null}
        {item.provenance.source_artifact_sha256 ? (
          <>
            <dt>source sha256</dt>
            <dd>{item.provenance.source_artifact_sha256}</dd>
          </>
        ) : null}
        <dt>{item.provenance.kind}</dt>
        <dd>{item.provenance.note}</dd>
      </dl>
    </details>
  )
}

function ModalityTile({ item, modality }: { item: DeliverableModality | null; modality: PlatformModality }) {
  const { t } = useTranslation()
  if (!item) {
    return (
      <Card id={`tile-${modality}`} className="deliverable-tile deliverable-tile--absent" aria-labelledby={`tile-${modality}-title`}>
        <CardHeader>
          <div className="platform-artifact-heading">
            <ModalityGlyph modality={modality} />
            <CardTitle id={`tile-${modality}-title`}>{t(`modality.${modality}`)}</CardTitle>
          </div>
          <Badge tone="neutral">{t('platform.status.notProduced')}</Badge>
        </CardHeader>
        <CardBody>
          <div className="platform-preview-fallback">{t('routes.platformDeliverable.notProducedBody')}</div>
        </CardBody>
      </Card>
    )
  }

  const statusDot = item.status === 'delivered' || item.status === 'converted'
  const inspectableBlocked = item.status === 'blocked' && Boolean(item.download_url)
  return (
    <Card
      id={`tile-${modality}`}
      className={`deliverable-tile${item.status === 'blocked' ? ' platform-blocked-card' : ''}`}
      aria-labelledby={`tile-${modality}-title`}
      data-testid={`deliverable-tile-${modality}`}
    >
      <CardHeader>
        <div className="platform-artifact-heading">
          <ModalityGlyph modality={modality} />
          <div>
            <CardTitle id={`tile-${modality}-title`}>{t(`modality.${modality}`)}</CardTitle>
            <CardDescription>{item.title}</CardDescription>
          </div>
        </div>
        <Badge tone={deliverableStatusTone(item.status)} dot={statusDot}>{t(deliverableStatusLabelKey(item.status))}</Badge>
      </CardHeader>
      <CardBody>
        {item.status === 'blocked' && !inspectableBlocked ? (
          <div className="deliverable-blocked-body">
            <strong>⚠</strong>
            <p>{item.blocked_reason ?? t('routes.platformDeliverable.notProducedBody')}</p>
            <span>{t('routes.platformDeliverable.notProducedBody')}</span>
          </div>
        ) : (
          <>
            <DeliverablePreview item={item} />
            {item.status === 'converted' ? <p className="deliverable-caption">{t('routes.platformDeliverable.convertedNote')}</p> : null}
            {inspectableBlocked ? (
              <p className="deliverable-caption">{item.blocked_reason}</p>
            ) : null}
          </>
        )}
      </CardBody>
      <CardFooter className="deliverable-footer">
        <span className="deliverable-filename" title={item.filename}>{item.filename}</span>
        <span>{item.bytes === null ? '—' : sizeLabel(item.bytes)}</span>
        {item.download_url && item.status !== 'blocked' ? (
          <Button type="button" size="sm" onClick={() => void downloadBlob(item.download_url!, item.filename)}>
            {t('routes.platform.download')}
          </Button>
        ) : null}
        <Provenance item={item} />
      </CardFooter>
    </Card>
  )
}

function HumanTimeline({ entries }: { entries: TimelineEntry[] }) {
  const { t } = useTranslation()
  return (
    <div>
      <h3 className="item-card__title">{t('routes.platformDeliverable.timelineTitle')}</h3>
      <ol className="platform-timeline">
        {entries.map((entry, index) => (
          <li key={`${entry.label}-${index}`} className={`platform-timeline-item platform-timeline-item--${entry.tone === 'done' ? 'complete' : entry.tone}`}>
            <span className="platform-timeline-dot" aria-hidden="true" />
            <div>
              <strong>{entry.label}</strong>
              {entry.ts ? <span>{formatTimestamp(entry.ts)}</span> : null}
            </div>
          </li>
        ))}
      </ol>
    </div>
  )
}

function timelineFor(items: Array<DeliverableModality | null>, t: (key: string, options?: Record<string, unknown>) => string): TimelineEntry[] {
  return items.map((item, index) => {
    const modality = deliverableModalities[index]!
    if (!item) {
      return { label: `${t(`modality.${modality}`)} · ${t('platform.status.notProduced')}`, tone: 'neutral' }
    }
    const tone: TimelineEntry['tone'] = item.status === 'blocked' ? 'blocked' : 'done'
    return { label: `${item.title} · ${t(deliverableStatusLabelKey(item.status))}`, tone }
  })
}

function PlatformDeliverablePage() {
  const { t } = useTranslation()
  const auth = useAuthState()
  const deliverable = usePlatformDeliverable(auth.status === 'ready')

  if (auth.status === 'booting') return <DeliverableSkeleton />
  if (auth.status === 'degraded') return <AuthUnavailable mode={auth.mode} />
  if (deliverable.isLoading) return <DeliverableSkeleton />
  if (deliverable.isError || !deliverable.data?.deliverable) {
    return <div data-testid="platform-deliverable-error" className="state-panel state-panel--error">{t('errors.platformDeliverable')}</div>
  }

  const payload = deliverable.data.deliverable
  if ((payload.modalities ?? []).length === 0) {
    return (
      <section data-testid="platform-root" className="stack platform-page">
        <PageHeader title={payload.title || t('routes.platform.title')} subtitle={t('routes.platform.subtitle')} />
        <EmptyState title={t('empty.platformDeliverable.title')} message={t('empty.platformDeliverable.message')} />
      </section>
    )
  }

  const byModality = new Map(payload.modalities.map((item) => [item.modality, item]))
  const items = deliverableModalities.map((modality) => normalizeModality(byModality.get(modality), modality, t))
  const done = items.filter((item) => item?.status === 'delivered' || item?.status === 'converted').length
  const total = deliverableModalities.length
  const assignedTs = payload.assigned_ts ?? payload.generated_at ?? '—'
  const timeline = payload.timeline?.length ? payload.timeline : timelineFor(items, t)

  return (
    <section data-testid="platform-root" className="stack platform-page">
      <PageHeader
        eyebrow={t('routes.platformDeliverable.eyebrow')}
        title={payload.title || t('routes.platform.title')}
        subtitle={t('routes.platformDeliverable.subtitle', { ts: assignedTs === '—' ? assignedTs : formatTimestamp(assignedTs), done, total })}
        actions={<Badge tone={done === total ? 'success' : 'info'} dot>{t('routes.platformDeliverable.summaryBadge', { done, total })}</Badge>}
      />

      <DeliverableSummary items={items} />

      <div className="deliverable-gallery" data-testid="deliverable-gallery">
        {items.map((item, index) => (
          <ModalityTile key={deliverableModalities[index]!} item={item} modality={deliverableModalities[index]!} />
        ))}
      </div>

      <details className="deliverable-diagnostics">
        <summary>{t('routes.platformDeliverable.diagnostics')}</summary>
        <HumanTimeline entries={timeline} />
        <Link to="/platform/history" className="platform-backlink">{t('routes.platformDeliverable.viewDebugList')}</Link>
      </details>
    </section>
  )
}

function NewTaskModal({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const createTask = useCreatePlatformTask()
  const [title, setTitle] = useState('')
  const [modalities, setModalities] = useState<PlatformModality[]>(['document'])

  function toggleModality(value: PlatformModality) {
    setModalities((current) =>
      current.includes(value) ? current.filter((item) => item !== value) : [...current, value],
    )
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const trimmed = title.trim()
    if (!trimmed || modalities.length === 0 || createTask.isPending) return
    createTask.mutate(
      { title: trimmed, modality_targets: modalities },
      {
        onSuccess: (task) => {
          onClose()
          void navigate({ to: '/platform/$taskId', params: { taskId: task.task_id } })
        },
      },
    )
  }

  return (
    <div className="platform-modal-backdrop" role="presentation">
      <div className="platform-modal" role="dialog" aria-modal="true" aria-labelledby="new-platform-task-title">
        <form className="stack" onSubmit={submit}>
          <div className="item-card__topline">
            <h2 id="new-platform-task-title" className="item-card__title">{t('routes.platform.newTask')}</h2>
            <Button type="button" variant="ghost" onClick={onClose}>{t('common.cancel')}</Button>
          </div>
          <label className="form-field" htmlFor="platform-task-title">
            <span className="form-label">{t('routes.platform.taskTitleLabel')}</span>
            <input
              id="platform-task-title"
              className="platform-input"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              autoFocus
              required
            />
          </label>
          <fieldset className="platform-fieldset">
            <legend className="form-label">{t('routes.platform.modalitiesLabel')}</legend>
            <div className="platform-modalities">
              {modalityOptions.map((modality) => (
                <label key={modality} className="platform-check-chip">
                  <input
                    type="checkbox"
                    checked={modalities.includes(modality)}
                    onChange={() => toggleModality(modality)}
                  />
                  <ModalityGlyph modality={modality} />
                  <span>{t(`modality.${modality}`)}</span>
                </label>
              ))}
            </div>
          </fieldset>
          {createTask.isError ? <p className="platform-inline-error">{t('errors.platformCreate')}</p> : null}
          <div className="platform-modal-actions">
            <Button type="button" variant="secondary" onClick={onClose}>{t('common.cancel')}</Button>
            <Button type="submit" variant="primary" disabled={!title.trim() || modalities.length === 0 || createTask.isPending}>
              {createTask.isPending ? t('state.loading') : t('routes.platform.createTask')}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}

function PlatformHistoryPage() {
  const { t } = useTranslation()
  const auth = useAuthState()
  const tasks = usePlatformTasks(auth.status === 'ready')
  const [modalOpen, setModalOpen] = useState(false)

  if (auth.status === 'booting') {
    return <div data-testid="platform-loading" className="state-panel">{t('state.loading')}</div>
  }
  if (auth.status === 'degraded') return <AuthUnavailable mode={auth.mode} />
  if (tasks.isLoading) {
    return <div data-testid="platform-loading" className="state-panel">{t('state.loading')}</div>
  }
  if (tasks.isError) {
    return <div data-testid="platform-error" className="state-panel state-panel--error">{t('errors.platform')}</div>
  }

  const taskList = tasks.data?.tasks ?? []

  return (
    <section data-testid="platform-history-root" className="stack platform-page">
      <PageHeader
        eyebrow={<Link to="/platform" className="platform-backlink">{t('routes.platformDeliverable.eyebrow')}</Link>}
        title={t('routes.platform.historyTitle')}
        subtitle={t('routes.platform.historySubtitle')}
        actions={<Button type="button" variant="primary" onClick={() => setModalOpen(true)}>{t('routes.platform.newTask')}</Button>}
      />

      {taskList.length === 0 ? (
        <EmptyState title={t('empty.platform.title')} message={t('empty.platform.message')} />
      ) : (
        <div className="platform-task-grid" data-testid="platform-task-list">
          {taskList.map((task) => (
            <Link key={task.task_id} to="/platform/$taskId" params={{ taskId: task.task_id }} className="platform-task-card">
              <Card interactive>
                <CardHeader>
                  <div>
                    <CardTitle>{task.title}</CardTitle>
                    <CardDescription>
                      {t('routes.platform.updated')} <time>{formatTimestamp(task.updated_ts)}</time>
                    </CardDescription>
                  </div>
                  <TaskStateBadge state={task.state} />
                </CardHeader>
                <CardBody>
                  <div className="platform-chip-row" aria-label={t('routes.platform.modalitiesLabel')}>
                    {task.modality_targets.map((modality) => (
                      <span key={modality} className="platform-chip"><ModalityGlyph modality={modality} />{t(`modality.${modality}`)}</span>
                    ))}
                  </div>
                </CardBody>
              </Card>
            </Link>
          ))}
        </div>
      )}

      {modalOpen ? <NewTaskModal onClose={() => setModalOpen(false)} /> : null}
    </section>
  )
}

function useTaskSocket(
  taskId: string,
  enabled: boolean,
  onFrame: (frame: PlatformServerFrame) => void,
): { status: SocketStatus; sendMessage: (text: string) => void } {
  const [status, setStatus] = useState<SocketStatus>('connecting')
  const socketRef = useRef<WebSocket | null>(null)
  const queueRef = useRef<string[]>([])
  const reconnectRef = useRef<number | null>(null)
  const backoffRef = useRef(500)
  const onFrameRef = useRef(onFrame)

  useEffect(() => {
    onFrameRef.current = onFrame
  }, [onFrame])

  const connect = useCallback(() => {
    if (!enabled) {
      setStatus('connecting')
      return
    }
    const authFrame = platformAuthFrame()
    if (!authFrame) {
      setStatus('auth-missing')
      return
    }
    setStatus((current) => (current === 'closed' ? 'connecting' : current === 'open' ? 'open' : 'reconnecting'))
    const socket = createPlatformTaskSocket(taskId)
    socketRef.current = socket
    socket.onopen = () => {
      backoffRef.current = 500
      setStatus('open')
      socket.send(JSON.stringify(authFrame))
      const queued = queueRef.current.splice(0)
      queued.forEach((text) => socket.send(JSON.stringify({ type: 'user_message', task_id: taskId, text })))
    }
    socket.onmessage = (event) => {
      try {
        onFrameRef.current(JSON.parse(String(event.data)) as PlatformServerFrame)
      } catch {
        onFrameRef.current({ type: 'error', task_id: taskId, code: 'invalid_frame', reason: 'Received an unreadable platform event.' })
      }
    }
    socket.onclose = () => {
      if (socketRef.current !== socket) return
      setStatus('reconnecting')
      const delay = backoffRef.current
      backoffRef.current = Math.min(backoffRef.current * 1.8, 8000)
      reconnectRef.current = window.setTimeout(connect, delay)
    }
    socket.onerror = () => {
      socket.close()
    }
  }, [enabled, taskId])

  useEffect(() => {
    if (!enabled) return undefined
    connect()
    return () => {
      if (reconnectRef.current !== null) window.clearTimeout(reconnectRef.current)
      reconnectRef.current = null
      const socket = socketRef.current
      socketRef.current = null
      setStatus('closed')
      socket?.close()
    }
  }, [connect, enabled])

  const sendMessage = useCallback((text: string) => {
    const socket = socketRef.current
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: 'user_message', task_id: taskId, text }))
      return
    }
    queueRef.current.push(text)
  }, [taskId])

  return { status, sendMessage }
}

function Composer({ onSend, disabled }: { onSend: (text: string) => void; disabled?: boolean }) {
  const { t } = useTranslation()
  const [text, setText] = useState('')
  const [recording, setRecording] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<BlobPart[]>([])

  function send() {
    const trimmed = text.trim()
    if (!trimmed) return
    onSend(trimmed)
    setText('')
  }

  async function toggleRecording() {
    if (recording) {
      recorderRef.current?.stop()
      return
    }
    if (typeof MediaRecorder === 'undefined' || !navigator.mediaDevices?.getUserMedia) {
      setNotice(t('routes.platform.voiceUnavailable'))
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' })
      chunksRef.current = []
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data)
      }
      recorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop())
        setRecording(false)
        const blob = new Blob(chunksRef.current, { type: 'audio/webm;codecs=opus' })
        void transcribePlatformAudio(blob)
          .then((response) => {
            if ('status' in response && response.status === 'not_provisioned') {
              setNotice(t('routes.platform.voiceNotProvisioned'))
              return
            }
            if ('text' in response && response.text) {
              setText(response.text)
              setNotice(null)
            }
          })
          .catch(() => setNotice(t('routes.platform.voiceUnavailable')))
      }
      recorderRef.current = recorder
      recorder.start()
      setRecording(true)
      setNotice(null)
    } catch {
      setNotice(t('routes.platform.voiceUnavailable'))
    }
  }

  return (
    <div className="platform-composer">
      {notice ? <p className="platform-inline-notice" role="status">{notice}</p> : null}
      <label className="sr-only" htmlFor="platform-composer-input">{t('routes.platform.composerLabel')}</label>
      <textarea
        id="platform-composer-input"
        className="platform-composer-input"
        value={text}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={(event) => {
          if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') send()
        }}
        placeholder={t('routes.platform.composerPlaceholder')}
        rows={3}
      />
      <div className="platform-composer-actions">
        <Button
          type="button"
          variant={recording ? 'primary' : 'secondary'}
          aria-pressed={recording}
          aria-label={recording ? t('routes.platform.stopRecording') : t('routes.platform.startRecording')}
          onClick={() => void toggleRecording()}
        >
          {recording ? t('routes.platform.recording') : t('routes.platform.mic')}
        </Button>
        <Button type="button" variant="primary" disabled={disabled || !text.trim()} onClick={send}>
          {t('routes.platform.send')}
        </Button>
      </div>
    </div>
  )
}

function ArtifactPreview({ artifact }: { artifact: PlatformArtifact }) {
  const { t } = useTranslation()
  const [url, setUrl] = useState<string | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let objectUrl: string | null = null
    let active = true
    void fetchPlatformArtifactBlob(artifact)
      .then((blob) => {
        if (!active) return
        objectUrl = URL.createObjectURL(blob)
        setUrl(objectUrl)
      })
      .catch(() => {
        if (active) setFailed(true)
      })
    return () => {
      active = false
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [artifact])

  if (failed) return <div className="platform-preview-fallback">{t('routes.platform.previewUnavailable')}</div>
  if (!url) return <div className="platform-preview-fallback">{t('state.loading')}</div>

  if (artifact.modality === 'image' || artifact.modality === 'poster') {
    return <img className="platform-artifact-image" src={url} alt={filenameFor(artifact)} loading="lazy" />
  }
  if (artifact.modality === 'video') {
    return <video className="platform-artifact-media" src={url} controls />
  }
  if (artifact.modality === 'music') {
    return <audio className="platform-artifact-audio" src={url} controls />
  }
  return (
    <div className="platform-doc-preview">
      <ModalityGlyph modality={artifact.modality} />
      <span>{t('routes.platform.documentPreview')}</span>
      <Button type="button" size="sm" variant="ghost" onClick={() => window.open(url, '_blank', 'noopener,noreferrer')}>
        {t('routes.platform.openPreview')}
      </Button>
    </div>
  )
}

function ArtifactCard({ artifact }: { artifact: PlatformArtifact }) {
  const { t } = useTranslation()
  const [downloading, setDownloading] = useState(false)

  async function download() {
    setDownloading(true)
    try {
      const blob = await fetchPlatformArtifactBlob(artifact)
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = filenameFor(artifact)
      document.body.append(anchor)
      anchor.click()
      anchor.remove()
      // Defer revoke: revoking synchronously can abort the just-started
      // download in some browsers because the click-initiated fetch of the
      // object URL has not necessarily begun by the next statement.
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000)
    } finally {
      setDownloading(false)
    }
  }

  return (
    <Card className="platform-artifact-card">
      <CardHeader>
        <div className="platform-artifact-heading">
          <ModalityGlyph modality={artifact.modality} />
          <div>
            <CardTitle>{filenameFor(artifact)}</CardTitle>
            <CardDescription>
              {artifact.modality} · {sizeLabel(artifact.bytes)} · sha {shortSha(artifact.sha256)}
            </CardDescription>
          </div>
        </div>
        <Button type="button" size="sm" onClick={() => void download()} disabled={downloading}>
          {downloading ? t('state.loading') : t('routes.platform.download')}
        </Button>
      </CardHeader>
      <CardBody>
        <ArtifactPreview artifact={artifact} />
      </CardBody>
    </Card>
  )
}

function BlockedArtifactCard({ blocked }: { blocked: PlatformBlockedFrame }) {
  const { t } = useTranslation()
  return (
    <Card className="platform-blocked-card">
      <CardHeader>
        <div className="platform-artifact-heading">
          <ModalityGlyph modality={blocked.modality} />
          <div>
            <CardTitle>{t('routes.platform.blockedArtifactTitle', { modality: blocked.modality })}</CardTitle>
            <CardDescription>{t('routes.platform.noReachableEndpoint')}</CardDescription>
          </div>
        </div>
        <Badge tone="warning">blocked</Badge>
      </CardHeader>
      <CardBody>
        <p>{blocked.reason}</p>
      </CardBody>
    </Card>
  )
}

function ProgressRail({ items }: { items: ProgressItem[] }) {
  const { t } = useTranslation()
  return (
    <aside className="platform-rail" aria-label={t('routes.platform.progressRail')}>
      <h2>{t('routes.platform.progressRail')}</h2>
      {items.length === 0 ? (
        <p className="text-muted">{t('routes.platform.progressEmpty')}</p>
      ) : (
        <ol className="platform-timeline">
          {items.map((item, index) => {
            // Only a genuinely in-progress last item is "current"; terminal
            // states (complete/blocked/error) must not keep pulsing.
            const current = index === items.length - 1 && item.state === 'active'
            return (
              <li key={item.id} className={`platform-timeline-item platform-timeline-item--${item.state}${current ? ' platform-timeline-item--current' : ''}`}>
                <span className="platform-timeline-dot" aria-hidden="true" />
                <div>
                  <strong>{item.label}</strong>
                  {item.meta ? <span>{item.meta}</span> : null}
                </div>
              </li>
            )
          })}
        </ol>
      )}
    </aside>
  )
}

function PlatformDetailPage() {
  const { t } = useTranslation()
  const auth = useAuthState()
  const { taskId } = platformDetailRoute.useParams()
  const detail = usePlatformTask(taskId, auth.status === 'ready')
  const [chat, setChat] = useState<ChatMessage[]>([])
  const [progress, setProgress] = useState<ProgressItem[]>([])
  const [artifacts, setArtifacts] = useState<PlatformArtifact[]>([])
  const [blocked, setBlocked] = useState<PlatformBlockedFrame[]>([])

  useEffect(() => {
    if (!detail.data) return
    setArtifacts(detail.data.artifacts ?? [])
    setProgress((detail.data.ledger ?? []).map((event, index) => ({
      id: `ledger-${index}`,
      label: ledgerLabel(event),
      meta: ledgerMeta(event),
      state: event.state === 'error' ? 'error' : event.state === 'blocked' ? 'blocked' : 'complete',
    })))
  }, [detail.data])

  const handleFrame = useCallback((frame: PlatformServerFrame) => {
    if (frame.type === 'ai_delta') {
      const text = aiDeltaText(frame.payload)
      setChat((current) => {
        const last = current.at(-1)
        if (last?.role === 'ai') {
          return [...current.slice(0, -1), { ...last, content: `${last.content}${text}` }]
        }
        return [...current, { id: `ai-${Date.now()}`, role: 'ai', content: text }]
      })
      return
    }
    if (frame.type === 'progress') {
      const progressFrame: PlatformProgressFrame = frame
      setProgress((current) => [
        ...current,
        {
          id: `progress-${Date.now()}-${current.length}`,
          label: progressFrame.message,
          meta: progressFrame.total !== undefined ? `${progressFrame.step ?? 0}/${progressFrame.total}` : undefined,
          state: progressFrame.message === 'delivered' ? 'complete' : 'active',
        },
      ])
      return
    }
    if (frame.type === 'ledger') {
      setProgress((current) => [
        ...current,
        {
          id: `ledger-${Date.now()}-${current.length}`,
          label: ledgerLabel(frame.event),
          meta: ledgerMeta(frame.event),
          state: frame.event.state === 'blocked' ? 'blocked' : frame.event.state === 'error' ? 'error' : 'complete',
        },
      ])
      return
    }
    if (frame.type === 'artifact') {
      const { type: _type, task_id: _taskId, ...artifact } = frame
      setArtifacts((current) => [...current, artifact])
      return
    }
    if (frame.type === 'blocked') {
      setBlocked((current) => [...current, frame])
      setProgress((current) => [...current, { id: `blocked-${Date.now()}`, label: t('routes.platform.blockedStep', { modality: frame.modality }), meta: frame.reason, state: 'blocked' }])
      return
    }
    if (frame.type === 'error') {
      setProgress((current) => [...current, { id: `error-${Date.now()}`, label: frame.code, meta: frame.reason, state: 'error' }])
      setChat((current) => [...current, { id: `error-${Date.now()}`, role: 'system', content: frame.reason }])
    }
  }, [t])

  const socket = useTaskSocket(taskId, auth.status === 'ready' && Boolean(detail.data?.task), handleFrame)

  const task: PlatformTask | undefined = detail.data?.task
  const displayProgress = useMemo(() => {
    if (progress.length > 0) return progress
    if (!task) return []
    const fallbackState: ProgressItem['state'] = inProgressStates.has(task.state)
      ? 'active'
      : task.state === 'blocked'
        ? 'blocked'
        : task.state === 'error'
          ? 'error'
          : 'complete'
    return [{ id: `state-${task.state}`, label: stateLabel(task.state), state: fallbackState }]
  }, [progress, task])

  if (auth.status === 'booting') {
    return <div data-testid="platform-detail-loading" className="state-panel">{t('state.loading')}</div>
  }
  if (auth.status === 'degraded') return <AuthUnavailable mode={auth.mode} />
  if (detail.isLoading) {
    return <div data-testid="platform-detail-loading" className="state-panel">{t('state.loading')}</div>
  }
  if (detail.isError || !task) {
    return <div data-testid="platform-detail-error" className="state-panel state-panel--error">{t('errors.platform')}</div>
  }

  function send(text: string) {
    setChat((current) => [...current, { id: `user-${Date.now()}`, role: 'user', content: text }])
    socket.sendMessage(text)
  }

  return (
    <section data-testid="platform-detail-root" className="stack platform-page">
      <PageHeader
        eyebrow={<Link to="/platform/history" className="platform-backlink">{t('routes.platform.backToTasks')}</Link>}
        title={task.title}
        subtitle={`${t('routes.platform.updated')} ${formatTimestamp(task.updated_ts)}`}
        actions={<TaskStateBadge state={task.state} />}
      />

      <div className="platform-detail-grid">
        <Card className="platform-chat-card">
          <CardHeader>
            <div>
              <CardTitle>{t('routes.platform.liveChat')}</CardTitle>
              <CardDescription>{t(`routes.platform.socket.${socket.status}`)}</CardDescription>
            </div>
          </CardHeader>
          <CardBody>
            <div className="platform-chat-log" aria-live="polite" aria-relevant="additions text">
              {chat.length === 0 ? (
                <p className="platform-chat-empty">{t('routes.platform.chatEmpty')}</p>
              ) : (
                chat.map((message) => (
                  <article key={message.id} className={`platform-chat-message platform-chat-message--${message.role}`}>
                    <span>{message.role === 'ai' ? t('routes.platform.ai') : message.role === 'user' ? t('routes.platform.you') : t('routes.platform.system')}</span>
                    <p>{message.content}</p>
                  </article>
                ))
              )}
            </div>
            <Composer onSend={send} disabled={socket.status === 'auth-missing'} />
          </CardBody>
        </Card>

        <ProgressRail items={displayProgress} />
      </div>

      <section className="platform-artifacts-section" aria-labelledby="platform-artifacts-title">
        <div className="item-card__topline">
          <h2 id="platform-artifacts-title" className="item-card__title">{t('routes.platform.artifacts')}</h2>
          <span className="text-muted">{artifacts.length + blocked.length}</span>
        </div>
        {artifacts.length === 0 && blocked.length === 0 ? (
          <Card><CardBody><p className="text-muted">{t('routes.platform.artifactsEmpty')}</p></CardBody></Card>
        ) : (
          <div className="platform-artifact-grid">
            {artifacts.map((artifact) => <ArtifactCard key={`${artifact.rel_path}-${artifact.sha256}`} artifact={artifact} />)}
            {blocked.map((item, index) => <BlockedArtifactCard key={`${item.modality}-${index}`} blocked={item} />)}
          </div>
        )}
      </section>
    </section>
  )
}

export const platformRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/platform',
  component: PlatformDeliverablePage,
})

export const platformHistoryRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/platform/history',
  component: PlatformHistoryPage,
})

export const platformDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/platform/$taskId',
  component: PlatformDetailPage,
})

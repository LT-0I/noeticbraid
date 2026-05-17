import { Link, createRoute, useNavigate } from '@tanstack/react-router'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { DragEvent, FormEvent } from 'react'
import { useTranslation } from 'react-i18next'

import { useAuthState } from '@/api/auth-context'
import {
  PlatformAttachmentError,
  createPlatformTaskSocket,
  downloadBlob,
  fetchPlatformArtifactBlob,
  platformAuthFrame,
  transcribePlatformAudio,
  elicitPlatformTask,
  useCreateConversationalPlatformTask,
  useCreatePlatformTask,
  useConfirmPlatformRequirements,
  useDeletePlatformAttachment,
  useElicitPlatformTask,
  usePlatformAttachments,
  usePlatformDeliverable,
  usePlatformTaskDeliverables,
  usePlatformTask,
  usePlatformTaskView,
  usePlatformTasks,
  useSendPlatformConversation,
  useSendPlatformAttachmentToHub,
  useUploadPlatformAttachment,
} from '@/api/platform-client'
import { Badge, Button, Card, CardBody, CardDescription, CardFooter, CardHeader, CardTitle, EmptyState, PageHeader } from '@/components/ui'
import type {
  ConversationalModality,
  DeliverableModality,
  PlatformAttachment,
  PlatformArtifact,
  PlatformCoarseStatusItem,
  PlatformConversationRow,
  PlatformBlockedFrame,
  PlatformDeliverableStatus,
  PlatformLedgerEvent,
  PlatformModality,
  PlatformPerTaskDeliverableItem,
  PlatformProgressFrame,
  PlatformServerFrame,
  PlatformTask,
  PlatformTaskState,
  PlatformTaskViewResponse,
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

function attachmentRejectionKey(error: unknown): string {
  if (error instanceof PlatformAttachmentError) {
    if (error.status === 413 || error.detail === 'upload_too_large') return 'routes.platform.attachments.sizeReject'
    if (error.status === 415 || error.detail === 'unsupported_attachment_type') return 'routes.platform.attachments.typeReject'
    if (error.detail === 'attachment_limit') return 'routes.platform.attachments.limitReject'
    if (error.detail === 'hub_attachment_count') return 'routes.platform.attachments.countReject'
    if (error.detail === 'invalid_attachment_name') return 'routes.platform.attachments.nameReject'
  }
  return 'routes.platform.attachments.genericReject'
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

function ModalityTile({ item, modality, calm = false }: { item: DeliverableModality | null; modality: PlatformModality; calm?: boolean }) {
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
        {/* SDD-D18 §5 / UI-SPEC v2 hard exclusion: the primary conversational
            deliverables zone must NOT surface sha/provenance/internal notes.
            Provenance stays only in the demoted /platform/_legacy/* views. */}
        {calm ? null : <Provenance item={item} />}
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


function inferConversationalModality(text: string): ConversationalModality {
  const lowered = text.toLowerCase()
  if (/(image|picture|poster|logo|图像|图片|海报)/.test(lowered)) return 'image'
  if (/(video|mp4|视频)/.test(lowered)) return 'video'
  if (/(music|song|audio|音乐|歌曲)/.test(lowered)) return 'music'
  if (/(slides|ppt|pptx|幻灯片)/.test(lowered)) return 'slides'
  if (/(code|repo|bug|代码|修复)/.test(lowered)) return 'code'
  if (/(research|analysis|analyze|研究|调研|分析)/.test(lowered)) return 'research'
  if (/(document|report|brief|doc|文档|报告)/.test(lowered)) return 'document'
  return 'text'
}

function capabilityNoticeText(notice: PlatformTaskViewResponse['capability_notice'][number], language: string): string {
  if (language.startsWith('zh')) return notice.reason_zh ?? notice.reason ?? notice.reason_en ?? ''
  return notice.reason_en ?? notice.reason ?? notice.reason_zh ?? ''
}

function latestTaskStatus(task: PlatformTask, t: (key: string) => string): string {
  return `${t('routes.platform.updated')} ${formatTimestamp(task.updated_ts)} · ${stateLabel(task.state)}`
}

function ConversationHomeComposer({ disabled }: { disabled?: boolean }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const createTask = useCreateConversationalPlatformTask()
  const [text, setText] = useState('')
  const [error, setError] = useState(false)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const raw = text.trim()
    if (!raw || disabled || createTask.isPending) return
    setError(false)
    const title = raw.split(/\n+/)[0]?.slice(0, 80) || t('routes.platform.newTask')
    try {
      const response = await createTask.mutateAsync({ title })
      await elicitPlatformTask(response.task.task_id, { raw_requirement: raw })
      setText('')
      void navigate({ to: '/platform/$taskId', params: { taskId: response.task.task_id } })
    } catch {
      setError(true)
    }
  }

  return (
    <form className="conversation-home-composer" onSubmit={submit} data-testid="platform-new-task-composer">
      <label className="form-label" htmlFor="platform-new-task-text">{t('routes.platform.describeTask')}</label>
      <textarea
        id="platform-new-task-text"
        className="platform-composer-input"
        value={text}
        onChange={(event) => setText(event.target.value)}
        rows={5}
        placeholder={t('routes.platform.describePlaceholder')}
      />
      {error ? <p className="platform-inline-error">{t('errors.platformCreate')}</p> : null}
      <div className="platform-composer-actions">
        <Button type="submit" variant="primary" disabled={disabled || !text.trim() || createTask.isPending}>
          {createTask.isPending ? t('state.loading') : t('routes.platform.newTask')}
        </Button>
      </div>
    </form>
  )
}

function PlatformConversationHome() {
  const { t } = useTranslation()
  const auth = useAuthState()
  const tasks = usePlatformTasks(auth.status === 'ready')

  if (auth.status === 'booting') return <div data-testid="platform-loading" className="state-panel">{t('state.loading')}</div>
  if (auth.status === 'degraded') return <AuthUnavailable mode={auth.mode} />
  if (tasks.isLoading) return <div data-testid="platform-loading" className="state-panel">{t('state.loading')}</div>
  if (tasks.isError) return <div data-testid="platform-error" className="state-panel state-panel--error">{t('errors.platform')}</div>

  const taskList = tasks.data?.tasks ?? []

  return (
    <section data-testid="platform-root" className="stack platform-page platform-conversation-page">
      <PageHeader
        title={t('routes.platform.conversationTitle')}
        subtitle={t('routes.platform.conversationSubtitle')}
        actions={<Link to="/platform/_legacy/deliverable" className="platform-backlink">{t('routes.platform.legacyLink')}</Link>}
      />
      <Card className="conversation-home-card">
        <CardBody>
          <ConversationHomeComposer disabled={auth.status !== 'ready'} />
        </CardBody>
      </Card>
      <section className="stack" aria-labelledby="platform-existing-tasks-title">
        <div className="item-card__topline">
          <h2 id="platform-existing-tasks-title" className="item-card__title">{t('routes.platform.existingTasks')}</h2>
          <span className="text-muted">{taskList.length}</span>
        </div>
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
                      <CardDescription>{latestTaskStatus(task, t)}</CardDescription>
                    </div>
                    <TaskStateBadge state={task.state} />
                  </CardHeader>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </section>
    </section>
  )
}

function CapabilityNoticeBanner({ notices }: { notices: PlatformTaskViewResponse['capability_notice'] }) {
  const { i18n, t } = useTranslation()
  if (notices.length === 0) return null
  return (
    <div className="platform-capability-notice" data-testid="platform-capability-notice" role="status">
      <strong>{t('routes.platform.capabilityNotice')}</strong>
      <ul>
        {notices.map((notice) => (
          <li key={`${notice.modality}-${notice.capability_status}`}>{capabilityNoticeText(notice, i18n.language)}</li>
        ))}
      </ul>
    </div>
  )
}

function ConversationTranscript({ rows }: { rows: PlatformConversationRow[] }) {
  const { t } = useTranslation()
  if (rows.length === 0) return <p className="platform-chat-empty">{t('routes.platform.chatEmpty')}</p>
  return (
    <div className="platform-chat-log" aria-live="polite" aria-relevant="additions text" data-testid="platform-conversation-log">
      {rows.map((row, index) => {
        if (row.kind === 'coarse_status') {
          return <div key={`${row.ts}-${index}`} className="platform-status-line">{row.text}</div>
        }
        return (
          <article key={`${row.ts}-${index}`} className={`platform-chat-message platform-chat-message--${row.role === 'user' ? 'user' : 'assistant'}`}>
            <span>{row.role === 'user' ? t('routes.platform.you') : t('routes.platform.ai')}</span>
            <p>{row.text}</p>
          </article>
        )
      })}
    </div>
  )
}

function ConversationalComposer({ onSend, disabled, suggestion }: { onSend: (text: string) => void; disabled?: boolean; suggestion?: string }) {
  const { t } = useTranslation()
  const [text, setText] = useState('')

  function send() {
    const trimmed = text.trim()
    if (!trimmed) return
    onSend(trimmed)
    setText('')
  }

  return (
    <div className="platform-composer">
      {suggestion ? (
        <button type="button" className="platform-suggestion" onClick={() => setText(suggestion)}>
          {t('routes.platform.useSuggestedAnswer')}: {suggestion}
        </button>
      ) : null}
      <label className="sr-only" htmlFor="platform-conversation-input">{t('routes.platform.composerLabel')}</label>
      <textarea
        id="platform-conversation-input"
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
        <Button type="button" variant="primary" disabled={disabled || !text.trim()} onClick={send}>{t('routes.platform.send')}</Button>
      </div>
    </div>
  )
}

function suggestedAnswer(rows: PlatformConversationRow[]): string | undefined {
  const lastQuestion = [...rows].reverse().find((row) => row.kind === 'question')
  if (!lastQuestion) return undefined
  const marker = 'Suggested answer:'
  const index = lastQuestion.text.indexOf(marker)
  if (index < 0) return undefined
  return lastQuestion.text.slice(index + marker.length).trim() || undefined
}

function RequirementConfirmation({ items, onConfirm, disabled }: { items: PlatformCoarseStatusItem[]; onConfirm: (items: Array<{ id: string; text: string; modality: ConversationalModality }>) => void; disabled?: boolean }) {
  const { t } = useTranslation()
  const [drafts, setDrafts] = useState(() => items.map((item) => ({ id: item.requirement_id, text: item.text, modality: inferConversationalModality(item.text) })))
  const [editing, setEditing] = useState<Record<string, boolean>>({})

  useEffect(() => {
    setDrafts(items.map((item) => ({ id: item.requirement_id, text: item.text, modality: inferConversationalModality(item.text) })))
    setEditing({})
  }, [items])

  if (items.length === 0) return null

  return (
    <Card className="platform-requirements-card" data-testid="platform-requirements-confirmation">
      <CardHeader>
        <CardTitle>{t('routes.platform.requirementsTitle')}</CardTitle>
        <CardDescription>{t('routes.platform.requirementsDescription')}</CardDescription>
      </CardHeader>
      <CardBody>
        <div className="platform-requirement-list">
          {drafts.map((draft, index) => {
            const source = items.find((item) => item.requirement_id === draft.id)
            const editId = `platform-requirement-edit-${draft.id}`
            const isEditing = editing[draft.id] === true
            return (
              <article key={draft.id} className="platform-requirement-card platform-requirement-row">
                <div className="platform-requirement-main">
                  <span className="form-label">{t('routes.platform.requirementText')}</span>
                  <p className="platform-requirement-text">{draft.text}</p>
                  {isEditing ? (
                    <label className="platform-requirement-edit" htmlFor={editId}>
                      <span className="sr-only">{t('routes.platform.requirementEditLabel')}</span>
                      <textarea
                        id={editId}
                        className="platform-input platform-requirement-edit-input"
                        value={draft.text}
                        rows={3}
                        onChange={(event) => setDrafts((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, text: event.target.value, modality: inferConversationalModality(event.target.value) } : item))}
                      />
                    </label>
                  ) : null}
                  {source?.blocked_reason ? <p className="platform-requirement-capability-line">{source.blocked_reason}</p> : null}
                </div>
                <div className="platform-requirement-meta">
                  <span className="form-label">{t('routes.platform.requirementModality')}</span>
                  <Badge className="platform-requirement-badge" tone="info">
                    {t(`modality.${draft.modality}`)}
                  </Badge>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="platform-requirement-edit-toggle"
                    aria-expanded={isEditing}
                    aria-controls={editId}
                    onClick={() => setEditing((current) => ({ ...current, [draft.id]: !isEditing }))}
                  >
                    {isEditing ? t('routes.platform.requirementEditDone') : t('routes.platform.requirementEdit')}
                  </Button>
                </div>
              </article>
            )
          })}
        </div>
      </CardBody>
      <CardFooter>
        <Button type="button" variant="primary" disabled={disabled || drafts.some((item) => !item.text.trim())} onClick={() => onConfirm(drafts)}>
          {disabled ? t('state.loading') : t('routes.platform.confirmRequirements')}
        </Button>
      </CardFooter>
    </Card>
  )
}

function CoarseStatusList({ items }: { items: PlatformCoarseStatusItem[] }) {
  const { t } = useTranslation()
  if (items.length === 0) return <p className="text-muted">{t('routes.platform.progressEmpty')}</p>
  return (
    <ol className="platform-timeline" data-testid="platform-coarse-status">
      {items.map((item) => (
        <li key={item.requirement_id} className={`platform-timeline-item platform-timeline-item--${item.coarse_state === 'blocked' ? 'blocked' : item.coarse_state === 'done' ? 'complete' : item.coarse_state === 'in_progress' ? 'active' : 'normal'}`}>
          <span className="platform-timeline-dot" aria-hidden="true" />
          <div>
            <strong>{item.text}</strong>
            <span>{item.blocked_reason ?? t(`platform.coarse.${item.coarse_state}`)}</span>
          </div>
        </li>
      ))}
    </ol>
  )
}

function ConversationalDeliverables({ deliverables }: { deliverables: PlatformTaskViewResponse['deliverables'] }) {
  const { t } = useTranslation()
  const payload = deliverables[0]
  const byModality = new Map((payload?.modalities ?? []).map((item) => [item.modality, item]))
  const items = deliverableModalities.map((modality) => normalizeModality(byModality.get(modality), modality, t))
  return (
    <section className="platform-deliverables-zone" aria-labelledby="platform-deliverables-title" data-testid="platform-deliverables-zone">
      <div className="item-card__topline">
        <h2 id="platform-deliverables-title" className="item-card__title">{t('routes.platform.deliverablesZone')}</h2>
        <span className="text-muted">{payload?.title ?? t('routes.platform.artifactsEmpty')}</span>
      </div>
      {payload ? (
        <div className="deliverable-gallery" data-testid="deliverable-gallery">
          {items.map((item, index) => (
            <ModalityTile key={deliverableModalities[index]!} item={item} modality={deliverableModalities[index]!} calm />
          ))}
        </div>
      ) : (
        <Card><CardBody><p className="text-muted">{t('routes.platform.artifactsEmpty')}</p></CardBody></Card>
      )}
    </section>
  )
}

function PerTaskDeliverables({ items }: { items?: PlatformPerTaskDeliverableItem[] }) {
  const { t } = useTranslation()
  const safeItems = (items ?? []).filter((item) => (
    item
    && typeof item.requirement_id === 'string'
    && typeof item.title === 'string'
    && item.title.trim()
    && (item.status === 'delivered' || item.status === 'blocked')
  ))
  if (safeItems.length === 0) return null

  return (
    <section className="platform-deliverables-zone" aria-labelledby="platform-pertask-deliverables-title" data-testid="platform-pertask-deliverables">
      <div className="item-card__topline">
        <h2 id="platform-pertask-deliverables-title" className="item-card__title">{t('routes.platform.pertaskDeliverables.title')}</h2>
      </div>
      <ol className="platform-timeline">
        {safeItems.map((item, index) => (
          <li key={`${item.requirement_id}-${index}`} className={`platform-timeline-item platform-timeline-item--${item.status === 'blocked' ? 'blocked' : 'complete'}`}>
            <span className="platform-timeline-dot" aria-hidden="true" />
            <div>
              <strong>{item.title}</strong>
              <span>{item.status === 'blocked' ? item.blocked_reason ?? t('routes.platform.pertaskDeliverables.blocked') : t('routes.platform.pertaskDeliverables.delivered')}</span>
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}

function TaskAttachmentRow({
  attachment,
  disabled,
  confirming,
  onConfirm,
  onDelete,
  onSend,
}: {
  attachment: PlatformAttachment
  disabled?: boolean
  confirming: boolean
  onConfirm: () => void
  onDelete: () => void
  onSend: () => void
}) {
  const { t } = useTranslation()
  return (
    <li className="platform-attachment-row">
      <div className="platform-attachment-main">
        <strong>{attachment.display_name}</strong>
        <span>{attachment.content_type || 'application/octet-stream'} · {sizeLabel(attachment.bytes)}</span>
      </div>
      <div className="platform-attachment-actions">
        <Button type="button" variant="ghost" size="sm" disabled={disabled} onClick={onSend}>
          {t('routes.platform.attachments.sendToHub')}
        </Button>
        <Button type="button" variant="ghost" size="sm" disabled={disabled} onClick={confirming ? onDelete : onConfirm}>
          {t('routes.platform.attachments.deleteAction')}
        </Button>
      </div>
      {confirming ? (
        <p className="platform-attachment-confirm" role="status">
          {t('routes.platform.attachments.deleteConfirm')}
        </p>
      ) : null}
    </li>
  )
}

function TaskAttachments({ taskId, disabled }: { taskId: string; disabled?: boolean }) {
  const { t } = useTranslation()
  const attachments = usePlatformAttachments(taskId, Boolean(taskId))
  const upload = useUploadPlatformAttachment(taskId)
  const remove = useDeletePlatformAttachment(taskId)
  const sendToHub = useSendPlatformAttachmentToHub(taskId)
  const [noticeKey, setNoticeKey] = useState<string | null>(null)
  const [uploadingName, setUploadingName] = useState<string | null>(null)
  const [confirmingId, setConfirmingId] = useState<string | null>(null)

  useEffect(() => {
    setNoticeKey(null)
    setUploadingName(null)
    setConfirmingId(null)
  }, [taskId])

  async function uploadFile(file: File | undefined) {
    if (!file || disabled || upload.isPending) return
    setNoticeKey(null)
    setUploadingName(file.name)
    try {
      await upload.mutateAsync(file)
    } catch (error) {
      setNoticeKey(attachmentRejectionKey(error))
    } finally {
      setUploadingName(null)
    }
  }

  function onDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault()
    void uploadFile(event.dataTransfer.files.item(0) ?? undefined)
  }

  async function deleteAttachment(attachmentId: string) {
    if (disabled || remove.isPending) return
    setNoticeKey(null)
    try {
      await remove.mutateAsync(attachmentId)
      setConfirmingId(null)
    } catch (error) {
      setNoticeKey(attachmentRejectionKey(error))
    }
  }

  async function sendAttachment(attachmentId: string) {
    if (disabled || sendToHub.isPending) return
    setNoticeKey(null)
    try {
      const response = await sendToHub.mutateAsync({ attachmentId })
      if (response.available === false || response.status === 'unavailable') {
        setNoticeKey('routes.platform.attachments.unavailableLine')
      }
    } catch (error) {
      setNoticeKey(attachmentRejectionKey(error))
    }
  }

  const rows = attachments.isError ? [] : attachments.data?.attachments ?? []
  const busy = disabled || upload.isPending || remove.isPending || sendToHub.isPending

  return (
    <section className="platform-attachments" aria-labelledby="platform-attachments-title" data-testid="platform-attachments">
      <div className="item-card__topline">
        <h2 id="platform-attachments-title" className="item-card__title">{t('routes.platform.attachments.title')}</h2>
        <span className="text-muted">{rows.length}</span>
      </div>
      <label
        className="platform-attachment-dropzone"
        onDragOver={(event) => event.preventDefault()}
        onDrop={onDrop}
      >
        <span>{t('routes.platform.attachments.uploadPrompt')}</span>
        <small>{t('routes.platform.attachments.dragDropHint')}</small>
        <input
          type="file"
          aria-label={t('routes.platform.attachments.uploadPrompt')}
          disabled={busy}
          onChange={(event) => {
            const files = event.currentTarget.files
            void uploadFile(files ? (typeof files.item === 'function' ? files.item(0) ?? undefined : files[0]) : undefined)
            event.currentTarget.value = ''
          }}
        />
      </label>
      {uploadingName ? <p className="platform-attachment-progress" role="status">{t('state.loading')} {uploadingName}</p> : null}
      {noticeKey ? <p className="platform-attachment-info" role="status">{t(noticeKey)}</p> : null}
      {rows.length === 0 ? (
        <p className="text-muted">{t('routes.platform.attachments.emptyHint')}</p>
      ) : (
        <ul className="platform-attachment-list" aria-label={t('routes.platform.attachments.listAria')}>
          {rows.map((attachment) => (
            <TaskAttachmentRow
              key={attachment.attachment_id}
              attachment={attachment}
              disabled={busy}
              confirming={confirmingId === attachment.attachment_id}
              onConfirm={() => setConfirmingId(attachment.attachment_id)}
              onDelete={() => { void deleteAttachment(attachment.attachment_id) }}
              onSend={() => { void sendAttachment(attachment.attachment_id) }}
            />
          ))}
        </ul>
      )}
    </section>
  )
}

function PlatformConversationTaskPage() {
  const { t } = useTranslation()
  const auth = useAuthState()
  const { taskId } = platformDetailRoute.useParams()
  const detail = usePlatformTask(taskId, auth.status === 'ready')
  const view = usePlatformTaskView(taskId, auth.status === 'ready')
  const perTaskDeliverables = usePlatformTaskDeliverables(taskId, auth.status === 'ready')
  const elicit = useElicitPlatformTask(taskId)
  const sendTurn = useSendPlatformConversation(taskId)
  const confirm = useConfirmPlatformRequirements(taskId)

  if (auth.status === 'booting' || detail.isLoading || view.isLoading) return <div data-testid="platform-detail-loading" className="state-panel">{t('state.loading')}</div>
  if (auth.status === 'degraded') return <AuthUnavailable mode={auth.mode} />
  if (detail.isError || view.isError || !detail.data?.task || !view.data) return <div data-testid="platform-detail-error" className="state-panel state-panel--error">{t('errors.platform')}</div>

  const task = detail.data.task
  const payload = view.data
  const busy = elicit.isPending || sendTurn.isPending || confirm.isPending

  function send(text: string) {
    if (payload.conversation.length === 0) {
      elicit.mutate({ raw_requirement: text })
      return
    }
    sendTurn.mutate({ text })
  }

  function confirmRequirements(items: Array<{ id: string; text: string; modality: ConversationalModality }>) {
    confirm.mutate(items)
  }

  return (
    <section data-testid="platform-conversation-root" className="stack platform-page platform-conversation-page">
      <PageHeader
        eyebrow={<Link to="/platform" className="platform-backlink">{t('routes.platform.backToTasks')}</Link>}
        title={task.title}
        subtitle={t('routes.platform.taskPanelSubtitle')}
        actions={<TaskStateBadge state={task.state} />}
      />
      <CapabilityNoticeBanner notices={payload.capability_notice} />
      <div className="platform-two-zone-grid">
        <Card className="platform-chat-card conversation-zone" data-testid="platform-conversation-zone">
          <CardHeader>
            <CardTitle>{t('routes.platform.conversationZone')}</CardTitle>
            <CardDescription>{t('routes.platform.conversationZoneDescription')}</CardDescription>
          </CardHeader>
          <CardBody>
            <ConversationTranscript rows={payload.conversation} />
            <ConversationalComposer onSend={send} disabled={busy} suggestion={suggestedAnswer(payload.conversation)} />
            <TaskAttachments taskId={taskId} disabled={busy} />
          </CardBody>
        </Card>
        <aside className="platform-rail">
          <h2>{t('routes.platform.progressRail')}</h2>
          <CoarseStatusList items={payload.coarse_status} />
        </aside>
      </div>
      <RequirementConfirmation items={payload.coarse_status} onConfirm={confirmRequirements} disabled={busy} />
      <ConversationalDeliverables deliverables={payload.deliverables} />
      <PerTaskDeliverables items={perTaskDeliverables.isError ? undefined : perTaskDeliverables.data?.deliverables} />
    </section>
  )
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
        <Link to="/platform/_legacy/history" className="platform-backlink">{t('routes.platformDeliverable.viewDebugList')}</Link>
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
          void navigate({ to: '/platform/_legacy/tasks/$taskId', params: { taskId: task.task_id } })
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
        eyebrow={<Link to="/platform/_legacy/deliverable" className="platform-backlink">{t('routes.platformDeliverable.eyebrow')}</Link>}
        title={t('routes.platform.historyTitle')}
        subtitle={t('routes.platform.historySubtitle')}
        actions={<Button type="button" variant="primary" onClick={() => setModalOpen(true)}>{t('routes.platform.newTask')}</Button>}
      />

      {taskList.length === 0 ? (
        <EmptyState title={t('empty.platform.title')} message={t('empty.platform.message')} />
      ) : (
        <div className="platform-task-grid" data-testid="platform-task-list">
          {taskList.map((task) => (
            <Link key={task.task_id} to="/platform/_legacy/tasks/$taskId" params={{ taskId: task.task_id }} className="platform-task-card">
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
        eyebrow={<Link to="/platform/_legacy/history" className="platform-backlink">{t('routes.platform.backToTasks')}</Link>}
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
  component: PlatformConversationHome,
})

export const platformLegacyDeliverableRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/platform/_legacy/deliverable',
  component: PlatformDeliverablePage,
})

export const platformLegacyHistoryRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/platform/_legacy/history',
  component: PlatformHistoryPage,
})

export const platformLegacyDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/platform/_legacy/tasks/$taskId',
  component: PlatformDetailPage,
})

export const platformDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/platform/$taskId',
  component: PlatformConversationTaskPage,
})

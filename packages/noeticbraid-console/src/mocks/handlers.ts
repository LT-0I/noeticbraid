import { http, HttpResponse } from 'msw'

import type {
  CandidateLesson,
  CapabilitiesResponse,
  CapabilityHealthCheckResponse,
  CapabilityHealthResult,
  CapabilityRegistryEntry,
  OMCProjectFixture,
  OMCProjectTaskRequest,
  RunRecord,
} from '@/types/contracts'
import type { PlatformArtifact, PlatformDeliverable, PlatformTask, PlatformTaskViewResponse } from '@/types/platform'

import accountStatus from './fixtures/account_status.json'
import approvals from './fixtures/approvals.json'
import capabilitiesFixture from './fixtures/capabilities.json'
import dashboardEmpty from './fixtures/dashboard_empty.json'
import omcProjectFixture from './fixtures/omc_project.json'
import runs from './fixtures/runs.json'
import threads from './fixtures/threads.json'

const omcProject = omcProjectFixture as OMCProjectFixture
const seedCandidate = omcProject.candidates[0]!
const seedRunRecord = omcProject.run_records[0]!
const initialCapabilities = capabilitiesFixture as CapabilitiesResponse
let candidates: CandidateLesson[] = omcProject.candidates.map((candidate) => ({ ...candidate }))
let adoptedHistory: CandidateLesson[] = omcProject.adopted_history.map((candidate) => ({ ...candidate }))
let omcRunRecords: RunRecord[] = omcProject.run_records.map((record) => ({ ...record }))
let capabilities: CapabilityRegistryEntry[] = initialCapabilities.capabilities.map((capability) => ({ ...capability }))

const platformArtifact: PlatformArtifact = {
  modality: 'document',
  rel_path: 'tasks/task_platform_seed/artifacts/01-document.md',
  filename: 'brief.md',
  sha256: '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef',
  bytes: 128,
}
const platformDeliverable: PlatformDeliverable = {
  title: 'NoeticBraid promo material',
  generated_at: '2026-05-17T06:51:59Z',
  modalities: [
    {
      modality: 'document',
      status: 'delivered',
      title: 'NoeticBraid Promo Document',
      filename: 'NoeticBraid-Promo-Document.md',
      content_type: 'text/markdown; charset=utf-8',
      bytes: 128,
      sha256: '1111111111111111111111111111111111111111111111111111111111111111',
      download_url: '/platform/deliverable/artifacts/document',
      blocked_reason: null,
      provenance: {
        source_task_id: 'task_promo_smoke_1778967211',
        ledgered: true,
        kind: 'ai_produced_markdown',
        note: 'AI-produced markdown artifact recorded in the source task ledger.',
        source_artifact_sha256: '1111111111111111111111111111111111111111111111111111111111111111',
      },
    },
    {
      modality: 'slides',
      status: 'converted',
      title: 'NoeticBraid Promo Deck',
      filename: 'NoeticBraid-Promo-Deck.pptx',
      content_type: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
      bytes: 2048,
      sha256: '2222222222222222222222222222222222222222222222222222222222222222',
      download_url: '/platform/deliverable/artifacts/slides',
      blocked_reason: null,
      provenance: {
        source_task_id: 'task_promo_chatgpt_1778967273',
        ledgered: true,
        kind: 'local_format_conversion',
        note: 'Rendered locally on 2026-05-17T06:51:59Z from AI-produced markdown. NOT an AI-generated binary.',
        source_artifact_sha256: 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
      },
    },
    {
      modality: 'poster',
      status: 'converted',
      title: 'NoeticBraid Promo Poster',
      filename: 'NoeticBraid-Promo-Poster.png',
      content_type: 'image/png',
      bytes: 512,
      sha256: '3333333333333333333333333333333333333333333333333333333333333333',
      download_url: '/platform/deliverable/artifacts/poster',
      blocked_reason: null,
      provenance: {
        source_task_id: 'task_promo_chatgpt_1778967273',
        ledgered: true,
        kind: 'local_format_conversion',
        note: 'Rendered locally on 2026-05-17T06:51:59Z from AI-produced markdown. NOT an AI-generated binary.',
        source_artifact_sha256: 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
      },
    },
    {
      modality: 'image',
      status: 'blocked',
      title: 'NoeticBraid Promo Image',
      filename: 'NoeticBraid-Promo-Image.png',
      content_type: 'image/png',
      bytes: 256,
      sha256: '4444444444444444444444444444444444444444444444444444444444444444',
      download_url: '/platform/deliverable/artifacts/image',
      blocked_reason: 'hub dispatch timed out',
      provenance: {
        source_task_id: 'task_promo_image_1778991545',
        ledgered: false,
        kind: 'on_disk_unledgered_real_binary',
        note: 'Real PNG exists on disk but is not ledgered.',
      },
    },
    {
      modality: 'video',
      status: 'blocked',
      title: 'NoeticBraid Promo Video',
      filename: 'NoeticBraid-Promo-Video.mp4',
      content_type: 'video/mp4',
      bytes: 1024,
      sha256: '5555555555555555555555555555555555555555555555555555555555555555',
      download_url: '/platform/deliverable/artifacts/video',
      blocked_reason: 'artifact path governance violation',
      provenance: {
        source_task_id: 'task_promo_gemini_1778968111',
        ledgered: false,
        kind: 'on_disk_unledgered_real_binary',
        note: 'Real MP4 exists on disk but is not ledgered.',
      },
    },
    {
      modality: 'music',
      status: 'blocked',
      title: 'NoeticBraid Promo Music',
      filename: 'NoeticBraid-Promo-Music.mp3',
      content_type: 'audio/mpeg',
      bytes: null,
      sha256: null,
      download_url: null,
      blocked_reason: 'Music generation was not attempted for this deliverable.',
      provenance: {
        source_task_id: null,
        ledgered: false,
        kind: 'not_attempted',
        note: 'Music generation was not attempted for this deliverable.',
      },
    },
  ],
}
let platformTasks: PlatformTask[] = [
  {
    task_id: 'task_platform_seed',
    title: 'Prepare launch brief',
    state: 'created',
    created_ts: '2026-05-16T12:00:00Z',
    updated_ts: '2026-05-16T12:05:00Z',
    modality_targets: ['document', 'slides'],
  },
]

const emptyTaskView = (): PlatformTaskViewResponse => ({
  conversation: [],
  deliverables: [],
  coarse_status: [],
  capability_notice: [],
})

let platformViews: Record<string, PlatformTaskViewResponse> = {
  task_platform_seed: {
    conversation: [
      { ts: '2026-05-16T12:00:00Z', role: 'user', kind: 'message', text: 'Prepare launch brief' },
      { ts: '2026-05-16T12:01:00Z', role: 'assistant', kind: 'question', text: 'Should this be a document or a slide deck?\n\nSuggested answer: Start with a document brief.' },
    ],
    deliverables: [],
    coarse_status: [
      { requirement_id: 'req_seed', text: 'Prepare launch brief', coarse_state: 'pending', capability_status: 'supported' },
    ],
    capability_notice: [],
  },
}

// SDD-D8-02: the happy-path startup token MSW handler issues the bearer in the
// X-NoeticBraid-Bearer response header (same-origin, so readable in dev/test).
const MOCK_BEARER = 'mock-startup-bearer-token'

function isAuthorized(request: Request): boolean {
  return request.headers.get('Authorization') === `Bearer ${MOCK_BEARER}`
}

function utcNow(): string {
  return '2026-05-12T12:30:00Z'
}

function adoptionArtifact(candidateId: string): string {
  return `.omx/artifacts/candidate-adoption-${candidateId}-20260512T123000Z.md`
}

function latestRuns(): { runs: RunRecord[] } {
  return { runs: [...(runs as { runs: RunRecord[] }).runs, ...omcRunRecords] }
}

export const coreHandlers = [
  http.get('/api/health', () =>
    HttpResponse.json({
      status: 'ok',
      contract_version: '1.3.0',
      authoritative: true,
    }),
  ),
  http.get('/api/dashboard/empty', () => HttpResponse.json(dashboardEmpty)),
  http.get('/api/workspace/threads', () => HttpResponse.json(threads)),
  http.get('/api/ledger/runs', () => HttpResponse.json(latestRuns())),
  http.get('/api/approval/queue', () => HttpResponse.json(approvals)),
  http.get('/api/projects/omc-ingest/candidates', () =>
    HttpResponse.json({ project_id: 'omc-ingest', candidates }),
  ),
  http.get('/api/projects/omc-ingest/adopted-history', () =>
    HttpResponse.json({ project_id: 'omc-ingest', adopted_candidates: adoptedHistory }),
  ),
  http.post('/api/projects/omc-ingest/tasks', async ({ request }) => {
    const payload = (await request.json()) as OMCProjectTaskRequest
    const candidateId = 'memory_omc_ingest_debate_loop'
    const candidate: CandidateLesson = {
      ...seedCandidate,
      candidate_id: candidateId,
      summary: payload.prompt || seedCandidate.summary,
      status: 'candidate',
      adopted_at: null,
      adopted_by: null,
    }
    candidates = [candidate]
    const record: RunRecord = {
      ...seedRunRecord,
      run_id: 'run_omc_ingest_debate_loop',
      event_type: 'lesson_candidate_created',
      created_at: utcNow(),
    }
    omcRunRecords = [record]
    return HttpResponse.json({
      project_id: 'omc-ingest',
      task_id: 'task_omc_ingest',
      candidate_id: candidateId,
      convergence_markdown_ref: '.omx/artifacts/convergence_omc_ingest_debate_loop.md',
      run_record_ref: candidate.run_record_ref,
      artifact_refs: candidate.artifact_refs,
      candidate,
      run_records: [record],
    })
  }),
  http.post('/api/candidates/:id/adopt', ({ params }) => {
    const candidateId = String(params.id)
    const existing = candidates.find((candidate) => candidate.candidate_id === candidateId)
    if (!existing) {
      return HttpResponse.json({ detail: 'candidate not found' }, { status: 404 })
    }
    const artifact = adoptionArtifact(candidateId)
    const adopted: CandidateLesson = {
      ...existing,
      status: 'adopted',
      adopted_at: utcNow(),
      adopted_by: 'user',
      artifact_refs: [...existing.artifact_refs, artifact],
      reuse_evidence_refs: [`artifact_candidate_adoption_${candidateId}_20260512T123000Z`],
    }
    candidates = candidates.map((candidate) => (candidate.candidate_id === candidateId ? adopted : candidate))
    adoptedHistory = [adopted, ...adoptedHistory.filter((candidate) => candidate.candidate_id !== candidateId)]
    omcRunRecords = [
      ...omcRunRecords,
      {
        ...seedRunRecord,
        run_id: adopted.run_record_ref ?? 'run_omc_ingest_debate_loop',
        event_type: 'artifact_created',
        created_at: utcNow(),
        artifact_refs: [`artifact_candidate_adoption_${candidateId}_20260512T123000Z`],
      },
    ]
    return HttpResponse.json({
      project_id: 'omc-ingest',
      candidate_id: candidateId,
      status: 'adopted',
      adopted_at: utcNow(),
      adopted_by: 'user',
      run_record_ref: adopted.run_record_ref,
      adoption_artifact_ref: artifact,
      ledger_refs: [adopted.run_record_ref, `artifact_candidate_adoption_${candidateId}_20260512T123000Z`],
      candidate: adopted,
    })
  }),
  http.get('/api/capabilities', () => HttpResponse.json({ capabilities })),
  http.get('/api/account/status', ({ request }) => {
    if (!isAuthorized(request)) return new HttpResponse(null, { status: 401 })
    return HttpResponse.json(accountStatus)
  }),
  http.get('/api/account/pool', ({ request }) => {
    if (!isAuthorized(request)) return new HttpResponse(null, { status: 401 })
    return HttpResponse.json(accountStatus)
  }),
  http.post('/api/capabilities/:id/health-check', ({ params }) => {
    const capabilityId = String(params.id)
    const capability = capabilities.find((item) => item.capability_id === capabilityId)
    if (!capability) {
      return HttpResponse.json({ detail: 'capability not found' }, { status: 404 })
    }
    const result: CapabilityHealthResult = {
      capability_id: capabilityId,
      mode: 'mock',
      status: 'available',
      checked_at: utcNow(),
      summary: `Mock health OK for ${capability.display_name}`,
      artifact_ref: null,
    }
    const updated: CapabilityRegistryEntry = {
      ...capability,
      status: 'available',
      health_mode: 'mock',
      last_checked_at: result.checked_at,
      last_result: result,
    }
    capabilities = capabilities.map((item) => (item.capability_id === capabilityId ? updated : item))
    const response: CapabilityHealthCheckResponse = { capability: updated, result }
    return HttpResponse.json(response)
  }),
]

function capabilityNoticeFor(modality: string) {
  if (modality === 'image') {
    return {
      modality: 'image' as const,
      capability_status: 'unavailable' as const,
      reason: '图像生成目前还达不到，这部分我们暂时做不了。',
      reason_zh: '图像生成目前还达不到，这部分我们暂时做不了。',
      reason_en: 'Image generation is not good enough yet, so we cannot do this part for now.',
    }
  }
  return null
}

function inferMockModality(text: string) {
  const lowered = text.toLowerCase()
  if (lowered.includes('image') || lowered.includes('picture') || lowered.includes('图像')) return 'image'
  if (lowered.includes('video')) return 'video'
  if (lowered.includes('music') || lowered.includes('song')) return 'music'
  if (lowered.includes('slide') || lowered.includes('ppt')) return 'slides'
  if (lowered.includes('research')) return 'research'
  if (lowered.includes('code')) return 'code'
  if (lowered.includes('document') || lowered.includes('brief') || lowered.includes('report')) return 'document'
  return 'text'
}

export const platformHandlers = [
  http.get('/platform/deliverable', ({ request }) => {
    if (!isAuthorized(request)) return new HttpResponse(null, { status: 401 })
    return HttpResponse.json({ deliverable: platformDeliverable })
  }),
  http.get('/platform/deliverable/artifacts/:modality', ({ params, request }) => {
    if (!isAuthorized(request)) return new HttpResponse(null, { status: 401 })
    const modality = String(params.modality)
    if (modality === 'document') {
      return new HttpResponse('# NoeticBraid promo\\n\\nTraceable execution.\\n', {
        headers: { 'Content-Type': 'text/markdown; charset=utf-8' },
      })
    }
    if (modality === 'video') {
      return new HttpResponse(new Uint8Array([0, 0, 0, 32, 102, 116, 121, 112]), {
        headers: { 'Content-Type': 'video/mp4' },
      })
    }
    if (modality === 'slides') {
      return new HttpResponse(new Uint8Array([80, 75, 3, 4]), {
        headers: { 'Content-Type': 'application/vnd.openxmlformats-officedocument.presentationml.presentation' },
      })
    }
    if (modality === 'poster' || modality === 'image') {
      return new HttpResponse(new Uint8Array([137, 80, 78, 71]), {
        headers: { 'Content-Type': 'image/png' },
      })
    }
    return new HttpResponse(null, { status: 404 })
  }),
  http.get('/platform/tasks', ({ request }) => {
    if (!isAuthorized(request)) return new HttpResponse(null, { status: 401 })
    return HttpResponse.json({ tasks: platformTasks })
  }),
  http.post('/platform/tasks', async ({ request }) => {
    if (!isAuthorized(request)) return new HttpResponse(null, { status: 401 })
    const payload = (await request.json()) as { title: string; modality_targets?: PlatformTask['modality_targets'] }
    const task: PlatformTask = {
      task_id: `task_platform_${platformTasks.length + 1}`,
      title: payload.title,
      state: 'created',
      created_ts: utcNow(),
      updated_ts: utcNow(),
      modality_targets: payload.modality_targets ?? [],
    }
    platformTasks = [task, ...platformTasks]
    const view = emptyTaskView()
    platformViews[task.task_id] = view
    return HttpResponse.json({ task, view })
  }),
  http.get('/platform/tasks/:taskId/view', ({ params, request }) => {
    if (!isAuthorized(request)) return new HttpResponse(null, { status: 401 })
    const taskId = String(params.taskId)
    if (!platformTasks.some((item) => item.task_id === taskId)) return HttpResponse.json({ detail: 'task not found' }, { status: 404 })
    return HttpResponse.json(platformViews[taskId] ?? emptyTaskView())
  }),
  http.get('/platform/tasks/:taskId/deliverables', ({ request }) => {
    if (!isAuthorized(request)) return new HttpResponse(null, { status: 401 })
    return HttpResponse.json({ deliverables: [] })
  }),
  http.post('/platform/tasks/:taskId/elicit', async ({ params, request }) => {
    if (!isAuthorized(request)) return new HttpResponse(null, { status: 401 })
    const taskId = String(params.taskId)
    const payload = (await request.json()) as { raw_requirement: string }
    const modality = inferMockModality(payload.raw_requirement)
    const view: PlatformTaskViewResponse = {
      ...(platformViews[taskId] ?? emptyTaskView()),
      conversation: [
        ...(platformViews[taskId]?.conversation ?? []),
        { ts: utcNow(), role: 'user', kind: 'message', text: payload.raw_requirement },
        { ts: utcNow(), role: 'assistant', kind: 'question', text: `Should I structure this as ${modality}?\n\nSuggested answer: Yes, structure it as ${modality}.` },
      ],
      coarse_status: [
        { requirement_id: 'req_1', text: payload.raw_requirement, coarse_state: 'pending', capability_status: 'supported' },
      ],
    }
    platformViews[taskId] = view
    return HttpResponse.json({ view })
  }),
  http.post('/platform/tasks/:taskId/conversation', async ({ params, request }) => {
    if (!isAuthorized(request)) return new HttpResponse(null, { status: 401 })
    const taskId = String(params.taskId)
    const payload = (await request.json()) as { text: string }
    const previous = platformViews[taskId] ?? emptyTaskView()
    const view: PlatformTaskViewResponse = {
      ...previous,
      conversation: [
        ...previous.conversation,
        { ts: utcNow(), role: 'user', kind: 'answer', text: payload.text },
        { ts: utcNow(), role: 'assistant', kind: 'message', text: 'I can draft the requirement list now. Please confirm before execution.' },
      ],
    }
    platformViews[taskId] = view
    return HttpResponse.json({ view })
  }),
  http.post('/platform/tasks/:taskId/requirements/confirm', async ({ params, request }) => {
    if (!isAuthorized(request)) return new HttpResponse(null, { status: 401 })
    const taskId = String(params.taskId)
    const payload = (await request.json()) as { requirements: Array<{ id: string; text: string; modality: string }> }
    const notices = payload.requirements.map((item) => capabilityNoticeFor(item.modality)).filter((item): item is NonNullable<ReturnType<typeof capabilityNoticeFor>> => item !== null)
    const view: PlatformTaskViewResponse = {
      ...(platformViews[taskId] ?? emptyTaskView()),
      capability_notice: notices,
      coarse_status: payload.requirements.map((item) => {
        const notice = capabilityNoticeFor(item.modality)
        return {
          requirement_id: item.id,
          text: item.text,
          coarse_state: notice ? 'blocked' : 'pending',
          capability_status: notice ? notice.capability_status : 'supported',
          ...(notice ? { blocked_reason: notice.reason ?? undefined } : {}),
        }
      }),
    }
    platformViews[taskId] = view
    return HttpResponse.json({ requirements: { task_id: taskId, schema_version: 1, status: 'confirmed', confirmed_at: utcNow(), requirements: payload.requirements }, view })
  }),
  http.get('/platform/capabilities', ({ request }) => {
    if (!isAuthorized(request)) return new HttpResponse(null, { status: 401 })
    return HttpResponse.json({
      capabilities: [
        { modality: 'text', capability_status: 'supported', reason_zh: null, reason_en: null },
        { modality: 'document', capability_status: 'supported', reason_zh: null, reason_en: null },
        { modality: 'research', capability_status: 'supported', reason_zh: null, reason_en: null },
        { modality: 'code', capability_status: 'supported', reason_zh: null, reason_en: null },
        { modality: 'image', capability_status: 'unavailable', reason_zh: '图像生成目前还达不到，这部分我们暂时做不了。', reason_en: 'Image generation is not good enough yet, so we cannot do this part for now.' },
      ],
    })
  }),
  http.get('/platform/tasks/:taskId', ({ params, request }) => {
    if (!isAuthorized(request)) return new HttpResponse(null, { status: 401 })
    const task = platformTasks.find((item) => item.task_id === String(params.taskId))
    if (!task) return HttpResponse.json({ detail: 'task not found' }, { status: 404 })
    return HttpResponse.json({
      task,
      ledger: [
        { event_type: 'task_created', state: task.state, created_at: task.created_ts },
      ],
      artifacts: task.task_id === 'task_platform_seed' ? [platformArtifact] : [],
    })
  }),
  http.get('/platform/artifacts', ({ request }) => {
    if (!isAuthorized(request)) return new HttpResponse(null, { status: 401 })
    return new HttpResponse('# Mock platform artifact\n', {
      headers: { 'Content-Type': 'text/markdown; charset=utf-8' },
    })
  }),
  http.post('/platform/stt/transcribe', ({ request }) => {
    if (!isAuthorized(request)) return new HttpResponse(null, { status: 401 })
    return HttpResponse.json({ status: 'not_provisioned' })
  }),
  http.post('/api/auth/startup_token', () =>
    HttpResponse.json(
      { accepted: true, mode: 'bearer_header_issued' },
      { headers: { 'X-NoeticBraid-Bearer': MOCK_BEARER } },
    ),
  ),
]

export const handlers = [...coreHandlers, ...platformHandlers]

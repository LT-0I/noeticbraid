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

export const handlers = [
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
  http.post('/api/auth/startup_token', () =>
    HttpResponse.json(
      { accepted: true, mode: 'bearer_header_issued' },
      { headers: { 'X-NoeticBraid-Bearer': MOCK_BEARER } },
    ),
  ),
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

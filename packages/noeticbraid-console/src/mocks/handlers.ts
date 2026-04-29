import { http, HttpResponse } from 'msw'

import approvals from './fixtures/approvals.json'
import dashboardEmpty from './fixtures/dashboard_empty.json'
import runs from './fixtures/runs.json'
import threads from './fixtures/threads.json'

export const handlers = [
  http.get('/api/health', () =>
    HttpResponse.json({
      status: 'ok',
      contract_version: '1.0.0',
      authoritative: true,
    }),
  ),
  http.get('/api/dashboard/empty', () => HttpResponse.json(dashboardEmpty)),
  http.get('/api/workspace/threads', () => HttpResponse.json(threads)),
  http.get('/api/ledger/runs', () => HttpResponse.json(runs)),
  http.get('/api/approval/queue', () => HttpResponse.json(approvals)),
]

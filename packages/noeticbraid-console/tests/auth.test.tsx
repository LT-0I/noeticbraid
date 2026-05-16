import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider, createMemoryHistory, createRouter } from '@tanstack/react-router'
import { http, HttpResponse } from 'msw'
import { afterEach, beforeEach, describe, expect, test } from 'vitest'

import {
  AuthUnavailableError,
  clearBearer,
  ensureBearer,
  getBearer,
} from '../src/api/auth'
import { fetchAccountStatus } from '../src/api/client'
import { server } from '../src/mocks/server'
import { routeTree } from '../src/routes/routeTree'

const MOCK_BEARER = 'mock-startup-bearer-token'

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

beforeEach(() => {
  clearBearer()
})

afterEach(() => {
  clearBearer()
})

describe('console bearer auth', () => {
  test('bootstrap success stores bearer and injects Authorization on subsequent calls', async () => {
    let seenAuth: string | null = null
    server.use(
      http.get('/api/account/status', ({ request }) => {
        seenAuth = request.headers.get('Authorization')
        if (seenAuth !== `Bearer ${MOCK_BEARER}`) {
          return new HttpResponse(null, { status: 401 })
        }
        return HttpResponse.json({ accounts: [] })
      }),
    )

    const result = await ensureBearer()
    expect(result.ok).toBe(true)
    expect(getBearer()).toBe(MOCK_BEARER)

    await fetchAccountStatus()
    expect(seenAuth).toBe(`Bearer ${MOCK_BEARER}`)
  })

  test('accepted:false bootstrap yields degraded result carrying mode', async () => {
    server.use(
      http.post('/api/auth/startup_token', () =>
        HttpResponse.json({ accepted: false, mode: 'dpapi_unavailable' }),
      ),
    )

    const result = await ensureBearer()
    expect(result.ok).toBe(false)
    expect(result.mode).toBe('dpapi_unavailable')
    expect(getBearer()).toBeNull()
  })

  test('401 triggers a single re-bootstrap retry then resolves with token', async () => {
    let bootstrapCalls = 0
    let statusCalls = 0
    server.use(
      http.post('/api/auth/startup_token', () => {
        bootstrapCalls += 1
        return HttpResponse.json(
          { accepted: true, mode: 'bearer_header_issued' },
          { headers: { 'X-NoeticBraid-Bearer': MOCK_BEARER } },
        )
      }),
      http.get('/api/account/status', ({ request }) => {
        statusCalls += 1
        if (request.headers.get('Authorization') !== `Bearer ${MOCK_BEARER}`) {
          return new HttpResponse(null, { status: 401 })
        }
        return HttpResponse.json({ accounts: [] })
      }),
    )

    // No bearer yet → first call 401s, one re-bootstrap, one retry succeeds.
    await fetchAccountStatus()
    expect(bootstrapCalls).toBe(1)
    expect(statusCalls).toBe(2)
  })

  test('401 with failing bootstrap throws a typed AuthUnavailableError carrying mode', async () => {
    server.use(
      http.post('/api/auth/startup_token', () =>
        HttpResponse.json({ accepted: false, mode: 'token_store_unavailable' }),
      ),
      http.get('/api/account/status', () => new HttpResponse(null, { status: 401 })),
    )

    await expect(fetchAccountStatus()).rejects.toBeInstanceOf(AuthUnavailableError)
    await expect(fetchAccountStatus()).rejects.toMatchObject({ mode: 'token_store_unavailable' })
  })

  test('accounts page renders auth-unavailable state with mode when degraded', async () => {
    server.use(
      http.post('/api/auth/startup_token', () =>
        HttpResponse.json({ accepted: false, mode: 'startup_credential_unavailable' }),
      ),
    )

    renderAt('/accounts')

    await waitFor(() => expect(screen.getByTestId('auth-unavailable')).toBeInTheDocument())
    expect(screen.getByTestId('auth-unavailable')).toHaveTextContent('startup credential unavailable')
    expect(screen.queryByTestId('account-list')).not.toBeInTheDocument()
  })

  test('public pages keep working while auth is degraded', async () => {
    server.use(
      http.post('/api/auth/startup_token', () =>
        HttpResponse.json({ accepted: false, mode: 'dpapi_unavailable' }),
      ),
    )

    renderAt('/capabilities')
    await waitFor(() => expect(screen.getByTestId('capabilities-root')).toBeInTheDocument())
  })
})

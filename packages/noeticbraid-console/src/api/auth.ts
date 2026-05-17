import type { AuthResponse } from '@/types/contracts'

/**
 * SDD-D8-02 console-wide bearer bootstrap.
 *
 * The startup bearer is a short-lived (TTL 30 min) bootstrap secret. It is
 * held ONLY in this module-level variable — never localStorage/sessionStorage
 * — so a full reload simply re-bootstraps. 401-driven re-bootstrap is the only
 * refresh path; there is no refresh timer and no token persistence.
 */

const BEARER_HEADER = 'X-NoeticBraid-Bearer'

let bearerToken: string | null = null

export function getBearer(): string | null {
  return bearerToken
}

export function setBearer(token: string): void {
  bearerToken = token
}

export function clearBearer(): void {
  bearerToken = null
}

export interface EnsureBearerResult {
  ok: boolean
  mode?: string
}

/** Typed auth error thrown when a protected call cannot be authorized. */
export class AuthUnavailableError extends Error {
  readonly mode: string

  constructor(mode: string) {
    super(`auth unavailable: ${mode}`)
    this.name = 'AuthUnavailableError'
    this.mode = mode
  }
}

let inFlight: Promise<EnsureBearerResult> | null = null

async function bootstrap(): Promise<EnsureBearerResult> {
  // NOTE: Against a real browser+backend the response header
  // `X-NoeticBraid-Bearer` is only readable once the backend CORS config adds
  // it to `expose_headers` (deferred backend stage-2.3 / Part 2). Under
  // same-origin MSW (dev/test) the header is readable, so this path works
  // without any backend/CORS change here.
  let res: Response
  try {
    res = await fetch('/api/auth/startup_token', { method: 'POST' })
  } catch {
    return { ok: false, mode: 'network_unavailable' }
  }

  if (!res.ok) {
    return { ok: false, mode: `http_${res.status}` }
  }

  let body: AuthResponse
  try {
    body = (await res.json()) as AuthResponse
  } catch {
    // A 2xx that is not JSON (e.g. an SPA HTML fallback when the mock/back
    // end is not intercepting) must degrade, never reject: a rejected
    // bootstrap leaves the single-flight promise unsettled and the auth
    // state stuck on `booting` (infinite loading panel).
    return { ok: false, mode: 'bad_response' }
  }
  if (body.accepted === true) {
    const header = res.headers.get(BEARER_HEADER)
    if (header) {
      setBearer(header)
      return { ok: true }
    }
    return { ok: false, mode: 'bearer_header_missing' }
  }
  return { ok: false, mode: body.mode }
}

/**
 * Idempotent single-flight bootstrap: concurrent callers share one in-flight
 * `POST /api/auth/startup_token`.
 */
export function ensureBearer(): Promise<EnsureBearerResult> {
  if (inFlight) return inFlight
  inFlight = bootstrap().finally(() => {
    inFlight = null
  })
  return inFlight
}

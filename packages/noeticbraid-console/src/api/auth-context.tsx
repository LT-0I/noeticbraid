import { createContext, useContext, useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'

import { ensureBearer } from './auth'

/**
 * SDD-D8-02 console-wide auth state.
 *
 * `booting`  → initial bootstrap in flight
 * `ready`    → bearer obtained; protected pages may load normally
 * `degraded` → bootstrap rejected; protected pages show a clear
 *              auth-unavailable state carrying `mode` (no silent 401s)
 */
export type AuthState =
  | { status: 'booting' }
  | { status: 'ready' }
  | { status: 'degraded'; mode: string }

const AuthContext = createContext<AuthState>({ status: 'booting' })

export function useAuthState(): AuthState {
  return useContext(AuthContext)
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: 'booting' })
  const started = useRef(false)

  useEffect(() => {
    if (started.current) return
    started.current = true
    let active = true
    void ensureBearer().then((result) => {
      if (!active) return
      setState(result.ok ? { status: 'ready' } : { status: 'degraded', mode: result.mode ?? 'unknown' })
    })
    return () => {
      active = false
    }
  }, [])

  return <AuthContext.Provider value={state}>{children}</AuthContext.Provider>
}

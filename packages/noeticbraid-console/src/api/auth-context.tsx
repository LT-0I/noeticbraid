import { createContext, useContext, useEffect, useState } from 'react'
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

  useEffect(() => {
    // NO ref-guard here. `ensureBearer()` is itself single-flight (module
    // level `inFlight`), so re-invoking it is idempotent and cheap. A ref
    // guard combined with the `active` cleanup is actively WRONG under
    // React StrictMode: mount registers the only settle callback, the
    // immediate StrictMode unmount's cleanup sets active=false killing it,
    // and the remount's effect would early-return via the guard registering
    // nothing — leaving auth stuck on `booting` forever (the infinite
    // "正在载入" panel). Letting every effect run keeps a live callback.
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

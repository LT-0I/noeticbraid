import { setupWorker } from 'msw/browser'

import { coreHandlers, handlers } from './handlers'

export const worker = setupWorker(...(import.meta.env.VITE_PLATFORM_LIVE === '1' ? coreHandlers : handlers))
